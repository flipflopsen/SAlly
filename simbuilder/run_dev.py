"""
Development server runner for SAlly simbuilder.

Starts two separate PowerShell windows:
1) Django backend (runserver)
2) Vite frontend (pnpm dev)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _ps_quote(s: str) -> str:
    # PowerShell single-quoted string escaping: ' -> ''
    return s.replace("'", "''")


def _find_powershell() -> str:
    # Prefer PowerShell 7 if installed, fallback to Windows PowerShell.
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"


def _spawn_powershell_window(*, title: str, cwd: Path, command: str, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    ps = _find_powershell()

    # Prepare env: inherit current env and add overrides
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    # Build a PowerShell command that:
    # - sets window title
    # - changes directory
    # - runs the command
    ps_cmd = (
        f"$Host.UI.RawUI.WindowTitle = '{_ps_quote(title)}'; "
        f"Set-Location -LiteralPath '{_ps_quote(str(cwd))}'; "
        f"{command}"
    )

    # CREATE_NEW_CONSOLE opens a new console window on Windows. [page:18]
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

    # -NoProfile avoids loading user profile scripts; -NoExit keeps the window open. [page:18]
    return subprocess.Popen(
        [ps, "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        cwd=str(cwd),
        env=env,
        creationflags=creationflags,
    )


def main() -> int:
    simbuilder_dir = Path(__file__).resolve().parent
    frontend_dir = simbuilder_dir / "frontend"

    # Basic checks
    if not (simbuilder_dir / "manage.py").exists():
        raise FileNotFoundError(f"manage.py not found in {simbuilder_dir}")

    if not frontend_dir.exists():
        raise FileNotFoundError(f"frontend dir not found: {frontend_dir}")

    # Ensure pnpm exists before opening the frontend console (otherwise you'll just get an immediate failure).
    pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if not pnpm:
        raise RuntimeError(
            "pnpm was not found on PATH. Install it (e.g., `winget install -e --id pnpm.pnpm`) "
            "or enable it via Corepack."
        )

    print("Starting backend PowerShell window...")
    backend_proc = _spawn_powershell_window(
        title="SAlly Backend (Django)",
        cwd=simbuilder_dir,
        extra_env={"DJANGO_SETTINGS_MODULE": "backend.config.settings"},
        command=f'{_ps_quote(sys.executable)} manage.py runserver 0.0.0.0:8000',
    )

    # Small delay to ensure backend window spawns first.
    time.sleep(0.7)

    print("Starting frontend PowerShell window...")
    frontend_command = (
        # install once if needed, then run dev server
        "if (-not (Test-Path -LiteralPath 'node_modules')) { "
        f'  & "{_ps_quote(pnpm)}" install; '
        "} "
        f'& "{_ps_quote(pnpm)}" run dev'
    )

    frontend_proc = _spawn_powershell_window(
        title="SAlly Frontend (Vite)",
        cwd=frontend_dir,
        command=frontend_command,
    )

    print("Both PowerShell windows launched. Close either window to stop its server.")
    print("Press Ctrl+C here to terminate both PowerShell processes.")

    try:
        while True:
            # If either console window is closed, exit (optional behavior).
            if backend_proc.poll() is not None:
                print("Backend PowerShell closed.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend PowerShell closed.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping both servers...")

    # Terminate both consoles (kills the shells; child processes usually die with them).
    for p in (backend_proc, frontend_proc):
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
