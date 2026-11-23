"""Local persistence and worker boundaries."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from demographics.build import ROOT
from demographics.engine import run_simulation
from demographics.models import SimulationConfig
from demographics.service import run_worker
from demographics.storage import RunStore


def test_save_load_and_reopen(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "nested" / "runs.sqlite3")
    result = run_simulation(SimulationConfig(years=1), "python")
    identifier = store.save("  Test run  ", result)
    reopened = RunStore(store.path)
    assert reopened.load(identifier) == result
    assert reopened.list_runs()[0]["name"] == "Test run"
    assert reopened.list_runs()[0]["parameters"] == result["parameters"]
    assert "people" not in reopened.list_runs()[0]
    with pytest.raises(KeyError):
        reopened.load("' OR 1=1 --")


def test_concurrent_writes(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    result = run_simulation(SimulationConfig(years=1), "python")
    with ThreadPoolExecutor(max_workers=4) as pool:
        identifiers = list(pool.map(lambda index: store.save(str(index), result), range(8)))
    assert len(set(identifiers)) == 8
    assert len(store.list_runs()) == 8


def test_actual_worker() -> None:
    config = SimulationConfig(years=1, initial_men=4, initial_women=4)
    result = run_worker(config, "python")
    assert result["parameters"] == config.to_dict()
    assert result["engine"] == "python"
    assert result["summary"]["years_simulated"] == 1


def test_cli_export(tmp_path: Path) -> None:
    output = tmp_path / "run.json"
    completed = subprocess.run(
        [sys.executable, "main.py", "1", "--backend", "python", "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text())["parameters"]["years"] == 1
