# Keeps every location server of the cluster running: a server that exits
# or crashes is started again after 10 s. Run from the GAMMA runtime folder:
#   powershell -ExecutionPolicy Bypass -File netcoop_cluster_watchdog.ps1
# Each entry: map name for the log, port, start location, persistent world.
param([string]$Runtime = $PSScriptRoot)
$ErrorActionPreference = "Stop"
$servers = @(
    @{ Name = "marsh";  Port = 1267; Start = "hidden_base";    World = "zone" },
    @{ Name = "escape"; Port = 1277; Start = "rookie_village"; World = "zone_escape" }
)
$exe = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
if (-not (Test-Path $exe)) { throw "missing $exe" }

function Start-Location($s) {
    $log = if ($s.Name -eq "marsh") { "srv" } else { "srv_$($s.Name)" }
    $arguments = "-nosplashwindow -netcoop -dbg -multi_instance -logname $log -fsltx fsgame_server.ltx " +
        "-netport $($s.Port) -netcoop_start_location=$($s.Start) -netcoop_world=$($s.World) " +
        "-start `"server(all/single/alife/new/portsv=$($s.Port)/maxplayers=16)`" " +
        "`"client(localhost/name=serverauthority/port=$($s.Port)/portcl=$($s.Port + 1))`""
    $p = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
    Write-Host ("{0:HH:mm:ss} started {1} (port {2}, pid {3})" -f (Get-Date), $s.Name, $s.Port, $p.Id)
    return $p
}

$running = @{}
foreach ($s in $servers) { $running[$s.Name] = Start-Location $s; Start-Sleep -Seconds 5 }
while ($true) {
    Start-Sleep -Seconds 10
    foreach ($s in $servers) {
        $p = $running[$s.Name]
        if ($p.HasExited) {
            Write-Host ("{0:HH:mm:ss} {1} exited with code {2}; restarting" -f (Get-Date), $s.Name, $p.ExitCode)
            $running[$s.Name] = Start-Location $s
        }
    }
}
