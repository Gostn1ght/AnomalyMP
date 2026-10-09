@echo off
cd /d "%~dp0"
if not exist "appdata\server" mkdir "appdata\server"
if not exist "appdata\server\netcoop_cluster.ltx" copy "hoster\netcoop_cluster.ltx.full" "appdata\server\netcoop_cluster.ltx" >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hoster\netcoop_cluster_panel.ps1" -Runtime "%~dp0."
if errorlevel 1 pause
