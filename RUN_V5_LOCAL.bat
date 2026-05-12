@echo off
echo [SYSTEM] Killing all old bot processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 3 /nobreak >nul
echo [SYSTEM] Starting BHARAT ALGO V5.3...
python main.py
pause
