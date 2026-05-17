@echo off
title 🏆 NIFTY SUPER LEAGUE — ENGINE
color 0A

echo.
echo  ============================================================
echo   🏆  NIFTY SUPER LEAGUE  v1.0  —  ENGINE LAUNCHER
echo  ============================================================
echo   Strategy  : Nifty 50 Options BUYING (Intraday)
echo   Signal    : 9:16 AM Anchor — CALL / PUT
echo   Candle    : Previous closed 5-min candle ONLY
echo   Expiry    : Always NEXT WEEK Thursday
echo   Strike    : Premium ₹100-₹120 range (highest)
echo   Exit Rule : +50%% TP | Signal Flip | 15:15 Force Close
echo  ============================================================
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Installing dependencies...
pip install -q requests pytz streamlit >nul 2>&1

echo.
echo Starting NIFTY SUPER LEAGUE Engine...
echo Press Ctrl+C to stop.
echo.

python nsl_engine.py

echo.
echo Engine stopped.
pause
