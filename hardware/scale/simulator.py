"""Deterministic readings for the simulated commercial capture cycle."""

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class ScaleSample:
    net_weight_grams: int
    tare_grams: int
    sampled_at: float
    moving: bool = False


class SimulatedScale:
    """Repeat zero, variation, stable weight and removal without serial I/O."""

    weights = (0, 0, 0, 180, 245, 252, 252, 252, 252, 252, 0, 0,
               290, 300, 300, 300, 300, 300, 0, 0, 390, 400, 400, 400, 400, 400, 0, 0)

    def __init__(self, weights=None):
        self.index = 0
        self.closed = False
        if weights is not None:
            self.weights = tuple(weights)
        if not self.weights:
            raise ValueError("Simulador exige uma sequência de leituras.")

    def read(self):
        """Return the next simulated sample."""
        if self.closed:
            raise RuntimeError("Simulador fechado.")
        weight = self.weights[self.index % len(self.weights)]
        self.index += 1
        if weight is None:
            raise OSError("Desconexão simulada.")
        return ScaleSample(weight, 0, monotonic())

    def close(self):
        """Release the simulator."""
        self.closed = True
