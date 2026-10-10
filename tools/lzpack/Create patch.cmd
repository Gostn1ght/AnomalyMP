@echo off
cd /d "%~dp0"
set "patchSource=%~1"
set "patchVersion=%~2"
if not defined patchSource set /p "patchSource=Patch source folder: "
if not defined patchVersion set /p "patchVersion=Unique six-digit version (000001): "
if not defined patchSource exit /b 1
if not defined patchVersion exit /b 1
py -3 "%~dp0lzpack.py" patch --key "%~dp0private\lzpack-v1.key" --input "%patchSource%" --output "%~dp0Patches" --version "%patchVersion%" --role both
if errorlevel 1 (echo Patch build failed. & pause & exit /b 1)
echo Copy Patches\client\*.db0 to the players' db\lostzone_updates.
echo Copy Patches\server\*.db0 to the server's db\lostzone_updates.
echo Restart the affected client/server after installing the patch.
pause
