@echo off
TITLE PolarSync AI - Smart Energy Management System (SIH26061)
color 0B

echo ===============================================================================
echo                POLARSYNC AI - SMART POLAR ENERGY MANAGEMENT SYSTEM
echo             Smart India Hackathon 2026 ^| Problem Statement: SIH26061
echo                  NCPOR, Ministry of Earth Sciences ^| Team: anvaya
echo ===============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Running Comprehensive Test Suite...
python tests/run_all_tests.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Unit test suite failed. Please check dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Checking 8760h Polar Environment Dataset...
if not exist "backend\data\polar_year_8760.csv" (
    echo Synthesizing 8760-hour Antarctic dataset (~70S)...
    python -m backend.data_generator
) else (
    echo [OK] Antarctic 8760-hour baseline verified.
)

echo.
echo [3/3] Launching PolarSync AI Cockpit Dashboard...
echo Opening browser at http://localhost:8501
start http://localhost:8501

python -m streamlit run frontend/app.py --server.port 8501 --server.headless false

pause
