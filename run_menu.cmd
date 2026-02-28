@echo off
setlocal

REM Launch the Risk-First Slate Menu using the project's .venv
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "risk_first_slate_menu.py"
  goto :eof
)

echo ERROR: .venv\Scripts\python.exe not found.
echo - Create the venv (.venv) and install requirements.
echo - Or update this file to point at your interpreter.
echo.
pause
