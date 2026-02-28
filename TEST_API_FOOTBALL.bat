@echo off
echo ============================================================
echo API-FOOTBALL CONNECTION TEST
echo ============================================================
echo.
echo Paste your RapidAPI key below and press Enter:
set /p APIKEY="API Key: "
echo.
echo Setting environment variable...
set RAPIDAPI_KEY=%APIKEY%
echo.
echo Testing connection with Cristiano Ronaldo...
echo.
.venv\Scripts\python.exe soccer\api_football_integration.py
echo.
echo ============================================================
echo Test complete. Check results above.
echo ============================================================
pause
