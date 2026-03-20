"""Run pytest and generate evaluation diagrams after each run.

Creates a run folder under `test_result_diagrams/` with the pattern:
  NN-<timestamp>-<group>

- NN is an incrementing run number (01, 02, ...)
- timestamp is YYYYMMDD-HHMMSS
- group is a user-provided label (e.g., unit, integration, benchmark)

The script runs pytest with `--junitxml` into the run folder, then parses the
JUnit XML and renders Matplotlib diagrams (PNG) into the same folder.

This is repo-local tooling; it does NOT modify production code under `sally/`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


_RUNS_ROOT = Path("test_result_diagrams")


@dataclass(frozen=True)
class TestCaseResult:
    nodeid: str
    classname: str
    name: str
    file_hint: str
    time_s: float
    outcome: str  # passed|failed|skipped|error


def _safe_import_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: WPS433 (runtime import)

        return plt
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Matplotlib is required to generate diagrams. "
            "Install with `pip install matplotlib` (or `uv pip install matplotlib`)."
        ) from exc


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_tests_with_diagrams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Runs pytest, saves JUnit XML, then generates diagrams into a new run folder.

            Examples:
              python scripts/run_tests_with_diagrams.py --group unit -- -m "not integration and not benchmark and not stress and not observability"
              python scripts/run_tests_with_diagrams.py --group integration -- -m integration
              python scripts/run_tests_with_diagrams.py --group all
            """
        ),
    )
    parser.add_argument(
        "--group",
        required=False,
        help="Test group label for folder naming (e.g., unit, integration, benchmark)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the built-in test groups sequentially (creates one run folder per group).",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional free-text name. If omitted, uses timestamp.",
    )
    parser.add_argument(
        "--runs-root",
        default=str(_RUNS_ROOT),
        help="Root folder to store run subfolders (default: test_result_diagrams)",
    )
    parser.add_argument(
        "--pytest",
        default=sys.executable,
        help="Python executable to invoke pytest with (default: current interpreter)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only create run folder + print the pytest command.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to pytest after `--`.",
    )

    ns = parser.parse_args(list(argv))

    # argparse includes the leading '--' in REMAINDER sometimes; normalize it out
    if ns.pytest_args and ns.pytest_args[0] == "--":
        ns.pytest_args = ns.pytest_args[1:]

    return ns


def _all_group_specs() -> list[tuple[str, list[str]]]:
    # Keep this list stable so evaluation folders are comparable over time.
    return [
        ("unit", ["-m", "unit"]),
        ("integration", ["-m", "integration"]),
        ("hdf5", ["-m", "hdf5"]),
        ("midas", ["-m", "midas"]),
        ("bhv", ["-m", "bhv"]),
        ("observability", ["-m", "observability"]),
        ("benchmark", ["-m", "benchmark"]),
    ]


def _next_run_number(runs_root: Path) -> int:
    if not runs_root.exists():
        return 1

    pattern = re.compile(r"^(?P<num>\d{2,})-")
    max_num = 0
    for entry in runs_root.iterdir():
        if not entry.is_dir():
            continue
        match = pattern.match(entry.name)
        if match:
            try:
                max_num = max(max_num, int(match.group("num")))
            except ValueError:
                continue

    return max_num + 1


def _sanitize_group(group: str) -> str:
    group = group.strip()
    group = re.sub(r"\s+", "_", group)
    group = re.sub(r"[^A-Za-z0-9_.-]", "", group)
    return group or "group"


def _sanitize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    return name or "run"


def _default_run_name() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _make_run_dir(runs_root: Path, name: str, group: str) -> Path:
    runs_root.mkdir(parents=True, exist_ok=True)

    run_num = _next_run_number(runs_root)
    run_num_str = f"{run_num:02d}"
    run_dir_name = f"{run_num_str}-{_sanitize_name(name)}-{_sanitize_group(group)}"
    run_dir = runs_root / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _run_pytest(
    python_exe: str,
    junit_path: Path,
    pytest_args: Sequence[str],
    env: Optional[dict] = None,
) -> int:
    # Use python -m pytest so it uses the same environment as python_exe.
    cmd = [python_exe, "-m", "pytest", f"--junitxml={str(junit_path)}", *pytest_args]
    print("[run]", " ".join(cmd))

    completed = subprocess.run(cmd, cwd=str(Path.cwd()), env=env)
    return int(completed.returncode)


def _read_junit_results(junit_xml_path: Path) -> Tuple[List[TestCaseResult], dict]:
    tree = ET.parse(junit_xml_path)
    root = tree.getroot()

    # JUnit root can be <testsuite> or <testsuites>
    testsuites: List[ET.Element]
    if root.tag == "testsuite":
        testsuites = [root]
    else:
        testsuites = list(root.findall("testsuite"))

    results: List[TestCaseResult] = []
    summary = {
        "tests": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "time": 0.0,
    }

    for suite in testsuites:
        for key in ("tests", "failures", "errors", "skipped"):
            if suite.get(key) is not None:
                summary[key] += int(float(suite.get(key, "0")))
        if suite.get("time") is not None:
            summary["time"] += float(suite.get("time", "0"))

        for case in suite.findall("testcase"):
            classname = case.get("classname", "")
            name = case.get("name", "")
            time_s = float(case.get("time", "0") or "0")

            # Determine outcome from child tags
            outcome = "passed"
            if case.find("failure") is not None:
                outcome = "failed"
            elif case.find("error") is not None:
                outcome = "error"
            elif case.find("skipped") is not None:
                outcome = "skipped"

            # Best-effort nodeid-ish label.
            # Pytest's junitxml uses classname like "tests.test_mod.TestClass".
            nodeid = f"{classname}::{name}" if classname else name

            file_hint = classname.split(".")[0] if classname else "unknown"
            if classname.startswith("tests."):
                # Keep tests.<module> as file hint.
                parts = classname.split(".")
                if len(parts) >= 2:
                    file_hint = parts[1]

            results.append(
                TestCaseResult(
                    nodeid=nodeid,
                    classname=classname,
                    name=name,
                    file_hint=file_hint,
                    time_s=time_s,
                    outcome=outcome,
                )
            )

    return results, summary


def _write_run_metadata(run_dir: Path, group: str, pytest_args: Sequence[str], exit_code: int) -> None:
    meta_path = run_dir / "run_meta.txt"
    now = _dt.datetime.now().isoformat(timespec="seconds")

    meta_path.write_text(
        "\n".join(
            [
                f"timestamp={now}",
                f"group={group}",
                f"exit_code={exit_code}",
                f"cwd={Path.cwd()}",
                f"pytest_args={' '.join(pytest_args)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _plot_outcomes(plt, run_dir: Path, results: List[TestCaseResult]) -> None:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for r in results:
        counts[r.outcome] = counts.get(r.outcome, 0) + 1

    labels = ["passed", "failed", "error", "skipped"]
    values = [counts.get(k, 0) for k in labels]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, values)
    ax.set_title("Test Outcomes")
    ax.set_ylabel("count")
    for i, v in enumerate(values):
        ax.text(i, v + max(0.5, 0.01 * max(values + [1])), str(v), ha="center")

    fig.tight_layout()
    fig.savefig(run_dir / "01_outcomes.png", dpi=160)
    plt.close(fig)


def _plot_duration_histogram(plt, run_dir: Path, results: List[TestCaseResult]) -> None:
    times = [r.time_s for r in results if r.outcome != "skipped"]
    if not times:
        return

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(times, bins=min(30, max(5, int(len(times) ** 0.5))))
    ax.set_title("Test Duration Histogram")
    ax.set_xlabel("seconds")
    ax.set_ylabel("tests")
    fig.tight_layout()
    fig.savefig(run_dir / "02_duration_hist.png", dpi=160)
    plt.close(fig)


def _plot_slowest_tests(plt, run_dir: Path, results: List[TestCaseResult], top_n: int = 15) -> None:
    non_skipped = [r for r in results if r.outcome != "skipped"]
    slowest = sorted(non_skipped, key=lambda r: r.time_s, reverse=True)[:top_n]
    if not slowest:
        return

    slowest_rev = list(reversed(slowest))
    labels = [r.name[:50] + ("…" if len(r.name) > 50 else "") for r in slowest_rev]
    values = [r.time_s for r in slowest_rev]

    fig, ax = plt.subplots(figsize=(10, 5))
    y = list(range(len(values)))
    ax.barh(y, values)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title(f"Top {len(slowest)} Slowest Tests")
    ax.set_xlabel("seconds")
    fig.tight_layout()
    fig.savefig(run_dir / "03_slowest_tests.png", dpi=160)
    plt.close(fig)


def _plot_outcomes_by_module(plt, run_dir: Path, results: List[TestCaseResult], max_modules: int = 15) -> None:
    # Group by file_hint/module hint
    module_counts = {}
    for r in results:
        mod = r.file_hint or "unknown"
        if mod not in module_counts:
            module_counts[mod] = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        module_counts[mod][r.outcome] += 1

    # pick most relevant modules by total tests
    modules_sorted = sorted(module_counts.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:max_modules]
    modules = [m for m, _ in modules_sorted]

    if not modules:
        return

    passed = [module_counts[m]["passed"] for m in modules]
    failed = [module_counts[m]["failed"] for m in modules]
    error = [module_counts[m]["error"] for m in modules]
    skipped = [module_counts[m]["skipped"] for m in modules]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = list(range(len(modules)))

    ax.bar(x, passed, label="passed")
    ax.bar(x, failed, bottom=passed, label="failed")

    bottom2 = [p + f for p, f in zip(passed, failed)]
    ax.bar(x, error, bottom=bottom2, label="error")

    bottom3 = [b + e for b, e in zip(bottom2, error)]
    ax.bar(x, skipped, bottom=bottom3, label="skipped")

    ax.set_xticks(x)
    ax.set_xticklabels(modules, rotation=45, ha="right")
    ax.set_title(f"Outcomes by Module (top {len(modules)})")
    ax.set_ylabel("count")
    ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(run_dir / "04_outcomes_by_module.png", dpi=160)
    plt.close(fig)


def _generate_diagrams(run_dir: Path, junit_xml_path: Path) -> None:
    plt = _safe_import_matplotlib()

    results, summary = _read_junit_results(junit_xml_path)

    # save summary for later analysis
    (run_dir / "junit_summary.txt").write_text(
        "\n".join(
            [
                f"tests={summary['tests']}",
                f"failures={summary['failures']}",
                f"errors={summary['errors']}",
                f"skipped={summary['skipped']}",
                f"time_s={summary['time']:.3f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _plot_outcomes(plt, run_dir, results)
    _plot_duration_histogram(plt, run_dir, results)
    _plot_slowest_tests(plt, run_dir, results)
    _plot_outcomes_by_module(plt, run_dir, results)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ns = _parse_args(argv or sys.argv[1:])

    runs_root = Path(ns.runs_root)
    run_name = ns.name or _default_run_name()

    if not ns.all and not ns.group:
        raise SystemExit("Provide either --group <name> or --all")

    def run_one(group: str, extra_pytest_args: Sequence[str]) -> int:
        run_dir = _make_run_dir(runs_root, run_name, group)
        junit_path = run_dir / "junit.xml"

        per_test_dir = run_dir / "per_test_diagrams"
        per_test_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["SALLY_DIAG_DIR"] = str(per_test_dir)

        effective_pytest_args = [f"--diag-dir={str(per_test_dir)}", *list(extra_pytest_args)]

        if ns.dry_run:
            print(f"[dry-run] created {run_dir}")
            print(
                "[dry-run] pytest command:",
                " ".join([ns.pytest, "-m", "pytest", f"--junitxml={junit_path}", *effective_pytest_args]),
            )
            return 0

        exit_code = _run_pytest(ns.pytest, junit_path, effective_pytest_args, env=env)
        _write_run_metadata(run_dir, group, effective_pytest_args, exit_code)

        try:
            if junit_path.exists():
                _generate_diagrams(run_dir, junit_path)
                print(f"[ok] diagrams written to {run_dir}")
            else:
                print(f"[warn] junit xml missing at {junit_path}")
        except Exception as exc:
            print(f"[warn] diagram generation failed: {exc}")
            print(f"[warn] junit xml still available at {junit_path}")

        return exit_code

    if ns.all:
        overall_ok = True
        for group, group_args in _all_group_specs():
            print(f"\n[all] running group={group}")
            code = run_one(group, [*group_args, *ns.pytest_args])
            if code != 0:
                overall_ok = False
        return 0 if overall_ok else 1

    return run_one(ns.group, ns.pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
