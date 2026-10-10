@echo off
rem Lost Zone server: give or take admin rights (hoster\netcoop_account_role.ps1).
rem The player registers on the server first; the role applies on the next login.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hoster\netcoop_account_role.ps1" -Runtime "%~dp0." -List
echo.
set "LZ_LOGIN="
set /p "LZ_LOGIN=Login (empty = exit): "
if not defined LZ_LOGIN exit /b 0
set "LZ_ROLE=admin"
set /p "LZ_ROLE=Role admin or player [admin]: "
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hoster\netcoop_account_role.ps1" -Runtime "%~dp0." -Login "%LZ_LOGIN%" -Role "%LZ_ROLE%"
pause
