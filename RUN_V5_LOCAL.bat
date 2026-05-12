@echo off
echo [SYSTEM] Killing ALL python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 3 /nobreak >nul
del /Q bot_running.lock 2>nul
echo [SYSTEM] Starting V5.4 Safe Mode...
python main.py
pause
