@echo off
title 🔑 NSL Token Refresh
color 0E

echo.
echo  ============================================================
echo   🔑  NIFTY SUPER LEAGUE — DAILY TOKEN REFRESH
echo  ============================================================
echo   Run this ONCE every morning before starting the engine.
echo  ============================================================
echo.

cd /d "%~dp0"

python REFRESH_TOKEN.py

echo.
pause
