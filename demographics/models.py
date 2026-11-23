"""Validated, serializable simulation parameters."""

import math
from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True)
class SimulationConfig:
    """Parameters for the illustrative (not predictive) demographic model."""

    years: int = 100
    initial_men: int = 95
    initial_women: int = 132
    initial_max_age: float = 60.0
    life_expectancy: float = 78.0
    lifespan_stddev: float = 12.0
    annual_conception_probability: float = 0.18
    fertility_min_age: float = 18.0
    fertility_max_age: float = 45.0
    gestation_days: int = 270
    maternal_mortality: float = 0.001
    infant_mortality: float = 0.01
    step_days: int = 30
    max_population: int = 40_000
    seed: int = 42

    def __post_init__(self) -> None:
        """Reject invalid values before allocating population or starting a worker."""
        integer_bounds = {
            "years": (1, 500),
            "initial_men": (0, 40_000),
            "initial_women": (0, 40_000),
            "gestation_days": (1, 730),
            "step_days": (1, 365),
            "max_population": (1, 100_000),
            "seed": (0, 2**32 - 1),
        }
        for name, (low, high) in integer_bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer between {low} and {high}.")
        float_bounds = {
            "initial_max_age": (0.0, 100.0),
            "life_expectancy": (1.0, 120.0),
            "lifespan_stddev": (0.0, 40.0),
            "annual_conception_probability": (0.0, 1.0),
            "fertility_min_age": (18.0, 70.0),
            "fertility_max_age": (18.0, 70.0),
            "maternal_mortality": (0.0, 1.0),
            "infant_mortality": (0.0, 1.0),
        }
        for name, (float_low, float_high) in float_bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not float_low <= value <= float_high
            ):
                raise ValueError(
                    f"{name} must be a finite number between {float_low} and {float_high}."
                )
        if self.fertility_min_age >= self.fertility_max_age:
            raise ValueError("Minimum fertility age must be below maximum fertility age.")
        if not 1 <= self.initial_men + self.initial_women <= self.max_population:
            raise ValueError("Initial population must be between 1 and the population limit.")

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible parameters."""
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "SimulationConfig":
        """Reject misspelled fields rather than silently ignoring them."""
        unknown = values.keys() - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}")
        return cls(**values)
