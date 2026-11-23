# ◉ Demographics Lab

**A small population sandbox with a proper workspace.** Design seeded experiments,
explore generations in Streamlit, compare saved runs, and optionally compile the
typed simulation engine to a native CPython extension with mypyc.

> An illustrative agent-based model, **not** a scientific demographic forecast.

## Start here

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
uv sync --locked
uv run streamlit run app.py --server.address 127.0.0.1
```

Open **http://localhost:8501**. uv uses the Python 3.12 pin in `.python-version`
and installs the development tools by default. Python 3.11–3.13 are supported.
`pyproject.toml` is the dependency source of truth; commit `uv.lock` whenever
dependencies change. No separate pip requirements file is needed.

### Your workspace

| Page | What it does |
| --- | --- |
| **Overview** | Latest saved run, population trends, age histogram, births and deaths |
| **New simulation** | All parameters, seed, Python/native selection, automatic saving |
| **Run history** | Search experiments, reopen results, reuse parameters, compare up to six runs |
| **Native engine** | Actually compile C, inspect diagnostics, check exact parity, measure speedup |

Each run records parameters, engine, kernel runtime, stop reason, full timeline,
family counts, and final living residents. JSON and timeline CSV downloads are
available under **Parameters & export**. Reusing parameters creates a new experiment;
it does not mutate the saved one. SQLite transactions keep results and metadata
together, including when multiple local browser sessions save at once.
Charts sample at most 2,000 observations per run to keep the browser responsive;
all observations remain in storage and downloads. Age histograms are aggregated
on the server instead of sending every resident to the chart.

## Native C compilation

Use **Native engine → Compile & verify native engine** in the dashboard, or:

```bash
uv run python -m demographics.build
uv run python -m demographics.build --status
uv run python -m demographics.benchmark
```

You need a working C compiler and Python development headers (for example,
`build-essential` and `python3-dev` on Debian/Ubuntu). Normal installation and the
Python backend do **not** require a compiler. Windows builds require the appropriate
Microsoft C++ Build Tools; they are not exercised in the Linux CI.

The build explicitly type-checks the kernel, translates `demographics/kernel.py`
with **mypyc**, builds its C extension, and compares complete seeded simulation
results against the original Python source. Standard `uv sync` never implicitly
compiles. The benchmark runs three identical 50-year, 1,500-founder experiments
per backend and reports median **kernel time**, not import, serialization, storage,
or UI time. It verifies every timeline observation and resident, not just totals.
Actual speedup varies with hardware, parameters, and Python version.

Workers run in fresh processes, so a successful UI build takes effect on the next
simulation **without restarting Streamlit**. Atomic binary replacement avoids
truncating an extension mapped by an existing worker. A build lock prevents
simultaneous compiler jobs. If a build process is forcibly killed, first confirm no
compiler is running, then remove the empty `build/.native-build-lock` directory.

**Rebuild after changing the kernel or switching Python versions.** The `auto`
backend imports an available extension; it does not automatically rebuild stale
binaries. `python` explicitly loads source even when a binary exists. `native`
fails clearly if no extension is available. To return to a source-only checkout,
remove only generated extension files listed by `--status` (and any generated
`*__mypyc*` helper extensions), or use a fresh clone. Build artifacts are ignored
by Git and are not portable releases.

## Command line

The original `main.py [years]` entry point now delegates to the maintained CLI:

```bash
uv run demographics 100 --backend python --save --name "Baseline"
uv run python main.py 30 --output data/example.json
uv run demographics --config examples/baseline.json --backend auto --save
```

`--config` accepts the same JSON parameters exported by the UI. A positional year
value overrides the file's `years`. Without `--save`, the CLI does not write history;
`--output` exports the complete result. Simulations stop at the requested duration,
extinction, or the hard population ceiling. The UI applies a ten-minute worker
timeout; larger experiments can be run from the CLI.

## Model assumptions & changes from the original

The previous exploratory scripts are preserved in [`legacy/`](legacy/), with their
historical requirements. They are not imported by the new app, supported by its
dependencies, or included in the type-check/native build. Old pickle files are not
automatically imported. **Never load an untrusted pickle: it can execute code.**

The maintained engine is a **deliberately redesigned demographic model**, not a
numerically compatible optimization of those scripts:

- Each experiment owns its clock and `random.Random(seed)`. Identical parameters
  give identical simulation data across reruns and Python/native backends in the
  same supported environment. Runtime metadata naturally differs.
- Founders have uniformly sampled initial ages. Lifespans are sampled from a
  normal distribution; founders are conditioned to survive day zero. This is a
  simplification, not a fitted mortality model.
- Only adults participate in conception. Women must fall in the configured age
  interval, and a living adult male must be available. Bounded random partner
  sampling excludes shared paternal families and known parent/child or sibling
  relationships; it is not a comprehensive kinship model. No explicit marriage,
  attraction, sexual-history, chromosome, or migration model is included.
- Annual conception probability is converted to the actual time-step duration:
  `1 - (1 - p) ** (days / 365.25)`. It applies to an eligible nonpregnant woman
  with an acceptable partner, not the whole population.
- Conception is recorded at a step's end. Delivery is processed at the first
  subsequent boundary after gestation. Babies age from **delivery**, not conception;
  both parents' child counts use the recorded father, not a newly sampled partner.
- Deaths are removed before partner selection. A mother who dies before the
  delivery boundary has no live birth. Per-birth infant and maternal mortality are
  separate probabilities. Birth and death counters include infants who die at birth.
- Steps are clamped to the requested duration. Events are discretized: smaller
  steps improve timing but increase work. Counts obey
  `population = initial_population + births - deaths` at every observation.
- Population never exceeds its limit. Births beyond remaining capacity are not
  processed; reaching the limit ends the simulation, without extrapolation.
- Person IDs replace cyclic references. The stored explorer is the **final living
  population**, not a genealogy archive of every deceased person. Parent IDs can
  refer to people no longer alive. Family numbers are stable paternal labels.

The hot loop is linear in living population per step, uses native typed objects
under mypyc, and avoids artificial sleeps, per-person printing, repeated singleton
clock lookups, and recursive object serialization. Observation data grows with the
number of steps; only final living person records are retained.

## Data & deployment

History lives at `data/simulations.sqlite3` (ignored by Git). Override the path with
`DEMOGRAPHICS_DB=/absolute/path/simulations.sqlite3`. Keep this directory on a
persistent local volume. To back up a running app, use SQLite's backup mechanism;
alternatively stop the app before copying the database.

This is a **trusted, local workspace**, with no login or per-user isolation. All
visitors to one deployment share its saved history. Keep it bound to localhost or
behind authentication; do not expose build controls on the public internet. Set
`DEMOGRAPHICS_ALLOW_BUILD=0` to disable UI compilation on hosted deployments.
Builds require writable source/build directories and dev dependencies. For a
source-only deployment, `uv sync --locked --no-dev` works; native benchmarks require
an extension compiled separately for that Python and platform.

## Development & verification

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest

# Includes real compilation through Streamlit's button, without mocks:
DEMOGRAPHICS_TEST_NATIVE=1 uv run pytest
```

The normal suite covers deterministic runs, validation, extinction, single-sex
populations, births and parentage, mortality accounting, population ceilings,
concurrent persistence, CLI exports, real simulation workers, and Streamlit
navigation/history/parameter reuse. Native parity runs when an extension exists;
the real UI compiler test is opt-in. GitHub Actions runs source-only tests first,
then the UI native-build test and the full native-enabled suite on Python 3.11–3.13.

```text
app.py                    Streamlit workspace
demographics/models.py    Validated parameters
demographics/kernel.py    Typed Python / mypyc hot loop
demographics/engine.py    Backend selection and JSON projection
demographics/storage.py   Transactional run history
demographics/service.py   Fresh worker subprocesses for the UI
demographics/build.py     Native compiler and verification workflow
tests/                    Model, storage, CLI, and Streamlit tests
legacy/                   Preserved original experiments
```
