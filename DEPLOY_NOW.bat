@echo off
chcp 65001 > nul
echo ====================================================
echo   BHARAT ALGOVERSE v3.0 - ONE-CLICK DEPLOY TOOL
echo ====================================================
echo.

echo [1/3] Pushing latest code to GitHub...
git add .
git commit -m "Auto-deploy: v3.0 update [%date% %time%]"
git push origin main_temp:main -f
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Git push had issues. Continuing with SSH deploy...
)
echo.

echo [2/3] Connecting to VPS and deploying...
echo (Password NOT needed if SETUP_PASSWORDLESS_LOGIN.bat was run once)
echo.
ssh -o StrictHostKeyChecking=no root@46.224.133.16 "cd ~ && [ -d BHARAT-ALGO-TRADING-APP ] && cd BHARAT-ALGO-TRADING-APP || mkdir -p BHARAT-ALGO-TRADING-APP && cd BHARAT-ALGO-TRADING-APP && git fetch --all && git reset --hard origin/main && git pull origin main && chmod +x vps_setup_dual.sh && bash vps_setup_dual.sh"

echo.
echo [3/3] Deployment Complete!
echo.
echo ====================================================
echo   LIVE LINKS:
echo   Buying Dashboard : http://46.224.133.16:8501
echo   Selling Dashboard: http://46.224.133.16:8502
echo ====================================================
echo.
pause
