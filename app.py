"""Streamlit application. Start with: uv run streamlit run app.py."""

import json
import os
from collections import Counter
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from demographics.build import build_native
from demographics.models import SimulationConfig
from demographics.service import benchmark_worker, native_status, run_worker
from demographics.storage import RunStore

st.set_page_config(page_title="Demographics Lab", page_icon="◉", layout="wide")
# Timelines can exceed 5,000 rows. Streamlit serves chart data through Arrow;
# disable Altair's inline-data guard without dropping observations from exports.
alt.data_transformers.disable_max_rows()


def navigate(page: str, parameters: dict[str, Any] | None = None) -> None:
    """Switch pages, optionally restoring a saved experiment's complete parameters."""
    st.session_state["page"] = page
    if parameters is not None:
        st.session_state["pending_parameters"] = parameters


def timeline_frame(result: dict[str, Any]) -> pd.DataFrame:
    """Bound chart payloads while leaving stored observations and exports untouched."""
    history = result["history"]
    stride = max(1, (len(history) + 1998) // 1999)
    indices = list(range(0, len(history), stride))
    if indices[-1] != len(history) - 1:
        indices.append(len(history) - 1)
    return pd.DataFrame([history[index] for index in indices])


def population_chart(result: dict[str, Any]) -> None:
    """Draw sex-specific population trajectories with a bounded browser payload."""
    frame = timeline_frame(result)
    long = frame[["year", "men", "women"]].melt(
        id_vars=["year"], value_vars=["men", "women"], var_name="group", value_name="population"
    )
    chart = (
        alt.Chart(long)
        .mark_area(opacity=0.8)
        .encode(
            x=alt.X("year:Q", title="Simulation year"),
            y=alt.Y("population:Q", title="Living population"),
            color=alt.Color(
                "group:N",
                title=None,
                scale=alt.Scale(domain=["men", "women"], range=["#2563eb", "#14b8a6"]),
            ),
            tooltip=["year:Q", "group:N", "population:Q"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)


def show_result(result: dict[str, Any], name: str) -> None:
    """Render one experiment with summaries, plots, individual records, and exports."""
    st.subheader(name)
    summary = result["summary"]
    if result["stop_reason"] != "completed":
        st.warning("Stopped early: " + result["stop_reason"].replace("_", " "))
    metrics = st.columns(4)
    metrics[0].metric(
        "Living population",
        f"{summary['population']:,}",
        f"{summary['population'] - summary['initial_population']:+,} people",
    )
    metrics[1].metric("Births / deaths", f"{summary['births']:,} / {summary['deaths']:,}")
    metrics[2].metric("Mean age", f"{summary['mean_age']:.1f} years")
    metrics[3].metric("Engine runtime", f"{result['duration_seconds']:.3f} s")
    st.caption(
        f"{summary['years_simulated']:g} years simulated · {result['engine'].upper()} engine"
        f" · seed {result['parameters']['seed']} · {summary['families']:,} living families"
    )

    overview, people, parameters = st.tabs(
        ["Population trends", "Population explorer", "Parameters & export"]
    )
    with overview:
        st.caption(
            "Charts show up to 2,000 sampled observations per run; downloads retain every step."
        )
        population_chart(result)
        left, right = st.columns(2)
        with left:
            st.markdown("#### Age distribution")
            if result["people"]:
                buckets = Counter(int(person["age"] // 5) * 5 for person in result["people"])
                age_data = pd.DataFrame(
                    [
                        {"age_from": age, "age_to": age + 5, "people": count}
                        for age, count in sorted(buckets.items())
                    ]
                )
                age_chart = (
                    alt.Chart(age_data)
                    .mark_bar(color="#2563eb", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                    .encode(
                        x=alt.X(
                            "age_from:Q", bin=alt.Bin(binned=True, step=5), title="Age (years)"
                        ),
                        x2="age_to:Q",
                        y=alt.Y("people:Q", title="People"),
                        tooltip=["age_from:Q", "age_to:Q", "people:Q"],
                    )
                )
                st.altair_chart(age_chart.properties(height=220), use_container_width=True)
            else:
                st.info("No living residents remain.")
        with right:
            st.markdown("#### Births & deaths over time")
            events = timeline_frame(result).melt(
                id_vars=["year"],
                value_vars=["births", "deaths"],
                var_name="event",
                value_name="count",
            )
            chart = (
                alt.Chart(events)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("year:Q", title="Simulation year"),
                    y=alt.Y("count:Q", title="Cumulative events"),
                    color=alt.Color("event:N", scale=alt.Scale(range=["#14b8a6", "#f97316"])),
                    tooltip=["year:Q", "event:N", "count:Q"],
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)
    with people:
        st.caption(
            "Final living population. Parent IDs may refer to deceased people, "
            "who are not in this snapshot."
        )
        if result["people"]:
            frame = pd.DataFrame(result["people"])
            search = st.text_input("Search by person or family", key="people_search")
            if search:
                frame = frame[frame["name"].str.contains(search, case=False, regex=False)]
            st.dataframe(frame, hide_index=True, use_container_width=True)
        else:
            st.info("This population is extinct.")
    with parameters:
        st.json(result["parameters"])
        json_col, csv_col, config_col = st.columns(3)
        json_col.download_button(
            "Download full run (JSON)",
            json.dumps(result, indent=2),
            "simulation.json",
            "application/json",
        )
        csv_col.download_button(
            "Download timeline (CSV)",
            pd.DataFrame(result["history"]).to_csv(index=False),
            "timeline.csv",
            "text/csv",
        )
        config_col.download_button(
            "Download parameters",
            json.dumps(result["parameters"], indent=2),
            "parameters.json",
            "application/json",
        )


def overview_page(store: RunStore) -> None:
    """Show the latest saved experiment or a useful first-run welcome."""
    runs = store.list_runs()
    if not runs:
        st.subheader("Your next population story starts here.")
        st.write(
            "Build a population, adjust its demographic assumptions, and watch generations unfold."
        )
        first, second, third = st.columns(3)
        first.info(
            "**01 · Configure**\n\nSet population size, fertility, mortality, "
            "and a reproducible seed."
        )
        second.info(
            "**02 · Simulate**\n\nUse Python immediately, or compile the typed engine to native C."
        )
        third.info(
            "**03 · Explore**\n\nInspect trends and residents. "
            "Every successful experiment is saved."
        )
        st.button("Create simulation", type="primary", on_click=navigate, args=("New simulation",))
        return
    st.caption(f"{len(runs)} saved experiments · showing your latest run")
    latest = runs[0]
    show_result(store.load(latest["id"]), latest["name"])


def number(
    label: str, field: str, minimum: int | float, maximum: int | float, step: int | float
) -> Any:
    """Bind a numeric control to its persisted parameter key."""
    return st.number_input(
        label, min_value=minimum, max_value=maximum, step=step, key=f"param_{field}"
    )


def new_simulation_page(store: RunStore) -> None:
    """Collect all model parameters and save only successfully completed worker results."""
    st.subheader("Design an experiment")
    st.caption(
        "A closed population: no migration. Each run has its own clock and random generator."
    )
    with st.form("simulation_form"):
        name = st.text_input("Experiment name", value="Population experiment", max_chars=120)
        left, right = st.columns(2)
        with left:
            st.markdown("#### Population & timeline")
            years = number("Years to simulate", "years", 1, 500, 1)
            men = number("Initial men", "initial_men", 0, 40_000, 1)
            women = number("Initial women", "initial_women", 0, 40_000, 1)
            max_age = number("Maximum initial age (years)", "initial_max_age", 0.0, 100.0, 1.0)
            step = number("Time step (days)", "step_days", 1, 365, 1)
            limit = number("Population limit", "max_population", 1, 100_000, 100)
            seed = number("Random seed", "seed", 0, 2**32 - 1, 1)
            backend = st.selectbox(
                "Execution engine",
                ["auto", "python", "native"],
                help="Auto selects native if compiled, otherwise Python.",
            )
        with right:
            st.markdown("#### Fertility & survival")
            lifespan = number("Mean sampled lifespan (years)", "life_expectancy", 1.0, 120.0, 1.0)
            stddev = number("Lifespan standard deviation", "lifespan_stddev", 0.0, 40.0, 1.0)
            fertility = number(
                "Annual conception probability", "annual_conception_probability", 0.0, 1.0, 0.01
            )
            min_age = number("Minimum fertility age", "fertility_min_age", 18.0, 70.0, 1.0)
            end_age = number("Maximum fertility age", "fertility_max_age", 18.0, 70.0, 1.0)
            gestation = number("Gestation (days)", "gestation_days", 1, 730, 1)
            maternal = number(
                "Maternal death probability per birth", "maternal_mortality", 0.0, 1.0, 0.001
            )
            infant = number(
                "Infant death probability per birth", "infant_mortality", 0.0, 1.0, 0.01
            )
        st.caption(
            "Smaller time steps improve event timing but take longer. "
            "Births occur at step boundaries."
        )
        submitted = st.form_submit_button("Run simulation", type="primary")
    if submitted:
        try:
            config = SimulationConfig(
                years=years,
                initial_men=men,
                initial_women=women,
                initial_max_age=max_age,
                life_expectancy=lifespan,
                lifespan_stddev=stddev,
                annual_conception_probability=fertility,
                fertility_min_age=min_age,
                fertility_max_age=end_age,
                gestation_days=gestation,
                maternal_mortality=maternal,
                infant_mortality=infant,
                step_days=step,
                max_population=limit,
                seed=seed,
            )
            with st.spinner("Simulating in an isolated worker…"):
                result = run_worker(config, backend)
                identifier = store.save(name, result)
            st.session_state["latest_run_id"] = identifier
            st.success("Simulation complete and saved to run history.")
        except (ValueError, RuntimeError, OSError) as error:
            st.error(str(error))
    if "latest_run_id" in st.session_state:
        show_result(store.load(st.session_state["latest_run_id"]), "Latest experiment")


def history_page(store: RunStore) -> None:
    """Browse persisted experiments, compare trajectories, and reuse exact inputs."""
    st.subheader("Experiment archive")
    runs = store.list_runs()
    if not runs:
        st.info("No saved simulations yet. Start with New simulation.")
        return
    search = st.text_input("Filter experiments")
    filtered = [run for run in runs if search.lower() in run["name"].lower()]
    if not filtered:
        st.info("No matching experiments.")
        return
    lookup = {run["id"]: run for run in filtered}

    def label(identifier: str) -> str:
        run = lookup[identifier]
        return f"{run['name']} · {run['created_at']} · {identifier[:6]}"

    selected = st.selectbox("Open saved simulation", list(lookup), format_func=label)
    if selected is None:
        return
    record = lookup[selected]
    st.button(
        "Reuse these parameters", on_click=navigate, args=("New simulation", record["parameters"])
    )
    with st.expander("Compare experiments"):
        compare_ids = st.multiselect(
            "Experiments to compare", list(lookup), format_func=label, max_selections=6
        )
        if compare_ids:
            frames = []
            comparisons = []
            for identifier in compare_ids:
                run = lookup[identifier]
                result = store.load(identifier)
                title = f"{run['name']} ({identifier[:6]})"
                frames.append(
                    timeline_frame(result)[["year", "population"]].assign(experiment=title)
                )
                comparisons.append(
                    {
                        "experiment": title,
                        **run["parameters"],
                        **run["summary"],
                        "engine": run["engine"],
                        "runtime_s": run["duration"],
                    }
                )
            chart = (
                alt.Chart(pd.concat(frames))
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("year:Q", title="Simulation year"),
                    y=alt.Y("population:Q", title="Population"),
                    color="experiment:N",
                    tooltip=["experiment:N", "year:Q", "population:Q"],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(pd.DataFrame(comparisons), hide_index=True)
    show_result(store.load(selected), record["name"])


def native_page() -> None:
    """Expose real compilation, diagnostic logs, parity checks, and measured speedup."""
    st.subheader("Native engine workshop")
    st.write(
        "mypy checks the types. mypyc translates the simulation kernel into C and builds a "
        "CPython extension. The dashboard itself stays in Python."
    )
    status = native_status()
    if status["native"]:
        st.success("Native extension is available to simulation workers.")
    else:
        st.info("Python engine is ready. Build the optional extension to enable native execution.")
    if status.get("error"):
        st.error(status["error"])
    st.caption(
        "Requires uv sync (including dev tools), a C compiler, and Python development headers."
    )
    allow_build = os.environ.get("DEMOGRAPHICS_ALLOW_BUILD", "1") == "1"
    if not allow_build:
        st.warning("Compilation is disabled by the administrator on this deployment.")
    build_col, test_col = st.columns(2)
    if build_col.button("Compile & verify native engine", type="primary", disabled=not allow_build):
        try:
            with st.spinner(
                "Type-checking, compiling C, and comparing native results with Python…"
            ):
                st.session_state["build_log"] = build_native()
            st.success("Native compilation and Python/native parity verification passed.")
        except (RuntimeError, OSError) as error:
            st.session_state["build_log"] = str(error)
            st.error(
                "Native build failed. Python remains available; inspect the diagnostics below."
            )
    if test_col.button("Run parity test & benchmark"):
        try:
            with st.spinner("Running identical seeded Python and native simulations, three times…"):
                st.session_state["benchmark_report"] = benchmark_worker()
        except (RuntimeError, OSError) as error:
            st.error(str(error))
    if "benchmark_report" in st.session_state:
        report = st.session_state["benchmark_report"]
        st.success("Exact parity passed: all timeline values and final residents match.")
        left, middle, right = st.columns(3)
        left.metric("Python (median)", f"{report['python_seconds']:.3f} s")
        middle.metric("Native (median)", f"{report['native_seconds']:.3f} s")
        right.metric("Measured speedup", f"{report['speedup']:.2f}×")
        st.caption(
            "50 years · 1,500 founders · 30-day steps · 3 repetitions. "
            "Timings cover simulation only; speedup depends on workload and hardware."
        )
    if "build_log" in st.session_state:
        with st.expander("Compiler & verification diagnostics", expanded=True):
            st.code(st.session_state["build_log"], language="text")


def main() -> None:
    """Initialize controls, connect local storage, and render the selected page."""
    st.markdown(
        """<style>
    .block-container {padding-top: 2rem; max-width: 1400px;}
    [data-testid="stMetric"] {background: white; border: 1px solid #dce4ef;
      border-radius: 12px; padding: 16px;}
    h1 {letter-spacing: -1.5px;} h2, h3 {letter-spacing: -.5px;}
    [data-testid="stSidebar"] {border-right: 1px solid #dce4ef;}
    </style>""",
        unsafe_allow_html=True,
    )
    pending = st.session_state.pop("pending_parameters", {})
    for field, default in SimulationConfig().to_dict().items():
        key = f"param_{field}"
        if field in pending:
            st.session_state[key] = pending[field]
        elif key not in st.session_state:
            st.session_state[key] = default
    with st.sidebar:
        st.title("◉ Demographics")
        st.caption("THE POPULATION LAB")
        page = st.radio(
            "Workspace", ["Overview", "New simulation", "Run history", "Native engine"], key="page"
        )
        st.divider()
        st.markdown("**Reproducible by design**")
        st.caption("Seeded experiments. Persistent history. Python clarity, optional native speed.")
        st.caption("Local, trusted-user workspace. No authentication is provided.")
    st.title("Demographics Lab")
    st.markdown("Explore how populations change, **one generation at a time.**")
    st.caption("EXPERIMENT • OBSERVE • COMPARE")
    st.divider()
    try:
        store = RunStore()
        if page == "Overview":
            overview_page(store)
        elif page == "New simulation":
            new_simulation_page(store)
        elif page == "Run history":
            history_page(store)
        else:
            native_page()
    except (OSError, KeyError) as error:
        st.error(f"Unable to open local simulation data: {error}")
    st.divider()
    st.caption(
        "Illustrative model, not a demographic forecast. Assumptions and timing approximations "
        "are documented in README.md."
    )


if __name__ == "__main__":
    main()
