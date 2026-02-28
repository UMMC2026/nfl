Set-Location -Path $PSScriptRoot

if (Test-Path ".\.venv\Scripts\python.exe") {
    # Default to the main menu (includes Auto-Scrape workflow).
    # Usage:
    #   .\run_menu.ps1            -> menu.py
    #   .\run_menu.ps1 risk       -> risk_first_slate_menu.py
    $target = ".\menu.py"
    if ($args.Count -ge 1) {
        $mode = $args[0].ToString().ToLowerInvariant()
        if ($mode -in @("risk", "riskfirst", "ascii")) {
            $target = ".\risk_first_slate_menu.py"
        }
    }

    & ".\.venv\Scripts\python.exe" $target
    exit $LASTEXITCODE
}

Write-Host "ERROR: .venv\Scripts\python.exe not found." -ForegroundColor Red
Write-Host "- Create the venv (.venv) and install requirements." 
Write-Host "- Or run with your interpreter: python menu.py"
Pause
