@echo off
echo [1/3] Killing ALL background python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
echo [2/3] Clearing lock files...
del /Q bot_running.lock 2>nul
timeout /t 2 /nobreak >nul
echo [3/3] Launching BTC ALGO V5.5 (main.py ONLY)...
python main.py
pause
