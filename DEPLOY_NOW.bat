@echo off
chcp 65001 > nul
echo ====================================================
echo   🚀 BHARAT ALGO-PRO - SINGLE BOT DEPLOY TOOL
echo ====================================================
echo.

echo [1/2] Pushing latest SINGLE-BOT code to GitHub...
git add .
git commit -m "🚀 Single-Bot Reset: 5M Buying | 6 Lots [%date% %time%]"
git push origin main_temp:main -f
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Git push had issues. Continuing with SSH deploy...
)
echo.

echo [2/2] Connecting to VPS and performing DEEP RESET...
echo (Switching to SINGLE-BOT Architecture)
echo.
ssh -o StrictHostKeyChecking=no root@46.224.133.16 "if [ ! -d BHARAT-ALGO-TRADING-APP ]; then git clone https://github.com/gurjeetsinghgill8-web/BHARAT-ALGO-TRADING-APP.git; fi; cd BHARAT-ALGO-TRADING-APP && git fetch --all && git reset --hard origin/main && git pull origin main && chmod +x deploy_single.sh && bash deploy_single.sh"

echo.
echo ✅ SINGLE-BOT Deployment Complete!
echo.
echo ====================================================
echo   LIVE LINK:
echo   Dashboard : http://46.224.133.16:8501
echo ====================================================
echo.
pause
