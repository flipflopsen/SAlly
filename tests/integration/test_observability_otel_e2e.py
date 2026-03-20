"""End-to-end-ish OpenTelemetry smoke test.

This test is designed for environments where the telemetry stack is running
(e.g., OTEL Collector at localhost:4317). It runs the export in a fresh Python
process to avoid TelemetryManager singleton initialization issues.

If the collector endpoint is not reachable, the test is skipped.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from urllib.parse import urlparse

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.observability]


def _is_tcp_reachable(host: str, port: int, timeout_s: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def test_otel_export_smoke_subprocess():
    endpoint = os.environ.get("SALLY_OTEL_ENDPOINT", "http://localhost:4317")
    parsed = urlparse(endpoint)

    host = parsed.hostname or "localhost"
    port = parsed.port or 4317

    if not _is_tcp_reachable(host, port):
        pytest.skip(f"OTEL collector not reachable at {host}:{port}")

    env = os.environ.copy()
    # Some shells/launchers end up exporting values like "None" for optional ints.
    # Sally's env-var loader currently treats that as a real value and tries int("None").
    for key, value in list(env.items()):
        if isinstance(value, str) and value.strip().lower() == "none":
            env.pop(key, None)
    env["SALLY_OTEL_ENABLED"] = "true"
    env["SALLY_OTEL_ENDPOINT"] = endpoint

    code = (
        "import time\n"
        "from sally.core.telemetry import get_telemetry\n"
        "t = get_telemetry()\n"
        "with t.span('pytest.otel.e2e', attributes={'kind': 'smoke'}):\n"
        "    t.counter('pytest.otel.e2e.counter', 1)\n"
        "time.sleep(0.1)\n"
        "print('telemetry_enabled', t.enabled)\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=os.getcwd(),
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    assert "telemetry_enabled" in completed.stdout
