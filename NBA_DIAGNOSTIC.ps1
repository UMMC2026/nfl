# NBA PIPELINE QUICK DIAGNOSTIC
# Run this to verify NBA Role Layer is working

Write-Host "="*70 -ForegroundColor Cyan
Write-Host "NBA PIPELINE QUICK DIAGNOSTIC" -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan

# Test 1: Check files exist
Write-Host "`n[TEST 1] Checking files..." -ForegroundColor Yellow
$files = @(
    "engine\enrich_nba_simple.py",
    "nba\role_scheme_normalizer.py",
    "filter_nba_role_layer.py",
    "risk_first_analyzer.py"
)

$filesOK = $true
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  OK: $file" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $file" -ForegroundColor Red
        $filesOK = $false
    }
}

# Test 2: Check specialist flags in enrichment
Write-Host "`n[TEST 2] Checking specialist detection..." -ForegroundColor Yellow
$enrichContent = Get-Content "engine\enrich_nba_simple.py" -Raw

$specialists = @('REB_SPECIALIST', '3PM_SPECIALIST', 'STL_SPECIALIST', 'BLK_SPECIALIST', 'FGM_SPECIALIST', 'AST_SPECIALIST')
$specialistsOK = $true
foreach ($spec in $specialists) {
    if ($enrichContent -match $spec) {
        Write-Host "  OK: $spec found" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $spec not found" -ForegroundColor Red
        $specialistsOK = $false
    }
}

# Test 3: Check latest output file
Write-Host "`n[TEST 3] Checking latest output..." -ForegroundColor Yellow
$latestFile = Get-ChildItem "outputs\*RISK_FIRST*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($latestFile) {
    Write-Host "  Latest file: $($latestFile.Name)" -ForegroundColor Cyan
    Write-Host "  Modified: $($latestFile.LastWriteTime)" -ForegroundColor Cyan
    
    $content = Get-Content $latestFile.FullName -Raw | ConvertFrom-Json
    $picks = $content.results
    
    Write-Host "  Total picks: $($picks.Count)" -ForegroundColor Cyan
    
    $withArchetype = ($picks | Where-Object { $_.nba_role_archetype }).Count
    $withSpecialist = ($picks | Where-Object { $_.nba_specialist_flags }).Count
    $withCapAdj = ($picks | Where-Object { $null -ne $_.nba_confidence_cap_adjustment }).Count
    
    if ($withArchetype -gt 0) {
        Write-Host "  OK: $withArchetype picks have archetype" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: No picks have archetype" -ForegroundColor Red
    }
    
    if ($withCapAdj -gt 0) {
        Write-Host "  OK: $withCapAdj picks have cap adjustment" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: No picks have cap adjustment" -ForegroundColor Red
    }
    
    if ($withSpecialist -gt 0) {
        Write-Host "  OK: $withSpecialist picks have specialist flags" -ForegroundColor Green
    } else {
        Write-Host "  WARN: No specialist flags (may need re-run)" -ForegroundColor Yellow
    }
    
    # Show archetype distribution
    Write-Host "`n  Archetype Distribution:" -ForegroundColor Cyan
    $archetypes = $picks | Where-Object { $_.nba_role_archetype } | Group-Object nba_role_archetype
    foreach ($arch in $archetypes) {
        Write-Host "    $($arch.Name): $($arch.Count) picks" -ForegroundColor White
    }
    
    # Show specialist flags if present
    if ($withSpecialist -gt 0) {
        Write-Host "`n  Specialist Flags Sample:" -ForegroundColor Cyan
        $picks | Where-Object { $_.nba_specialist_flags } | Select-Object -First 5 | ForEach-Object {
            Write-Host "    $($_.player) - $($_.stat): $($_.nba_specialist_flags -join ', ')" -ForegroundColor White
        }
    }
} else {
    Write-Host "  WARN: No output files found - run analysis first" -ForegroundColor Yellow
}

# Test 4: Check menu integration
Write-Host "`n[TEST 4] Checking menu integration..." -ForegroundColor Yellow
$menuContent = Get-Content "menu.py" -Raw

if ($menuContent -match "run_nba_role_filter") {
    Write-Host "  OK: run_nba_role_filter function found" -ForegroundColor Green
} else {
    Write-Host "  FAIL: run_nba_role_filter function not found" -ForegroundColor Red
}

if ($menuContent -match "\[L\]" -and $menuContent -match "NBA Role Layer Filter") {
    Write-Host "  OK: [L] menu option found" -ForegroundColor Green
} else {
    Write-Host "  FAIL: [L] menu option not found" -ForegroundColor Red
}

# Summary
Write-Host "`n" + ("="*70) -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host ("="*70) -ForegroundColor Cyan

if ($filesOK -and $specialistsOK -and $withArchetype -gt 0) {
    Write-Host "STATUS: SYSTEM READY" -ForegroundColor Green
    Write-Host "All critical components are in place and working." -ForegroundColor Green
} else {
    Write-Host "STATUS: NEEDS ATTENTION" -ForegroundColor Yellow
    if (-not $filesOK) {
        Write-Host "  - Some files are missing" -ForegroundColor Red
    }
    if (-not $specialistsOK) {
        Write-Host "  - Specialist detection incomplete" -ForegroundColor Red
    }
    if ($withArchetype -eq 0) {
        Write-Host "  - No NBA Role Layer data in output (re-run analysis)" -ForegroundColor Yellow
    }
}

Write-Host "`nNext Steps:" -ForegroundColor Cyan
if ($withSpecialist -eq 0) {
    Write-Host "  1. Re-run analysis to populate specialist flags" -ForegroundColor Yellow
    Write-Host "     Menu -> [2] -> Press Enter" -ForegroundColor White
}
Write-Host "  2. Test filter with Menu -> [L]" -ForegroundColor White
Write-Host "  3. Try filter option [7] for specialist picks" -ForegroundColor White

Write-Host "`n"
