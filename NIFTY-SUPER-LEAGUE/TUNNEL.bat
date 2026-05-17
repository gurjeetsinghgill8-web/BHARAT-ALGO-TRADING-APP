@echo off
title NSL TUNNEL — VPS Proxy
color 0B
echo.
echo  ============================================================
echo    NSL TUNNEL — Routing traffic through VPS 46.224.133.16
echo    KEEP THIS WINDOW OPEN while trading!
echo  ============================================================
echo.
cd /d "%~dp0"
python NSL_TUNNEL.py
echo.
pause
