"""Select an engine and convert its native-friendly objects to portable JSON."""

import importlib
import importlib.machinery
import importlib.util
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from demographics.models import SimulationConfig

BACKENDS = ("auto", "python", "native")


def load_kernel(backend: str = "auto") -> Any:
    """Load the extension when available, or explicitly load the original Python source."""
    if backend not in BACKENDS:
        raise ValueError(f"Backend must be one of {BACKENDS}.")
    if backend == "python":
        name = "demographics._python_kernel"
        if name not in sys.modules:
            path = Path(__file__).with_name("kernel.py")
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Unable to load the Python engine.")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        return sys.modules[name]
    module = importlib.import_module("demographics.kernel")
    if backend == "native" and not is_native(module):
        raise RuntimeError("Native engine is not built. Run: uv run python -m demographics.build")
    return module


def is_native(module: Any) -> bool:
    """Inspect the actual loaded binary, not merely the presence of build files."""
    return any(str(module.__file__).endswith(s) for s in importlib.machinery.EXTENSION_SUFFIXES)


def run_simulation(config: SimulationConfig, backend: str = "auto") -> dict[str, Any]:
    """Run an independent experiment and return JSON-safe observations and people."""
    kernel = load_kernel(backend)
    start = time.perf_counter()
    history, people, reason = kernel.simulate(config)
    elapsed = time.perf_counter() - start
    final = history[-1]
    population = final.men + final.women
    rows = [
        {
            "day": round(row.day, 2),
            "year": round(row.day / 365.25, 4),
            "population": row.men + row.women,
            "men": row.men,
            "women": row.women,
            "births": row.births,
            "deaths": row.deaths,
            "mean_age": round(row.mean_age, 2),
        }
        for row in history
    ]
    residents = [
        {
            "id": p.identifier,
            "name": f"Family {p.family} · Person {p.identifier}",
            "sex": "Female" if p.female else "Male",
            "age": round((final.day - p.birth_day) / 365.25, 2),
            "birth_year": round(p.birth_day / 365.25, 2),
            "family": p.family,
            "mother_id": p.mother_id or None,
            "father_id": p.father_id or None,
            "children": p.children,
            "pregnant": p.due_day >= 0.0,
        }
        for p in people
    ]
    families = Counter(p.family for p in people)
    return {
        "schema_version": 1,
        "parameters": config.to_dict(),
        "engine": "native" if is_native(kernel) else "python",
        "duration_seconds": elapsed,
        "stop_reason": reason,
        "summary": {
            "initial_population": config.initial_men + config.initial_women,
            "population": population,
            "births": final.births,
            "deaths": final.deaths,
            "years_simulated": round(final.day / 365.25, 4),
            "mean_age": round(final.mean_age, 2),
            "families": len(families),
        },
        "history": rows,
        "people": residents,
        "families": [
            {"family": family, "population": count} for family, count in families.most_common()
        ],
    }
