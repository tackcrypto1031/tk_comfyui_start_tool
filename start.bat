@echo off
cd /d "%~dp0"
if exist "%~dp0tools\python\pythonw.exe" (
    start "" "%~dp0tools\python\pythonw.exe" launcher.py
) else (
    start "" pythonw launcher.py
)
