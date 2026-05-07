@echo off
chcp 65001 > nul
echo ====================================================
echo   🛡️ BHARAT ALGOVERSE v3.0 - STABLE RESTORATION
echo ====================================================
echo.

echo [1/2] Pushing Stable V3 Master Code...
git add .
git commit -m "🛡️ STABLE V3 RESTORED: Pure Buying | 5M | 6 Lots"
git push origin main_temp:main -f
echo.

echo [2/2] Nuclear Reset on VPS and Deploying V3...
ssh -o StrictHostKeyChecking=no root@46.224.133.16 "pkill -9 -f streamlit ; pkill -9 -f python ; rm -rf /root/BHARAT-BUYING* ; rm -rf /root/BHARAT-SELLING* ; cd /root/BHARAT-ALGO-TRADING-APP && git fetch --all && git reset --hard origin/main && git pull origin main && chmod +x deploy_single.sh && bash deploy_single.sh"

echo.
echo ✅ V3 STABLE RESTORATION COMPLETE!
echo.
pause
