@echo off
title NSL — DEPLOY TO VPS (Permanent Mobile Access)
color 0A
chcp 65001 >nul

echo.
echo  ============================================================
echo    NIFTY SUPER LEAGUE — DEPLOYING TO VPS
echo    After this: LAPTOP BAND KAR DO. Mobile se chalaao!
echo  ============================================================
echo.

set VPS_IP=46.224.133.16
set VPS_USER=root
set VPS_PASS=
set REMOTE_DIR=/root/nsl-engine
set LOCAL_DIR=C:\Users\pc\Desktop\gurjas ai\BHARAT ALGO-TRADING\NIFTY-SUPER-LEAGUE

echo VPS: %VPS_USER%@%VPS_IP%
echo Remote: %REMOTE_DIR%
echo.

REM Check if scp/ssh available
where scp >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: SCP not found. Using plink/pscp from BHARAT-FUTURES-ENGINE...
    set PSCP=C:\Users\pc\Desktop\gurjas ai\BHARAT-FUTURES-ENGINE\pscp.exe
    set PLINK=C:\Users\pc\Desktop\gurjas ai\BHARAT-FUTURES-ENGINE\plink.exe
    goto :use_pscp
)
set PSCP=scp
set PLINK=ssh

:use_pscp

echo [1/5] Uploading NSL engine files to VPS...
echo.

REM Upload all NSL files
"%PSCP%" -r -pw "%VPS_PASS%" "%LOCAL_DIR%\*" %VPS_USER%@%VPS_IP%:%REMOTE_DIR%/

echo.
echo [2/5] Files uploaded!
echo.

echo [3/5] Running VPS setup script...
echo.

REM Run setup on VPS via SSH
"%PLINK%" -pw "%VPS_PASS%" -batch %VPS_USER%@%VPS_IP% "bash /root/nsl-engine/vps_setup.sh"

echo.
echo [4/5] Setup complete!
echo.

echo [5/5] Getting dashboard URL...
"%PLINK%" -pw "%VPS_PASS%" -batch %VPS_USER%@%VPS_IP% "echo Dashboard: http://%VPS_IP%:8502 && systemctl is-active nsl_engine && systemctl is-active nsl_dashboard"

echo.
echo  ============================================================
echo   DONE! Dashboard is LIVE at:
echo   http://%VPS_IP%:8502
echo.
echo   Save this URL in your phone Chrome.
echo   Tap menu (3 dots) - Add to Home Screen - Done!
echo.
echo   LAPTOP BAND KAR SAKTE HO ABHI!
echo  ============================================================
echo.
pause
