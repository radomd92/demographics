"""Exercise real Streamlit controls, storage, subprocesses, and optional compilation."""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from demographics.build import ROOT
from demographics.engine import run_simulation
from demographics.models import SimulationConfig
from demographics.storage import RunStore


def test_simulation_history_and_parameter_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("DEMOGRAPHICS_DB", str(database))
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert not app.exception
    app.button[0].click().run()
    assert app.radio[0].value == "New simulation"
    app.number_input(key="param_years").set_value(2)
    app.selectbox[0].set_value("python")
    app.text_input[0].set_value("UI experiment")
    app.button[0].click().run()
    assert not app.exception
    assert app.success
    assert len(RunStore(database).list_runs()) == 1
    assert app.metric[0].label == "Living population"

    app.radio[0].set_value("Run history").run()
    assert not app.exception
    assert "UI experiment" in str(app.selectbox[0].options)
    app.multiselect[0].select(RunStore(database).list_runs()[0]["id"]).run()
    assert not app.exception
    app.button[0].click().run()
    assert app.radio[0].value == "New simulation"
    assert app.number_input(key="param_years").value == 2
    assert not app.exception
    # History must survive a completely new browser session.
    fresh = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert fresh.metric[0].label == "Living population"
    assert not fresh.exception


def test_ui_validation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMOGRAPHICS_DB", str(tmp_path / "invalid.sqlite3"))
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    app.radio[0].set_value("New simulation").run()
    app.number_input(key="param_initial_men").set_value(0)
    app.number_input(key="param_initial_women").set_value(0)
    app.button[0].click().run()
    assert app.error
    assert not app.exception
    assert RunStore(tmp_path / "invalid.sqlite3").list_runs() == []


def test_disabled_compilation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMOGRAPHICS_DB", str(tmp_path / "disabled.sqlite3"))
    monkeypatch.setenv("DEMOGRAPHICS_ALLOW_BUILD", "0")
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    app.radio[0].set_value("Native engine").run()
    assert app.button[0].disabled
    assert not app.exception


@pytest.mark.parametrize("extinct", [False, True])
def test_long_timeline_and_empty_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extinct: bool
) -> None:
    database = tmp_path / "edge.sqlite3"
    monkeypatch.setenv("DEMOGRAPHICS_DB", str(database))
    result = run_simulation(
        SimulationConfig(
            years=20,
            step_days=1,
            initial_men=1,
            initial_women=0,
            initial_max_age=0.0,
            life_expectancy=1.0 if extinct else 120.0,
            lifespan_stddev=0.0,
        ),
        "python",
    )
    RunStore(database).save("Chart edge case", result)
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert not app.exception
    if extinct:
        assert app.warning
    else:
        assert len(result["history"]) > 5000


@pytest.mark.skipif(
    os.environ.get("DEMOGRAPHICS_TEST_NATIVE") != "1",
    reason="Set DEMOGRAPHICS_TEST_NATIVE=1 to compile from the real UI",
)
def test_real_compilation_and_benchmark_in_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No mocks: click the build button, compile C, check parity, then benchmark."""
    monkeypatch.setenv("DEMOGRAPHICS_DB", str(tmp_path / "native.sqlite3"))
    monkeypatch.setenv("DEMOGRAPHICS_ALLOW_BUILD", "1")
    app = AppTest.from_file(ROOT / "app.py", default_timeout=300).run()
    app.radio[0].set_value("Native engine").run()
    app.button[0].click().run(timeout=300)
    assert not app.exception
    assert not app.error
    assert any("compilation and Python/native parity" in message.value for message in app.success)
    assert "parity" in app.code[0].value
    app.button[1].click().run(timeout=180)
    assert not app.exception
    assert not app.error
    assert app.metric[2].label == "Measured speedup"
    assert app.session_state["benchmark_report"]["parity"] is True
    # The new extension must be picked up without restarting the Streamlit session.
    app.radio[0].set_value("New simulation").run()
    app.number_input(key="param_years").set_value(2)
    app.selectbox[0].set_value("native")
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert not app.error
    saved = RunStore(tmp_path / "native.sqlite3").list_runs()
    assert len(saved) == 1
    assert saved[0]["engine"] == "native"
