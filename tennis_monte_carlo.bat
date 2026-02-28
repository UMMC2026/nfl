@echo off
REM Tennis Props Monte Carlo - Quick Launcher
REM 1. Copy Underdog props to clipboard
REM 2. Run this file
REM 3. Paste props (Right-click in terminal)
REM 4. Press Ctrl+Z then Enter
REM 5. Get SLAM/STRONG/LEAN picks!

cd /d "%~dp0"
.venv\Scripts\python.exe quick_tennis.py
pause
