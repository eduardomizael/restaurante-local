"""Bridge the pure cycle to short domain transactions on the worker connection."""

from time import monotonic

from hardware.scale.cycle import CaptureCycle
from apps.measurements.services import capture_measurement
from apps.products.selectors import scale_product


class ScaleCaptureController:
    """Rearm after any catalogue revision, never carrying ORM objects in state."""

    def __init__(self, cycle=None):
        self.cycle = cycle or CaptureCycle()
        self.configuration = None
        self.status = "WAITING_ZERO"

    def reset(self):
        """Require observed zero after pause or physical failure."""
        self.cycle.reset()
        self.status = "WAITING_ZERO"

    def observe(self, sample):
        """Capture only with valid current commercial configuration.

        Args:
            sample: Fresh reading supplied by the worker.

        Returns:
            str: Physical or configuration status for presentation.
        """
        product = scale_product()
        configuration = (product.pk, product.revision) if product else None
        if configuration != self.configuration:
            self.reset()
            self.configuration = configuration
        if product is None:
            self.reset()
            self.status = "CONFIG_REQUIRED"
            return self.status
        candidate = self.cycle.observe(sample, monotonic())
        if candidate:
            capture_measurement(
                capture_key=candidate.capture_key, net_weight_grams=candidate.net_weight_grams,
                tare_grams=candidate.tare_grams, device=sample.device,
                stability_parameters=self.cycle.parameters(),
                expected_product_id=product.pk, expected_product_revision=product.revision,
            )
            self.cycle.acknowledge()
        self.status = self.cycle.status
        return self.status
