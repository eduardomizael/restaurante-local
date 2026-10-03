from apps.measurements.models import Measurement


def available_measurements():
    """Return all available captures without expiration or order filtering."""
    return Measurement.objects.filter(status=Measurement.Status.AVAILABLE)
