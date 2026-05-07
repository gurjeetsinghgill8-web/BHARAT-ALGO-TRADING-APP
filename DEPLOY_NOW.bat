@echo off
:: BHARAT ALGO-PRO - SINGLE BOT DEPLOY TOOL
:: Cleaned version for Windows Compatibility

echo ====================================================
echo   BHARAT ALGO-PRO - SINGLE BOT DEPLOY TOOL
echo ====================================================
echo.

echo [1/2] Pushing latest code to GitHub...
git add .
git commit -m "Single-Bot Reset: 5M Buying 6 Lots"
git push origin main_temp:main -f
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Git push had issues. Continuing with SSH deploy...
)
echo.

echo [2/2] Connecting to VPS and performing DEEP RESET...
ssh -o StrictHostKeyChecking=no root@46.224.133.16 "cd /root/BHARAT-ALGO-TRADING-APP && git fetch --all && git reset --hard origin/main && git pull origin main && chmod +x deploy_single.sh && bash deploy_single.sh"

echo.
echo Deployment Complete!
echo.
echo ====================================================
echo   LIVE LINK:
echo   Dashboard : http://46.224.133.16:8501
echo ====================================================
echo.
pause
