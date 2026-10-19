@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Lost Zone - мастер мира
if exist "UPDATING.lock" (
  echo Идёт обновление Lost Zone, дождитесь окончания.
  pause
  exit /b 1
)
if not exist "hoster\netcoop_master_control.ps1" (
  echo Не найден запуск мастера. Скопируйте папку сервера целиком.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "hoster\netcoop_unblock_launch.ps1" -RuntimeRoot "%~dp0."
if errorlevel 1 (
  echo Cannot prepare server launch files. See the error above.
  pause
  exit /b 1
)
if not exist "appdata\server" mkdir "appdata\server"
if not exist "appdata\server\netcoop_cluster.ltx" copy "hoster\netcoop_cluster.ltx.six" "appdata\server\netcoop_cluster.ltx" >nul
rem The master in the engine (owner 2026-10-19): the server executable with
rem -netcoop_master opens its own window; the panel stays for the maps.
if exist "dedicated\sqlite3.dll" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "hoster\netcoop_master_control.ps1" -MasterRoot "%~dp0." -StartMaster
  if errorlevel 1 ( pause & exit /b 1 )
  exit /b 0
)
rem Older folders: the master window of the location panel (owner 2026-10-17).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "hoster\netcoop_cluster_panel.ps1" -Runtime "%~dp0." -StartMaster -Tab console
if errorlevel 1 (
  echo Мастер не запустился. Проверьте сообщение выше.
  pause
  exit /b 1
)
exit /b 0
