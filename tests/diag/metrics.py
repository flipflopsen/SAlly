"""Lightweight metric recording for pytest-run diagram generation.

Tests can call `record_metric(...)` to emit numeric series that are later
rendered into per-test diagrams by `tests/conftest.py`.

This avoids changing production code and keeps the recording format simple.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def _get_diag_dir() -> Optional[Path]:
    value = os.environ.get("SALLY_DIAG_DIR")
    if not value:
        return None
    p = Path(value)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return p


def _sanitize_nodeid(nodeid: str) -> str:
    # Keep filenames short-ish and safe on Windows.
    out = nodeid
    for ch in ["\\", "/", ":", "*", "?", '"', "<", ">", "|", "[", "]", " "]:
        out = out.replace(ch, "_")
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:200] or "test"


def _current_nodeid() -> Optional[str]:
    # Provided by pytest while a test is running, looks like:
    #   "tests/test_mod.py::test_name (call)"
    current = os.environ.get("PYTEST_CURRENT_TEST")
    if not current:
        return None
    nodeid = current.split(" ", 1)[0]
    return nodeid


def record_metric(
    metric: str,
    value: float,
    unit: str = "",
    **tags: Any,
) -> None:
    """Append one metric data point for the currently running test."""

    diag_dir = _get_diag_dir()
    nodeid = _current_nodeid()
    if diag_dir is None or nodeid is None:
        return

    metrics_dir = diag_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    safe = _sanitize_nodeid(nodeid)
    path = metrics_dir / f"{safe}.jsonl"

    payload: Dict[str, Any] = {
        "ts": time.time(),
        "nodeid": nodeid,
        "metric": metric,
        "value": float(value),
        "unit": unit,
        "tags": tags or {},
    }

    path.write_text("", encoding="utf-8") if not path.exists() else None
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
