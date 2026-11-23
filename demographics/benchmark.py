"""Verify exact Python/native parity and measure the same seeded workload."""

import argparse
import json
import statistics
from typing import Any

from demographics.engine import run_simulation
from demographics.models import SimulationConfig


def comparable(result: dict[str, Any]) -> dict[str, Any]:
    """Remove runtime metadata, retaining every simulated value for parity checks."""
    return {
        key: value for key, value in result.items() if key not in ("engine", "duration_seconds")
    }


def benchmark(repeats: int = 3) -> dict[str, Any]:
    """Compare real native and Python engines; fail rather than silently fall back."""
    config = SimulationConfig(years=50, initial_men=750, initial_women=750, seed=2026)
    python_times: list[float] = []
    native_times: list[float] = []
    population = 0
    for _ in range(repeats):
        pure = run_simulation(config, "python")
        native = run_simulation(config, "native")
        if comparable(pure) != comparable(native):
            raise RuntimeError("Python/native simulation results differ.")
        python_times.append(pure["duration_seconds"])
        native_times.append(native["duration_seconds"])
        population = native["summary"]["population"]
    python_median = statistics.median(python_times)
    native_median = statistics.median(native_times)
    return {
        "parity": True,
        "repeats": repeats,
        "parameters": config.to_dict(),
        "python_seconds": python_median,
        "native_seconds": native_median,
        "speedup": python_median / native_median,
        "final_population": population,
    }


def main() -> None:
    """Print a machine-readable report for the dashboard and CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()
    report = benchmark()
    text = json.dumps(report, indent=2)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
