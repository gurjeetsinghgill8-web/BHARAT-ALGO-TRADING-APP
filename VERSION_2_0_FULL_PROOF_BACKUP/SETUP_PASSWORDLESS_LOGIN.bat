@echo off
echo 🔐 BHARAT ALGOVERSE: PASSWORD-LESS SETUP 🔐
echo ------------------------------------------
echo.
echo [1/2] Generating your Secure Key...
if not exist "%USERPROFILE%\.ssh\id_rsa" (
    ssh-keygen -t rsa -b 4096 -f "%USERPROFILE%\.ssh\id_rsa" -N ""
) else (
    echo Key already exists.
)

echo.
echo [2/2] Connecting to VPS to save your key...
echo.
echo !!! IMPORTANT !!!
echo Aapko ek aakhiri baar password dena padega. 
echo Iske baad ye file apne aap aapke password ko yaad rakhegi (SSH Key ke zariye).
echo.

set PUB_KEY=
for /f "delims=" %%i in ('type "%USERPROFILE%\.ssh\id_rsa.pub"') do set PUB_KEY=%%i

ssh root@46.224.133.16 "mkdir -p ~/.ssh && echo %PUB_KEY% >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"

echo.
echo ✅ SETUP COMPLETE! 
echo Ab aap 'DEPLOY_NOW.bat' ko bina password ke chala sakte hain.
echo.
pause
