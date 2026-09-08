@echo off
REM Double-click this file to start the Pinnacle Market Dashboard.
REM It installs dependencies on first run, starts the local server, and opens
REM your browser automatically. Runs entirely on this PC -- no other device needed.

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python isn't installed, or isn't on PATH.
    echo Install it from https://www.python.org/downloads/
    echo IMPORTANT: on the installer's first screen, check "Add python.exe to PATH".
    pause
    exit /b 1
)

python run_dashboard.py

echo.
pause
