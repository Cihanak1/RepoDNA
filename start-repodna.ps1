# RepoDNA v0.7.0 — Repository Intelligence Platform Quick Launcher
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  RepoDNA v0.7.0 — Repository Intelligence Platform" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCmd = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "[INFO] Using virtual environment (.venv)..." -ForegroundColor Green
    $pythonCmd = ".venv\Scripts\python.exe"
} else {
    Write-Host "[INFO] Virtual environment not found, using system Python..." -ForegroundColor Yellow
}

Write-Host "[INFO] Starting RepoDNA Intelligence Server and Workstation UI..." -ForegroundColor Green
& $pythonCmd -m repodna.cli.main start --open-browser
