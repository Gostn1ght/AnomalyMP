@echo off
if exist "%~dp0UPDATING.lock" (echo Lost Zone update is in progress. & pause & exit /b 1)
rem Lost Zone server: writes fsgame_server.ltx for this folder and opens the
rem location panel (list of maps, start / stop / restart, automatic mode).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$r = (Get-Location).Path.TrimEnd('\') + '\'; (Get-Content -Raw -LiteralPath 'fsgame_server.template' -Encoding Default).Replace('{ROOT}', $r) | Set-Content -NoNewline -Encoding Default -LiteralPath 'fsgame_server.ltx'"
if errorlevel 1 (echo Cannot write fsgame_server.ltx & pause & exit /b 1)
if not exist "appdata\server" mkdir "appdata\server"
if not exist "appdata\server\netcoop_cluster.ltx" copy "hoster\netcoop_cluster.ltx.six" "appdata\server\netcoop_cluster.ltx" >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hoster\netcoop_cluster_panel.ps1" -Runtime "%~dp0."
if errorlevel 1 pause
