@echo off
cd /d "%~dp0"
start "" "dedicated\LostZoneServerDX11.exe" -nosplashwindow -netcoop -netcoop_world=lostzone -netcoop_chunk_shadow -dbg -multi_instance -logname hideout_srv -fsltx fsgame_server.ltx -netport 1277 -netcoop_start_location=hidden_base -start "server(all/single/alife/new/portsv=1277/maxplayers=2)" "client(localhost/name=serverauthority/port=1277/portcl=1278)"
