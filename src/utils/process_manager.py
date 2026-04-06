"""Process management utilities."""
import socket
import subprocess
import sys
from typing import Optional

import psutil

# Hide subprocess windows on Windows
_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW


def start_process(cmd: list, cwd: str = None, env: dict = None,
                  capture_output: bool = False, log_file: str = None) -> subprocess.Popen:
    """Start a subprocess and return the Popen object.

    Args:
        capture_output: If True, pipe stdout/stderr. If False, redirect to DEVNULL
                       (appropriate for long-running background processes).
        log_file: If provided, redirect stdout and stderr to this file path.
    """
    if capture_output:
        out_target = subprocess.PIPE
    elif log_file:
        out_target = open(log_file, 'w', encoding='utf-8')
    else:
        out_target = subprocess.DEVNULL

    return subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=out_target, stderr=subprocess.STDOUT if log_file else out_target,
        text=True,
        **_SUBPROCESS_KWARGS,
    )


def stop_process(pid: int, graceful_timeout: int = 5) -> bool:
    """Stop a process gracefully, then force kill if needed."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=graceful_timeout)
        return True
    except psutil.TimeoutExpired:
        proc.kill()
        return True
    except psutil.NoSuchProcess:
        return False


def is_process_running(pid: int) -> bool:
    """Check if a process is still running."""
    return psutil.pid_exists(pid)


def stop_process_on_port(port: int, graceful_timeout: int = 5) -> bool:
    """Find and stop the process listening on the given port."""
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port and conn.status == 'LISTEN' and conn.pid:
            return stop_process(conn.pid, graceful_timeout)
    return False


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def find_available_port(start_port: int = 8188, max_tries: int = 10) -> int:
    """Find an available port starting from start_port."""
    for i in range(max_tries):
        port = start_port + i
        if not is_port_in_use(port):
            return port
    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_tries - 1}"
    )
