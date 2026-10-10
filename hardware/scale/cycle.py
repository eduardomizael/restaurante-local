"""Pure physical cycle for scale captures; no ORM, serial or threads."""

from collections import deque
from dataclasses import dataclass
import math
from uuid import uuid4


@dataclass(frozen=True)
class CaptureCandidate:
    capture_key: object
    net_weight_grams: int
    tare_grams: int | None


class CaptureCycle:
    """Require zero, recent stable samples and removal for each capture.

    Args:
        sample_count: Consecutive samples required within the tolerance window.
        tolerance_grams: Maximum variation within that window.
        zero_grams: Maximum absolute weight considered removal/zero.
        zero_sample_count: Consecutive nonmoving near-zero readings to rearm.
        maximum_silence_seconds: Bounded empty-reply gap; zero disables recovery.
        minimum_grams: Minimum positive commercial weight.
        maximum_age_seconds: Age/gap above which samples are rejected or reset.
        profile: Technical profile recorded with each persisted capture.
    """

    def __init__(self, sample_count=3, tolerance_grams=2, zero_grams=0,
                 minimum_grams=11, maximum_age_seconds=2, profile="SIMULATION_ONLY",
                 zero_sample_count=1, maximum_silence_seconds=0):
        self.sample_count = sample_count
        self.tolerance_grams = tolerance_grams
        self.zero_grams = zero_grams
        self.zero_sample_count = zero_sample_count
        self.maximum_silence_seconds = maximum_silence_seconds
        self.minimum_grams = minimum_grams
        self.maximum_age_seconds = maximum_age_seconds
        self.profile = profile
        self.samples = deque(maxlen=sample_count)
        self.reset()

    def reset(self):
        """Disarm after startup, pause, reconnect or configuration change."""
        self.status = "WAITING_ZERO"
        self.samples.clear()
        self.candidate = None
        self.last_sampled_at = None
        self.zero_samples = 0
        self.zero_readings = deque(maxlen=self.zero_sample_count)
        self.recovering_silence = False

    def interrupt_silence(self, now):
        """Discard stability samples, preserving a recent arm or saved lock.

        Args:
            now: Monotonic time at the end of the failed query.

        Returns:
            bool: Whether the last valid reading permits bounded recovery.
        """
        if (self.maximum_silence_seconds <= 0 or self.last_sampled_at is None
                or not 0 <= now - self.last_sampled_at <= self.maximum_silence_seconds):
            self.reset()
            return False
        self.samples.clear()
        self.zero_samples = 0
        self.zero_readings.clear()
        if self.status != "WAITING_REMOVAL":
            self.candidate = None
            if self.status == "STABILIZING":
                self.status = "MEASURING"
        self.recovering_silence = True
        return True

    def observe(self, sample, now):
        """Produce a retryable candidate until acknowledged after persistence.

        Args:
            sample: Immutable net/tare/monotonic sample from an adapter.
            now: Monotonic time used only for technical age validation.

        Returns:
            CaptureCandidate | None: Stable capture with an unchanged retry key.

        Raises:
            ValueError: Invalid, duplicated, future or stale sample.
        """
        signed_removal = sample.protocol == "PROT_F"
        minimum_reading = -1_000_000 if signed_removal else -self.zero_grams
        if (type(sample.net_weight_grams) is not int or not minimum_reading <= sample.net_weight_grams <= 1_000_000
                or (sample.tare_grams is None and not signed_removal)
                or (sample.tare_grams is not None and (type(sample.tare_grams) is not int
                                                      or not 0 <= sample.tare_grams <= 1_000_000))
                or not math.isfinite(sample.sampled_at) or not math.isfinite(now)
                or not 0 <= now - sample.sampled_at <= self.maximum_age_seconds
                or (self.last_sampled_at is not None and sample.sampled_at <= self.last_sampled_at)):
            self.reset()
            raise ValueError("Leitura inválida ou antiga; aguarde retorno ao zero.")
        gap_limit = self.maximum_silence_seconds if self.recovering_silence else self.maximum_age_seconds
        if self.last_sampled_at is not None and (
                sample.sampled_at - self.last_sampled_at > gap_limit
                or (self.recovering_silence and now - self.last_sampled_at > gap_limit)):
            self.reset()
        self.recovering_silence = False
        self.last_sampled_at = sample.sampled_at
        zero = (sample.net_weight_grams <= self.zero_grams if signed_removal
                else abs(sample.net_weight_grams) <= self.zero_grams) and not sample.moving
        if self.status in ("WAITING_ZERO", "WAITING_REMOVAL"):
            if zero:
                self.zero_readings.append(sample.net_weight_grams)
                if signed_removal and max(self.zero_readings) - min(self.zero_readings) > self.tolerance_grams:
                    self.zero_readings.clear()
                    self.zero_readings.append(sample.net_weight_grams)
                    self.zero_samples = 0
            else:
                self.zero_readings.clear()
            self.zero_samples = self.zero_samples + 1 if zero else 0
            if self.zero_samples >= self.zero_sample_count:
                self.status = "MEASURING"
                self.samples.clear()
                self.candidate = None
                self.zero_samples = 0
                self.zero_readings.clear()
            return None
        if zero or sample.net_weight_grams < self.minimum_grams or sample.moving:
            self.samples.clear()
            self.candidate = None
            self.status = "MEASURING"
            return None
        self.status = "STABILIZING"
        self.samples.append(sample)
        weights = [reading.net_weight_grams for reading in self.samples]
        tares = [reading.tare_grams for reading in self.samples]
        if max(weights) - min(weights) > self.tolerance_grams or len(set(tares)) > 1:
            self.samples.clear()
            self.samples.append(sample)
            self.candidate = None
            return None
        if len(self.samples) < self.sample_count:
            return None
        if self.candidate is None:
            self.candidate = CaptureCandidate(uuid4(), sample.net_weight_grams, sample.tare_grams)
        elif abs(sample.net_weight_grams - self.candidate.net_weight_grams) > self.tolerance_grams:
            self.samples.clear()
            self.samples.append(sample)
            self.candidate = None
            return None
        return self.candidate

    def acknowledge(self):
        """Wait for removal only after a candidate was safely persisted."""
        if self.candidate is None:
            raise RuntimeError("Não há captura estável para confirmar.")
        self.status = "WAITING_REMOVAL"

    def parameters(self):
        """Return the provisional stability parameters for snapshots."""
        return {
            "sample_count": self.sample_count, "tolerance_grams": self.tolerance_grams,
            "zero_grams": self.zero_grams, "minimum_grams": self.minimum_grams,
            "zero_sample_count": self.zero_sample_count,
            "maximum_silence_seconds": self.maximum_silence_seconds,
            "maximum_age_seconds": self.maximum_age_seconds, "profile": self.profile,
        }
