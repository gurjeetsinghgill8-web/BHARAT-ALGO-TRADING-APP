@echo off
echo 🩺 BHARAT ALGOVERSE: AUTO-DEPLOYMENT TOOL 🩺
echo ------------------------------------------
echo.
echo [1/3] Pushing latest code to GitHub...
git add .
git commit -m "Auto-deploy update"
git push origin main_temp:main -f
echo.
echo [2/3] Connecting to Hostasia VPS (46.224.133.16)...
echo IMPORTANT: When prompted, please type your VPS password.
echo.
ssh -t root@46.224.133.16 "cd ~/BHARAT-ALGO-TRADING-APP && git pull origin main && chmod +x vps_setup.sh && ./vps_setup.sh"
echo.
echo [3/3] Deployment Finished!
echo Check your Dashboard at: http://46.224.133.16:8501
echo.
pause
