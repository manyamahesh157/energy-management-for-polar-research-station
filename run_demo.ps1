# PolarSync AI - 1-Click PowerShell Runner
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "               POLARSYNC AI - SMART POLAR ENERGY MANAGEMENT SYSTEM" -ForegroundColor Yellow
Write-Host "            Smart India Hackathon 2026 | Problem Statement: SIH26061" -ForegroundColor Green
Write-Host "                 NCPOR, Ministry of Earth Sciences | Team: anvaya" -ForegroundColor White
Write-Host "===============================================================================" -ForegroundColor Cyan

# 1. Run Tests
Write-Host "`n[1/3] Running Comprehensive Polar Test Suite..." -ForegroundColor Cyan
python tests/run_all_tests.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Test suite failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

# 2. Check Data
Write-Host "`n[2/3] Checking 8760h Polar Environment Dataset..." -ForegroundColor Cyan
if (!(Test-Path "backend/data/polar_year_8760.csv")) {
    Write-Host "Synthesizing 8760-hour Antarctic dataset (~70°S)..." -ForegroundColor Yellow
    python -m backend.data_generator
} else {
    Write-Host "[OK] Antarctic 8760-hour baseline verified." -ForegroundColor Green
}

# 3. Launch Dashboard
Write-Host "`n[3/3] Launching PolarSync AI Dashboard on http://localhost:8501..." -ForegroundColor Green
Start-Process "http://localhost:8501"
python -m streamlit run frontend/app.py --server.port 8501
