@echo off
title BHARAT AI ALGO TRADER v5.2
color 0A
echo.
echo ============================================================
echo    BHARAT AI ALGO TRADER v5.2 - Starting...
echo ============================================================
echo.
echo Starting Dashboard in your browser...
echo (A new window will open automatically)
echo.
echo DO NOT close this black window while the bot is running!
echo.
start "" python main_engine.py
timeout /t 3 /nobreak >nul
start "" streamlit run dashboard.py --server.port 8502 --server.headless false
echo.
echo ============================================================
echo    Bot is RUNNING!
echo    Dashboard: http://localhost:8502
echo.
echo    To STOP: Close this window
echo ============================================================
echo.
pause
