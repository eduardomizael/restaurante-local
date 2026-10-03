"""Transport-independent scale sample with technical timestamp only."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleSample:
    net_weight_grams: int
    tare_grams: int
    sampled_at: float
    moving: bool = False
    device: str = "SIMULATOR"
