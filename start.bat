@echo off
cd /d "%~dp0"

set "LAUNCHER_LOG=%~dp0launcher-startup.log"
set "PY_EMBED=%~dp0tools\python\python.exe"
set "PYW_EMBED=%~dp0tools\python\pythonw.exe"

if not exist "%PY_EMBED%" (
    echo [ERROR] tools\python\python.exe not found. Run install.bat first.
    pause
    exit /b 1
)

REM Smoke test: run the launcher in console-mode briefly to surface import errors.
REM If the smoke test exits 0 within a short window it means startup is healthy
REM and we hand off to pythonw.exe for the real run.
"%PY_EMBED%" -c "import PySide6, PySide6.QtWebEngineWidgets" > "%LAUNCHER_LOG%" 2>&1
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
    echo   "%PY_EMBED%" launcher.py
    pause
    exit /b 1
)

start "" "%PYW_EMBED%" launcher.py
