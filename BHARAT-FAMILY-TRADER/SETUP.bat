@echo off
title BHARAT AI ALGO TRADER v5.2 - Setup
color 0A
echo.
echo ============================================================
echo    BHARAT AI ALGO TRADER v5.2
echo    Welcome! Setting up your trading bot...
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python from: https://www.python.org/downloads/
    echo  - Click "Download Python"
    echo  - During install: CHECK "Add Python to PATH"
    pause
    exit
)

echo [OK] Python found!
echo.
echo Installing required libraries... (this may take 2-3 minutes)
echo Please wait...
echo.

pip install streamlit pandas requests python-dotenv pyotp --quiet
pip install pandas-ta --quiet

echo.
echo ============================================================
echo    SETUP COMPLETE!
echo.
echo    Next Step: Double-click START.bat to launch your bot
echo ============================================================
echo.
pause
