@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Lost Zone - запуск локаций

rem Запасной запуск без панели: мастер мира, затем основные карты по очереди.
rem Каждая карта в своём окне; закрыть окно карты = остановить её.
rem Миры, аккаунты и персонажи в appdata\server не трогаются.

if exist "UPDATING.lock" (
  echo Идёт обновление Lost Zone, дождитесь окончания.
  pause
  exit /b 1
)
if not exist "dedicated\LostZoneServerDX11.exe" (
  echo Не найден dedicated\LostZoneServerDX11.exe - папка сервера скопирована не целиком.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$r = (Get-Location).Path.TrimEnd('\') + '\'; (Get-Content -Raw -LiteralPath 'fsgame_server.template' -Encoding Default).Replace('{ROOT}', $r) | Set-Content -NoNewline -Encoding Default -LiteralPath 'fsgame_server.ltx'"
if errorlevel 1 (
  echo Не удалось записать fsgame_server.ltx
  pause
  exit /b 1
)
if not exist "appdata\server\logs" mkdir "appdata\server\logs"
if not exist "appdata\server\netcoop_cluster.ltx" copy "hoster\netcoop_cluster.ltx.six" "appdata\server\netcoop_cluster.ltx" >nul

rem Без мастера карты не пускают игроков: он ведёт календарь, погоду и выбросы.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "hoster\netcoop_master_control.ps1" -MasterRoot "%~dp0." -StartMaster
if errorlevel 1 (
  echo Мастер мира не запустился - карты не будут пускать игроков.
  pause
  exit /b 1
)

set "WAIT=60"
call :start_map Болота               k00_marsh            1267 hidden_base             zone                      srv
call :start_map Кордон               l01_escape           1277 rookie_village          zone_escape               srv_l01_escape
call :start_map Свалка               l02_garbage          1307 train_hangar            zone_l02_garbage          srv_l02_garbage
call :start_map Луга                 y04_pole             1339 lz_y04_pole             zone_y04_pole             srv_y04_pole
call :start_map Бар                  l05_bar              1313 makeshift_barracks      zone_l05_bar              srv_l05_bar
call :start_map Агропром             l03_agroprom         1309 research_institute      zone_l03_agroprom         srv_l03_agroprom
call :start_map Подземелья_Агропрома l03u_agr_underground 1345 lz_l03u_agr_underground zone_l03u_agr_underground srv_l03u_agr_underground

echo.
echo Все основные локации запущены. Остальные - из панели (Start Server Panel.cmd).
echo Логи: appdata\server\logs
pause
exit /b 0

:start_map
rem %1 название, %2 карта, %3 порт, %4 стартовая точка, %5 мир, %6 имя лога
set /a PORTCL=%3+1
echo [%time:~0,8%] Запуск: %1 (порт %3)
start "LZ %2 %3" /belownormal "dedicated\LostZoneServerDX11.exe" -nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname %6 -fsltx fsgame_server.ltx -netport %3 -netcoop_start_location=%4 -netcoop_world=%5 -netcoop_hibernate=120 -start "server(all/single/alife/new/portsv=%3/maxplayers=129)" "client(localhost/name=serverauthority/port=%3/portcl=%PORTCL%)"
echo           жду %WAIT% с, пока карта загрузится...
timeout /t %WAIT% /nobreak >nul
exit /b 0
