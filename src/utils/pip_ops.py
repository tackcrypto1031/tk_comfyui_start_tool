"""pip operations wrapper."""
from collections import deque
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Hide subprocess windows on Windows
_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW


def get_venv_python(venv_path: str) -> str:
    """Get the python executable path inside a venv.

    Always returns an absolute path so subprocess calls work regardless
    of the current working directory.
    """
    venv = Path(venv_path).resolve()
    if sys.platform == "win32":
        return str(venv / "Scripts" / "python.exe")
    return str(venv / "bin" / "python")


def create_venv(venv_path: str, python_executable: str = "") -> None:
    """Create a Python virtual environment.

    If *python_executable* is provided it is used instead of the running
    interpreter, allowing venvs to be created for a different Python version.
    Embeddable Python distributions lack the built-in ``venv`` module, so
    when a custom executable is given we use ``virtualenv`` (which is
    installed during the Python download step) as a fallback.
    """
    executable = python_executable if python_executable else sys.executable

    if python_executable:
        # Custom (embeddable) Python — try venv first, fall back to virtualenv
        result = subprocess.run(
            [executable, "-m", "venv", venv_path],
            capture_output=True,
            text=True,
            **_SUBPROCESS_KWARGS,
        )
        if result.returncode != 0:
            # venv unavailable (embeddable build) — use virtualenv instead.
            # Install virtualenv on-demand if it isn't already present
            # (covers Python versions downloaded before the installer was
            # updated to bundle virtualenv).
            probe = subprocess.run(
                [executable, "-m", "virtualenv", "--version"],
                capture_output=True, text=True, **_SUBPROCESS_KWARGS,
            )
            if probe.returncode != 0:
                subprocess.run(
                    [executable, "-m", "pip", "install", "virtualenv"],
                    check=True, capture_output=True, text=True,
                    **_SUBPROCESS_KWARGS,
                )
            subprocess.run(
                [executable, "-m", "virtualenv", venv_path],
                check=True,
                capture_output=True,
                text=True,
                **_SUBPROCESS_KWARGS,
            )
    else:
        subprocess.run(
            [executable, "-m", "venv", venv_path],
            check=True,
            capture_output=True,
            text=True,
            **_SUBPROCESS_KWARGS,
        )


def get_python_version(venv_path: str) -> str:
    """Get the Python version in a venv."""
    python = get_venv_python(venv_path)
    result = subprocess.run(
        [python, "--version"],
        capture_output=True,
        text=True,
        check=True,
        **_SUBPROCESS_KWARGS,
    )
    # Output: "Python 3.11.9\n"
    return result.stdout.strip().replace("Python ", "")


def run_pip(venv_path: str, args: list) -> subprocess.CompletedProcess:
    """Run pip in the specified venv."""
    python = get_venv_python(venv_path)
    return subprocess.run(
        [python, "-m", "pip"] + args,
        capture_output=True,
        text=True,
        **_SUBPROCESS_KWARGS,
    )


def run_pip_with_progress(venv_path: str, args: list,
                          progress_callback=None) -> subprocess.CompletedProcess:
    """Run pip in the specified venv, streaming output to progress_callback.

    Merges stderr into stdout to avoid pipe deadlock, then reads stdout
    in chunks to handle pip's \\r-based progress bar updates.
    """
    python = get_venv_python(venv_path)
    proc = subprocess.Popen(
        [python, "-m", "pip"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr into stdout to avoid deadlock
        **_SUBPROCESS_KWARGS,
    )

    def _is_notice_line(line: str) -> bool:
        return line.lower().startswith("[notice]")

    def _looks_like_error_line(line: str) -> bool:
        low = line.lower()
        error_markers = (
            "error:",
            "fatal:",
            "traceback",
            "exception",
            "failed",
            "could not",
            "no matching distribution found",
            "no versions found",
            "subprocess-exited-with-error",
            "readtimeout",
            "timed out",
            "proxyerror",
            "ssl",
            "connection error",
            "http error",
        )
        return any(marker in low for marker in error_markers)

    def _compact(line: str, limit: int = 160) -> str:
        if len(line) <= limit:
            return line
        return line[:limit - 3] + "..."

    last_line = ""
    last_non_notice_line = ""
    recent_lines = deque(maxlen=40)
    buf = ""
    while True:
        chunk = proc.stdout.read(512)
        if not chunk:
            break
        try:
            text = chunk.decode("utf-8", errors="replace")
        except AttributeError:
            text = chunk  # already str if text=True
        buf += text
        # Split on both \n and \r to capture pip's progress updates
        while "\n" in buf or "\r" in buf:
            for sep in ("\n", "\r"):
                idx = buf.find(sep)
                if idx != -1:
                    line = buf[:idx].strip()
                    buf = buf[idx + 1:]
                    if line:
                        last_line = line
                        recent_lines.append(line)
                        if not _is_notice_line(line):
                            last_non_notice_line = line
                        if progress_callback:
                            progress_callback(line)
                    break
    # Handle remaining buffer
    remaining = buf.strip()
    if remaining:
        last_line = remaining
        recent_lines.append(remaining)
        if not _is_notice_line(remaining):
            last_non_notice_line = remaining
        if progress_callback:
            progress_callback(remaining)
    proc.wait()
    if proc.returncode != 0:
        non_notice_lines = [line for line in recent_lines if not _is_notice_line(line)]
        detail = next(
            (line for line in reversed(non_notice_lines) if _looks_like_error_line(line)),
            "",
        )
        if not detail:
            if non_notice_lines:
                tail = " | ".join(_compact(line) for line in non_notice_lines[-4:])
                detail = f"no explicit error line from pip; output tail: {tail}"
            else:
                detail = _compact(last_line) if last_line else "unknown error"
        raise RuntimeError(f"pip failed (exit {proc.returncode}): {detail}")
    return proc


def freeze(venv_path: str) -> dict:
    """Get pip freeze output as a dict of {package: version}."""
    result = run_pip(venv_path, ["freeze"])
    packages = {}
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("-e ") or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            packages[name.strip()] = version.strip()
    return packages
