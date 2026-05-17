@echo off
title NSL Auto Login
color 0A
echo.
echo  ============================================================
echo    NIFTY SUPER LEAGUE - Auto Token Refresh
echo    (Run this every morning before starting engine)
echo  ============================================================
echo.
cd /d "%~dp0"
python NSL_AUTO_LOGIN.py
echo.
pause
