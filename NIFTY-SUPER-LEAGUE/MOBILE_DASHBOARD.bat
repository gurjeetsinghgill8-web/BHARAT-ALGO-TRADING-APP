@echo off
title 🏆 NSL — MOBILE DASHBOARD (Internet Access)
color 0B

echo.
echo  ============================================================
echo    🏆  NIFTY SUPER LEAGUE — MOBILE DASHBOARD LAUNCHER
echo  ============================================================
echo    Opens dashboard accessible from ANY device, anywhere.
echo    Share the URL with your phone - works WITHOUT laptop WiFi!
echo  ============================================================
echo.

cd /d "%~dp0"

:: Kill any existing streamlit on 8502
echo [1/3] Clearing port 8502...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| find ":8502 " ^| find "LISTEN"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: Start Streamlit dashboard in background (minimized)
echo [2/3] Starting dashboard on port 8502...
start "NSL Dashboard" /MIN python -m streamlit run nsl_dashboard.py ^
    --server.port 8502 ^
    --server.headless true ^
    --server.address localhost ^
    --browser.gatherUsageStats false

:: Wait for streamlit to be ready
echo     Waiting for dashboard to start...
timeout /t 12 /nobreak >nul

echo.
echo  ============================================================
echo   INSTRUCTIONS FOR MOBILE:
echo   1. Wait for the PUBLIC URL below (ends in trycloudflare.com)
echo   2. Open that URL on your PHONE in Chrome
echo   3. Chrome menu (3 dots) -> "Add to Home Screen"
echo   4. Works like a native APP!
echo   5. URL changes each time you run this - share fresh URL
echo  ============================================================
echo.
echo [3/3] Starting Cloudflare tunnel... (URL appears in 5-10 sec)
echo.

:: Use local cloudflared.exe
cloudflared.exe tunnel --url http://localhost:8502

echo.
echo  Tunnel stopped. Dashboard is no longer accessible from mobile.
pause
