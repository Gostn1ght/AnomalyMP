@echo off
rem Lost Zone: writes fsgame.ltx for the folder this file is in, then starts the game.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$r = (Get-Location).Path.TrimEnd('\') + '\'; (Get-Content -Raw -LiteralPath 'fsgame.template' -Encoding Default).Replace('{ROOT}', $r) | Set-Content -NoNewline -Encoding Default -LiteralPath 'fsgame.ltx'"
if errorlevel 1 (echo Cannot write fsgame.ltx & pause & exit /b 1)
if not exist "appdata\player" mkdir "appdata\player"
start "" "bin\LostZoneClientDX11.exe" -nosplashwindow -netcoop -noprefetch -fsltx fsgame.ltx
