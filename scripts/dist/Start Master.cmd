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
if not exist "appdata\server" mkdir "appdata\server"
if not exist "appdata\server\netcoop_cluster.ltx" copy "hoster\netcoop_cluster.ltx.six" "appdata\server\netcoop_cluster.ltx" >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "hoster\netcoop_master_control.ps1" -MasterRoot "%~dp0." -StartMaster
if errorlevel 1 (
  echo Мастер не запустился. Проверьте сообщение выше.
  pause
  exit /b 1
)
exit /b 0
