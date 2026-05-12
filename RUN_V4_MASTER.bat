@echo off
chcp 65001 > nul
echo ====================================================
echo   BHARAT ALGOVERSE v4.0 - MASTER STABLE ENGINE
echo   Sealed: 2026-05-07 ^| Ground Truth Version
echo ====================================================
echo.

echo [1/5] Killing ALL background python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo [2/5] Clearing lock files...
del /Q "%~dp0bot_running.lock" 2>nul
timeout /t 1 /nobreak >nul

echo [3/5] Checking secrets.txt...
if not exist "%~dp0VERSION_4_0_MASTER_STABLE\secrets.txt" (
    if exist "%~dp0secrets.txt" (
        copy "%~dp0secrets.txt" "%~dp0VERSION_4_0_MASTER_STABLE\secrets.txt" >nul
        echo    secrets.txt auto-copied from root folder.
    ) else (
        echo    WARNING: secrets.txt not found. Please create it in VERSION_4_0_MASTER_STABLE folder.
        echo    Required format:
        echo      DELTA_API_KEY=...
        echo      DELTA_API_SECRET=...
        echo      TELEGRAM_TOKEN=...
        echo      TELEGRAM_CHAT_ID=...
        pause
        exit /b 1
    )
) else (
    echo    secrets.txt already present. OK.
)

echo [4/5] Copying crypto_roller dependency...
if not exist "%~dp0VERSION_4_0_MASTER_STABLE\crypto_roller.py" (
    copy "%~dp0crypto_roller.py" "%~dp0VERSION_4_0_MASTER_STABLE\crypto_roller.py" >nul
)

echo [5/5] Launching BHARAT V4.0 MASTER ENGINE...
echo.
echo   ✅ Clean Slate Enforcement : ON
echo   ✅ Stop Loss @ 40%%        : ON
echo   ✅ Take Profit @ 100%%     : ON + Auto-Reinvest
echo   ✅ Multi-Strike Support    : ON
echo   ✅ Multi-Timeframe         : ON
echo.
cd /d "%~dp0VERSION_4_0_MASTER_STABLE"
set PYTHONUTF8=1
python main.py
pause
