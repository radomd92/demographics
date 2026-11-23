"""UI subprocess boundaries keep compilation and simulations out of Streamlit imports."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from demographics.build import ROOT
from demographics.models import SimulationConfig


def run_worker(config: SimulationConfig, backend: str) -> dict[str, Any]:
    """Use a fresh interpreter so a newly built extension needs no server restart."""
    with TemporaryDirectory(prefix="demographics-") as directory:
        config_path = Path(directory) / "parameters.json"
        result_path = Path(directory) / "result.json"
        config_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "demographics.cli",
                    "--config",
                    str(config_path),
                    "--backend",
                    backend,
                    "--output",
                    str(result_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "Simulation exceeded the 10-minute UI limit. Try a larger step."
            ) from error
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout)[-8000:])
        result: dict[str, Any] = json.loads(result_path.read_text())
        return result


def native_status() -> dict[str, Any]:
    """Probe native availability without caching an extension in the UI process."""
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "demographics.build", "--status"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode:
            return {"native": False, "error": completed.stderr[-2000:]}
        result: dict[str, Any] = json.loads(completed.stdout)
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"native": False, "error": str(error)}


def benchmark_worker() -> dict[str, Any]:
    """Run the exact-parity benchmark without importing native code into Streamlit."""
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "demographics.benchmark"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Benchmark exceeded the 3-minute limit.") from error
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout)[-8000:])
    result: dict[str, Any] = json.loads(completed.stdout)
    return result
