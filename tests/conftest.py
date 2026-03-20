"""Pytest plugin: generate per-test diagrams.

Goal: after *every* test case, emit at least one semantically meaningful PNG.
- Always: duration + outcome summary
- If the test recorded metrics via `tests.diag.metrics.record_metric`, also plot those.

Runner support: `scripts/run_tests_with_diagrams.py` sets `SALLY_DIAG_DIR` and
passes `--diag-dir` automatically.
"""

from __future__ import annotations

import json
import os
import tracemalloc
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--diag-dir",
        action="store",
        default=None,
        help="Directory to write per-test diagrams/metrics (default: env SALLY_DIAG_DIR)",
    )


def _get_diag_dir(config: pytest.Config) -> Optional[Path]:
    opt = config.getoption("--diag-dir")
    value = opt or os.environ.get("SALLY_DIAG_DIR")
    if not value:
        return None
    p = Path(value)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sanitize_nodeid(nodeid: str) -> str:
    out = nodeid
    for ch in ["\\", "/", ":", "*", "?", '"', "<", ">", "|", "[", "]", " "]:
        out = out.replace(ch, "_")
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:200] or "test"


def _safe_import_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _load_metrics(diag_dir: Path, nodeid: str) -> Dict[str, List[Tuple[float, float, str]]]:
    metrics_dir = diag_dir / "metrics"
    safe = _sanitize_nodeid(nodeid)
    path = metrics_dir / f"{safe}.jsonl"
    if not path.exists():
        return {}

    out: Dict[str, List[Tuple[float, float, str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            continue
        metric = str(obj.get("metric", ""))
        if not metric:
            continue
        ts = float(obj.get("ts", 0.0))
        val = float(obj.get("value", 0.0))
        unit = str(obj.get("unit", ""))
        out.setdefault(metric, []).append((ts, val, unit))

    # Ensure sorted by time
    for k in list(out.keys()):
        out[k] = sorted(out[k], key=lambda t: t[0])

    return out


def _iter_marker_names(item: pytest.Item) -> List[str]:
    names: List[str] = []
    try:
        for m in item.iter_markers():
            if m and m.name:
                names.append(str(m.name))
    except Exception:
        return []
    # De-dup preserving order
    seen = set()
    out: List[str] = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _test_out_dir(diag_dir: Path, nodeid: str) -> Path:
    safe = _sanitize_nodeid(nodeid)
    out = diag_dir / safe
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_json(path: Path, obj: dict) -> None:
    try:
        path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        return


def _derive_metric_overlays(metrics: Dict[str, List[Tuple[float, float, str]]]) -> Dict[str, float]:
    """Compute derived values (e.g., events/ms) from common raw metrics."""
    derived: Dict[str, float] = {}

    def last(metric_name: str) -> Optional[Tuple[float, float, str]]:
        series = metrics.get(metric_name)
        if not series:
            return None
        return series[-1]

    pub = last("publish_throughput_eps")
    if pub is not None:
        derived["publish_throughput_epms"] = float(pub[1]) / 1000.0
    proc = last("process_throughput_eps")
    if proc is not None:
        derived["process_throughput_epms"] = float(proc[1]) / 1000.0

    return derived


def _plot_summary(out_dir: Path, nodeid: str, outcome: str, duration_s: float, peak_kib: Optional[float]) -> None:
    plt = _safe_import_matplotlib()

    fig, ax = plt.subplots(figsize=(10, 3))
    color = {
        "passed": "#2ca02c",
        "failed": "#d62728",
        "skipped": "#7f7f7f",
        "error": "#ff7f0e",
    }.get(outcome, "#1f77b4")

    xs = ["duration_s"]
    ys = [max(0.0, float(duration_s or 0.0))]
    if peak_kib is not None:
        xs.append("peak_alloc_kib")
        ys.append(max(0.0, float(peak_kib)))

    ax.bar(xs, ys, color=color)
    ax.set_title(f"{nodeid} | outcome={outcome}")
    ax.set_ylim(bottom=0)
    for i, y in enumerate(ys):
        ax.text(i, y, f"{y:.3f}", ha="center", va="bottom")

    fig.tight_layout()
    fig.savefig(out_dir / "00-summary.png", dpi=140)
    plt.close(fig)


def _plot_metadata(out_dir: Path, nodeid: str, markers: List[str], derived: Dict[str, float]) -> None:
    plt = _safe_import_matplotlib()

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.axis("off")
    marker_text = ", ".join(markers) if markers else "(none)"
    ax.text(0.01, 0.85, "Logical / classification view", fontsize=12, weight="bold")
    ax.text(0.01, 0.60, f"nodeid: {nodeid}", fontsize=10)
    ax.text(0.01, 0.40, f"markers: {marker_text}", fontsize=10)
    extra = []
    if "publish_throughput_epms" in derived:
        extra.append(f"publish: {derived['publish_throughput_epms']:.3f} events/ms")
    if "process_throughput_epms" in derived:
        extra.append(f"process: {derived['process_throughput_epms']:.3f} events/ms")
    if extra:
        ax.text(0.01, 0.25, " | ".join(extra), fontsize=10)
        ax.text(0.01, 0.10, "Arrange → Act → Assert", fontsize=11)
    else:
        ax.text(0.01, 0.15, "Arrange → Act → Assert", fontsize=11)

    fig.tight_layout()
    fig.savefig(out_dir / "01-metadata.png", dpi=140)
    plt.close(fig)


def _plot_metrics(out_dir: Path, metrics: Dict[str, List[Tuple[float, float, str]]]) -> None:
    plt = _safe_import_matplotlib()

    if not metrics:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.axis("off")
        ax.text(0.5, 0.5, "No custom metrics recorded", ha="center", va="center")
        fig.tight_layout()
        fig.savefig(out_dir / "02-metrics.png", dpi=140)
        plt.close(fig)
        return

    preferred = [
        "publish_throughput_eps",
        "process_throughput_eps",
        "push_ops_per_s",
        "pop_ops_per_s",
    ]
    metric_names = [m for m in preferred if m in metrics] + [m for m in metrics.keys() if m not in preferred]
    metric_names = metric_names[:6]

    # Combined overview plot
    fig, ax = plt.subplots(figsize=(12, 4))
    for metric in metric_names:
        series = metrics[metric]
        ys = [v for _, v, _ in series]
        unit = series[-1][2] if series else ""
        label = f"{metric} ({unit})".strip()
        if len(ys) == 1:
            ax.bar([label], ys)
        else:
            ax.plot(list(range(len(ys))), ys, marker="o", label=label)

    ax.set_title("Recorded metrics (overview)")
    if any(len(metrics[m]) > 1 for m in metric_names):
        ax.legend(loc="best")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out_dir / "02-metrics.png", dpi=140)
    plt.close(fig)

    # Per-metric intermediate diagrams (kept, not removed)
    for metric in metric_names:
        series = metrics[metric]
        ys = [v for _, v, _ in series]
        unit = series[-1][2] if series else ""

        fig, ax = plt.subplots(figsize=(10, 3))
        if len(ys) == 1:
            ax.bar([metric], ys)
            ax.text(0, ys[0], f"{ys[0]:.3f}", ha="center", va="bottom")
        else:
            ax.plot(list(range(len(ys))), ys, marker="o")
        ax.set_title(f"{metric} ({unit})".strip())
        ax.set_ylim(bottom=0)
        fig.tight_layout()

        safe_metric = _sanitize_nodeid(metric)
        fig.savefig(out_dir / f"metric-{safe_metric}.png", dpi=140)
        plt.close(fig)


def _plot_per_test(item: pytest.Item, diag_dir: Path, nodeid: str, outcome: str, duration_s: float) -> None:
    out_dir = _test_out_dir(diag_dir, nodeid)
    metrics = _load_metrics(diag_dir, nodeid)
    markers = _iter_marker_names(item)

    # Tracemalloc stats captured earlier (best-effort)
    peak_kib = getattr(item, "_diag_peak_kib", None)

    derived = _derive_metric_overlays(metrics)
    payload = {
        "nodeid": nodeid,
        "outcome": outcome,
        "duration_s": float(duration_s or 0.0),
        "markers": markers,
        "peak_alloc_kib": peak_kib,
        "derived": derived,
        "recorded_metrics": sorted(list(metrics.keys())),
    }
    _write_json(out_dir / "result.json", payload)

    _plot_summary(out_dir, nodeid, outcome, duration_s, peak_kib)
    _plot_metadata(out_dir, nodeid, markers, derived)
    _plot_metrics(out_dir, metrics)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_runtest_setup(item: pytest.Item) -> None:
    # Capture generic “precision” signal for every test: peak allocated memory.
    try:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        tracemalloc.reset_peak()
    except Exception:
        return


def pytest_runtest_teardown(item: pytest.Item, nextitem):
    # Capture peak memory after call.
    try:
        if tracemalloc.is_tracing():
            _cur, peak = tracemalloc.get_traced_memory()
            setattr(item, "_diag_peak_kib", float(peak) / 1024.0)
    except Exception:
        pass
    finally:
        try:
            if tracemalloc.is_tracing():
                tracemalloc.stop()
        except Exception:
            pass

    # Create the diagram once per test, after call phase.
    rep = getattr(item, "rep_call", None)
    if rep is None:
        return

    diag_dir = _get_diag_dir(item.config)
    if diag_dir is None:
        return

    try:
        _plot_per_test(item, diag_dir, rep.nodeid, rep.outcome, float(rep.duration or 0.0))
    except Exception:
        return
