"""Deterministic live readings; does not create commercial measurements."""

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class ScaleSample:
    net_weight_grams: int
    tare_grams: int
    sampled_at: float


class SimulatedScale:
    """Repeat zero, variation, stable weight and removal without serial I/O."""

    weights = (0, 0, 0, 180, 245, 252, 252, 252, 252, 252, 0, 0)

    def __init__(self):
        self.index = 0
        self.closed = False

    def read(self):
        """Return the next simulated sample."""
        if self.closed:
            raise RuntimeError("Simulador fechado.")
        weight = self.weights[self.index % len(self.weights)]
        self.index += 1
        return ScaleSample(weight, 0, monotonic())

    def close(self):
        """Release the simulator."""
        self.closed = True
