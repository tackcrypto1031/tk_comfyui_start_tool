"""pip operations wrapper."""
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Hide subprocess windows on Windows
_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW


def get_venv_python(venv_path: str) -> str:
    """Get the python executable path inside a venv."""
    if sys.platform == "win32":
        return str(Path(venv_path) / "Scripts" / "python.exe")
    return str(Path(venv_path) / "bin" / "python")


def create_venv(venv_path: str) -> None:
    """Create a Python virtual environment."""
    subprocess.run(
        [sys.executable, "-m", "venv", venv_path],
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
    last_line = ""
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
                        if progress_callback:
                            progress_callback(line)
                    break
    # Handle remaining buffer
    remaining = buf.strip()
    if remaining:
        last_line = remaining
        if progress_callback:
            progress_callback(remaining)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"pip failed (exit {proc.returncode}): {last_line}")
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
