@echo off
cd /d "%~dp0"

set "LAUNCHER_LOG=%~dp0launcher-startup.log"
set "PY_EMBED=%~dp0tools\python\python.exe"
set "PYW_EMBED=%~dp0tools\python\pythonw.exe"

REM Prefer embedded Python; fall back to system Python on PATH so users who
REM already have Python installed (and never ran install.bat) still work.
if exist "%PY_EMBED%" (
    set "PY_EXE=%PY_EMBED%"
    set "PYW_EXE=%PYW_EMBED%"
) else (
    where pythonw >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No Python found.
        echo Either run install.bat to install the embedded Python,
        echo or install Python 3.10+ and ensure pythonw.exe is on PATH.
        pause
        exit /b 1
    )
    set "PY_EXE=python"
    set "PYW_EXE=pythonw"
)

REM Smoke test: run the launcher in console-mode briefly to surface import errors.
REM If the smoke test exits 0 within a short window it means startup is healthy
REM and we hand off to pythonw.exe for the real run.
"%PY_EXE%" -c "import PySide6, PySide6.QtWebEngineWidgets" > "%LAUNCHER_LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python dependencies are not importable.
    echo See log: %LAUNCHER_LOG%
    echo.
    echo ---- launcher-startup.log ----
    type "%LAUNCHER_LOG%"
    echo ------------------------------
    echo.
    echo Try re-running install.bat, or run this for a detailed trace:
    echo   "%PY_EXE%" launcher.py
    pause
    exit /b 1
)

start "" "%PYW_EXE%" launcher.py
