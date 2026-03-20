# Test execution + diagram generation

This repo includes a small runner that:
1) runs `pytest` with `--junitxml`
2) generates Matplotlib PNG diagrams from the JUnit XML
3) generates **one PNG per test case** (duration/outcome + any recorded metrics)
4) writes everything into a new run folder under `test_result_diagrams/`:

`NN-<timestamp>-<group>`

- `NN` is incrementing (01, 02, ...)
- `<timestamp>` is `YYYYMMDD-HHMMSS`
- `<group>` is your label (e.g., `unit`, `midas`, `hdf5`)

Each run folder contains:

- `junit.xml` (pytest JUnit output)
- run-level PNG diagrams (from the JUnit XML)
- `per_test_diagrams/` (per-test folders; multiple intermediate PNGs per test)
	- `per_test_diagrams/<test-nodeid-sanitized>/00-summary.png` (duration + peak alloc + outcome)
	- `per_test_diagrams/<test-nodeid-sanitized>/01-metadata.png` (logical/classification view)
	- `per_test_diagrams/<test-nodeid-sanitized>/02-metrics.png` (overview)
	- `per_test_diagrams/<test-nodeid-sanitized>/metric-*.png` (intermediate per-metric charts; not deleted)
	- `per_test_diagrams/<test-nodeid-sanitized>/result.json` (machine-readable per-test result + derived values)
	- `per_test_diagrams/metrics/*.jsonl` (raw metric points emitted by tests)

## Markers / groups

Markers are declared in `pyproject.toml` and used for grouping:

- `unit`
- `integration`
- `hdf5`
- `midas`
- `bhv`
- `benchmark`
- `observability`

## Run a group (recommended)

From the repo root:

Using the venv Python:

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group unit -- -m unit
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group midas -- -m midas
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group hdf5 -- -m hdf5
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group bhv -- -m bhv
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group observability -- -m observability
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group benchmark -- -m benchmark
```

Using `uv`:

```powershell
uv run python scripts\run_tests_with_diagrams.py --group midas -- -m midas
```

## Run ALL groups (one folder per group)

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --all
```

You can pass additional pytest args that apply to every group run:

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --all -- -q
```

## Run a single test file (still produces diagrams)

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group single -- tests\midas\test_midas.py
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group single -- tests\integration\test_scada_integration.py
```

## Run a single test by node id

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group single -- tests\midas\test_midas.py::TestMidasScenarioParser::test_parse_string
```

## Per-test diagrams when running pytest directly

You can also generate per-test diagrams without the runner:

```powershell
pytest --diag-dir .\test_result_diagrams\_adhoc_per_test
```

## Strict benchmark thresholds (optional)

Benchmark tests record throughput metrics by default, but **do not fail** on high, machine-dependent thresholds unless you opt in.

Enable strict throughput assertions:

```powershell
$env:SALLY_STRICT_BENCHMARKS='1'
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group benchmark -- -m benchmark
```

## Benchmark precision controls (optional)

Some benchmarks support repeat runs to generate more "precision" points per test (produces line charts instead of single bars):

```powershell
$env:SALLY_BENCH_REPEATS='5'
$env:SALLY_BENCH_EVENTS='200000'
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group benchmark -- tests\test_event_bus_benchmark.py::TestEventBusBenchmark::test_publish_throughput_sync
```

## Run by keyword (pytest -k)

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_with_diagrams.py --group single -- -k "midas and parse"
```
