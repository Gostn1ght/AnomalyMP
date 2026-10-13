@echo off
setlocal
cd /d "%~dp0"
echo Approve a registered account. Its player/admin role is preserved.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hoster\netcoop_account_role.ps1" -Runtime "%~dp0." -List
if errorlevel 1 goto :failed
echo.
set "LZ_LOGIN="
set /p "LZ_LOGIN=Account login (empty = exit): "
if not defined LZ_LOGIN exit /b 0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hoster\netcoop_account_role.ps1" -Runtime "%~dp0." -Login "%LZ_LOGIN%" -Approve
if errorlevel 1 goto :failed
echo Ask the player to retry login.
pause
exit /b 0
:failed
echo Registration was not approved. Read the error above.
pause
exit /b 1
