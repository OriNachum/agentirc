"""PID file management for culture daemon instances."""

from __future__ import annotations

import os
import re
from pathlib import Path

PID_DIR = os.path.expanduser("~/.culture/pids")


def _safe_name(name: str) -> str:
    """Sanitize a daemon name to prevent path traversal."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", Path(name).name)


def write_pid(name: str, pid: int) -> Path:
    """Write a PID file for the named daemon. Creates the directory if needed."""
    pid_dir = Path(PID_DIR)
    pid_dir.mkdir(parents=True, exist_ok=True)
    pid_path = pid_dir / f"{_safe_name(name)}.pid"
    pid_path.write_text(str(pid))
    return pid_path


def read_pid(name: str) -> int | None:
    """Read the PID for the named daemon. Returns None if file is missing."""
    pid_path = Path(PID_DIR) / f"{_safe_name(name)}.pid"
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def remove_pid(name: str) -> None:
    """Remove the PID file for the named daemon if it exists."""
    pid_path = Path(PID_DIR) / f"{_safe_name(name)}.pid"
    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass


def write_port(name: str, port: int) -> Path:
    """Write a port file for the named daemon. Creates the directory if needed."""
    pid_dir = Path(PID_DIR)
    pid_dir.mkdir(parents=True, exist_ok=True)
    port_path = pid_dir / f"{_safe_name(name)}.port"
    port_path.write_text(str(port))
    return port_path


def read_port(name: str) -> int | None:
    """Read the port for the named daemon. Returns None if file is missing."""
    port_path = Path(PID_DIR) / f"{_safe_name(name)}.port"
    if not port_path.exists():
        return None
    try:
        return int(port_path.read_text().strip())
    except (ValueError, OSError):
        return None


def remove_port(name: str) -> None:
    """Remove the port file for the named daemon if it exists."""
    port_path = Path(PID_DIR) / f"{_safe_name(name)}.port"
    try:
        port_path.unlink()
    except FileNotFoundError:
        pass


def is_culture_process(pid: int) -> bool:
    """Check whether the given PID belongs to a culture process.

    Reads /proc/<pid>/cmdline on Linux and checks NUL-separated argv
    tokens for an exact "culture" match (e.g. argv[0] basename or a
    ``-m culture`` argument).  On platforms without /proc, returns True
    (assumes valid).  On Linux, read/parse failures return False (fail
    closed) to avoid killing unrelated processes after PID reuse.
    """
    if not os.path.isdir("/proc"):
        # /proc not available (macOS / Windows) — can't verify, assume valid
        return True
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        tokens = [t for t in raw.decode(errors="replace").split("\x00") if t]
        return any(os.path.basename(t) == "culture" or t == "culture" for t in tokens)
    except (OSError, PermissionError):
        # On Linux /proc exists but we can't read this PID — fail closed
        return False


def is_process_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
