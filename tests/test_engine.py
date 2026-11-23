"""Simulation invariants and deterministic edge cases."""

import json
from typing import Any

import pytest

from demographics.benchmark import comparable
from demographics.engine import is_native, load_kernel, run_simulation
from demographics.models import SimulationConfig


@pytest.mark.parametrize("seed", [0, 42, 2026])
def test_reproducible_and_conserved(seed: int) -> None:
    config = SimulationConfig(years=60, seed=seed)
    first = run_simulation(config, "python")
    second = run_simulation(config, "python")
    assert comparable(first) == comparable(second)
    initial = config.initial_men + config.initial_women
    for row in first["history"]:
        assert row["population"] == initial + row["births"] - row["deaths"]
        assert row["population"] == row["men"] + row["women"]
        assert 0 <= row["population"] <= config.max_population
    assert len(first["people"]) == first["summary"]["population"]
    assert len({person["id"] for person in first["people"]}) == len(first["people"])
    assert all(person["age"] >= 0 for person in first["people"])
    assert first["history"][-1]["year"] == 60
    json.dumps(first, allow_nan=False)


@pytest.mark.parametrize("men,women", [(0, 20), (20, 0)])
def test_single_sex_population(men: int, women: int) -> None:
    result = run_simulation(
        SimulationConfig(years=10, initial_men=men, initial_women=women), "python"
    )
    assert result["summary"]["births"] == 0


def test_extinction_does_not_crash() -> None:
    config = SimulationConfig(
        years=10,
        initial_men=1,
        initial_women=0,
        initial_max_age=0.0,
        life_expectancy=1.0,
        lifespan_stddev=0.0,
    )
    result = run_simulation(config, "python")
    assert result["stop_reason"] == "extinct"
    assert result["summary"]["population"] == 0
    assert result["people"] == []


def test_hard_population_limit() -> None:
    config = SimulationConfig(
        years=10,
        max_population=230,
        initial_max_age=30.0,
        annual_conception_probability=1.0,
        infant_mortality=0.0,
        maternal_mortality=0.0,
        life_expectancy=120.0,
        lifespan_stddev=0.0,
    )
    result = run_simulation(config, "python")
    assert result["stop_reason"] == "population_limit"
    assert result["summary"]["population"] == 230
    assert result["summary"]["births"] == 3


def test_newborns_are_born_at_delivery_and_parents_are_distinct() -> None:
    config = SimulationConfig(
        years=5,
        initial_max_age=30.0,
        annual_conception_probability=1.0,
        infant_mortality=0.0,
        maternal_mortality=0.0,
        life_expectancy=120.0,
        lifespan_stddev=0.0,
    )
    result = run_simulation(config, "python")
    babies = [person for person in result["people"] if person["mother_id"] is not None]
    assert babies
    by_id = {person["id"]: person for person in result["people"]}
    for baby in babies:
        assert baby["age"] < config.years
        assert baby["birth_year"] >= config.gestation_days / 365.25
        assert by_id[baby["mother_id"]]["sex"] == "Female"
        assert by_id[baby["father_id"]]["sex"] == "Male"
        assert baby["mother_id"] != baby["father_id"]
    assert sum(person["children"] for person in result["people"]) == 2 * len(babies)


def test_maternal_and_infant_deaths_counted() -> None:
    config = SimulationConfig(
        years=5,
        initial_max_age=30.0,
        annual_conception_probability=1.0,
        infant_mortality=1.0,
        maternal_mortality=1.0,
        life_expectancy=120.0,
        lifespan_stddev=0.0,
    )
    result = run_simulation(config, "python")
    assert result["summary"]["births"] > 0
    assert result["summary"]["deaths"] == 2 * result["summary"]["births"]
    assert result["summary"]["population"] == 227 - result["summary"]["births"]


@pytest.mark.parametrize(
    "values",
    [
        {"years": 0},
        {"years": True},
        {"step_days": 0},
        {"initial_men": -1},
        {"initial_women": 0, "initial_men": 0},
        {"max_population": 10},
        {"annual_conception_probability": 1.01},
        {"maternal_mortality": float("nan")},
        {"lifespan_stddev": float("inf")},
        {"fertility_min_age": 17.0},
        {"fertility_min_age": 45.0},
        {"unknown_parameter": 10},
        {"seed": 1.5},
    ],
)
def test_parameter_validation(values: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        SimulationConfig.from_dict(values)


def test_native_parity_if_built() -> None:
    if not is_native(load_kernel()):
        pytest.skip("Optional native extension not built")
    for config in [
        SimulationConfig(years=30),
        SimulationConfig(years=2, initial_men=0),
        SimulationConfig(years=3, initial_max_age=0.0, life_expectancy=1.0, lifespan_stddev=0.0),
        SimulationConfig(years=10, max_population=230, annual_conception_probability=1.0),
    ]:
        assert comparable(run_simulation(config, "python")) == comparable(
            run_simulation(config, "native")
        )


def test_invalid_backend() -> None:
    with pytest.raises(ValueError, match="Backend"):
        load_kernel("not-an-engine")
