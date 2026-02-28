# API-Football Quick Test
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "API-FOOTBALL CONNECTION TEST" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$env:RAPIDAPI_KEY = "40617f7d9c0d475d905494f0adb0b545"

Write-Host "Testing connection with Cristiano Ronaldo..." -ForegroundColor Yellow
Write-Host ""

& .venv\Scripts\python.exe soccer\api_football_integration.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "If you see stats above, API is working!" -ForegroundColor Green
Write-Host "If you see 403 error, subscribe at:" -ForegroundColor Yellow
Write-Host "https://rapidapi.com/api-sports/api/api-football" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
