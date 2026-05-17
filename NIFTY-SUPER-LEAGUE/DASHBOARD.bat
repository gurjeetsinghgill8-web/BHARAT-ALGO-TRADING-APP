@echo off
title NSL DASHBOARD — Nifty Super League
color 0A
echo.
echo  ============================================================
echo    NSL DASHBOARD — Opening on ALL devices (laptop + mobile)
echo  ============================================================
echo.
cd /d "%~dp0"

:: Find local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "169.254"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo  Laptop : http://localhost:8502
echo  Mobile : http://%IP%:8502
echo.
echo  Make sure mobile and laptop are on SAME WiFi!
echo  ============================================================
echo.
python -m streamlit run nsl_dashboard.py --server.port 8502 --server.address 0.0.0.0 --server.headless true
pause
