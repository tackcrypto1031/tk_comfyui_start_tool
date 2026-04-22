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
    out_target = None
    close_after_spawn = None

    if capture_output:
        out_target = subprocess.PIPE
    elif log_file:
        close_after_spawn = open(log_file, 'w', encoding='utf-8')
        out_target = close_after_spawn
    else:
        out_target = subprocess.DEVNULL

    try:
        return subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=out_target, stderr=subprocess.STDOUT if log_file else out_target,
            text=True,
            **_SUBPROCESS_KWARGS,
        )
    finally:
        # Child process keeps its own handle; parent should release this handle.
        if close_after_spawn is not None:
            close_after_spawn.close()


def stop_process(pid: int, graceful_timeout: int = 5) -> bool:
    """Stop a process and its entire descendant tree.

    ComfyUI spawns children at runtime (torch DataLoader workers,
    ComfyUI-Manager's git/pip subprocesses, custom-node helpers) that can
    inherit the listening socket on port 8188. On Windows, ``terminate()``
    maps to ``TerminateProcess`` which is NOT recursive — killing only the
    parent leaves children alive and still bound to the port, which matches
    the user-reported "Stop did nothing" symptom on some machines.

    Enumerate descendants first, terminate children then parent, wait, and
    force ``kill()`` any survivor.
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False

    # Collect descendants BEFORE terminating the parent, otherwise they may
    # be reparented or reaped before we can see them.
    try:
        children = proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []

    for child in children:
        try:
            child.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    try:
        proc.terminate()
        proc.wait(timeout=graceful_timeout)
        result = True
    except psutil.TimeoutExpired:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        result = True
    except psutil.NoSuchProcess:
        result = False

    for child in children:
        try:
            if child.is_running():
                child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return result


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


def find_pid_on_port(port: int) -> Optional[int]:
    """Find the PID of the process listening on the given port."""
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port and conn.status == 'LISTEN' and conn.pid:
            return conn.pid
    return None


def find_available_port(start_port: int = 8188, max_tries: int = 10,
                        exclude: Optional[set] = None) -> int:
    """Find an available port starting from start_port.

    A port is considered unavailable if either:
      * ``is_port_in_use`` reports it as occupied (something is already
        listening — i.e. a live socket bind), OR
      * it appears in ``exclude`` (a set of ports that have been "claimed"
        but not yet bound — e.g. reserved by another environment that is
        still booting).  This closes the race where two environments
        launched in rapid succession both call ``find_available_port(8188)``
        before either has bound the socket and would otherwise both be
        handed port 8188.
    """
    excluded = set(exclude) if exclude else set()
    for i in range(max_tries):
        port = start_port + i
        if port in excluded:
            continue
        if not is_port_in_use(port):
            return port
    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_tries - 1}"
    )
