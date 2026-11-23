"""CLI entry points shared by the dashboard and shell."""

import argparse
import json
from pathlib import Path

from demographics.engine import BACKENDS, run_simulation
from demographics.models import SimulationConfig
from demographics.storage import RunStore


def main() -> None:
    """Run a simulation, export JSON, and optionally save it to local history."""
    parser = argparse.ArgumentParser(description="Demographics Lab population simulator")
    parser.add_argument("years", nargs="?", type=int, help="Years to simulate (default: 100)")
    parser.add_argument("--config", type=Path, help="JSON parameter file")
    parser.add_argument("--backend", choices=BACKENDS, default="auto")
    parser.add_argument("--output", type=Path, help="Export the complete JSON result")
    parser.add_argument("--save", action="store_true", help="Save to dashboard history")
    parser.add_argument("--name", default="CLI simulation")
    args = parser.parse_args()
    try:
        values = json.loads(args.config.read_text()) if args.config else {}
        if not isinstance(values, dict):
            raise ValueError("Configuration must be a JSON object.")
        if args.years is not None:
            values["years"] = args.years
        result = run_simulation(SimulationConfig.from_dict(values), args.backend)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
        if args.save:
            print(f"Saved run: {RunStore().save(args.name, result)}")
        print(
            json.dumps(
                {
                    "engine": result["engine"],
                    "summary": result["summary"],
                    "duration_seconds": result["duration_seconds"],
                },
                indent=2,
            )
        )
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
