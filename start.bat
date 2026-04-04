@echo off
echo ============================================
echo   CRYPTO AGENT TRADING ARENA - 24/7 MODE
echo ============================================
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.12+
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import ccxt, pandas, numpy, apscheduler" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting 24/7 Arena Engine...
echo Press Ctrl+C to stop gracefully
echo.

:loop
python run_247.py

if errorlevel 1 (
    echo.
    echo ERROR: Arena engine crashed with error code %errorlevel%
    echo Check logs/crash_log.jsonl for details
    echo.
    echo Restarting in 30 seconds...
    timeout /t 30 /nobreak >nul
    goto loop
)

echo.
echo Arena engine stopped.
pause
