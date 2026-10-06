# Location cluster watchdog: runs this machine's location servers and starts
# again any that exits. The plan is appdata\server\netcoop_cluster.ltx
# ([locations] map = host:port, [launch] map = start section, [cluster]
# per_server); a map belongs to this machine when its host is one of its
# addresses (or 127.0.0.1/localhost). Servers start one after another: a
# loading server briefly needs ~6 GB.
#   powershell -ExecutionPolicy Bypass -File netcoop_cluster_watchdog.ps1 [-Maps k00_marsh,l01_escape]
param(
    [string]$Runtime = $PSScriptRoot,
    [string[]]$Maps = @(),
    [int]$LoadTimeoutSeconds = 600
)
$ErrorActionPreference = "Stop"
$exe = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$planPath = Join-Path $Runtime "appdata\server\netcoop_cluster.ltx"
if (-not (Test-Path $exe)) { throw "missing $exe" }
if (-not (Test-Path $planPath)) { throw "missing $planPath (copy scripts\netcoop-cluster\netcoop_cluster.ltx.full there)" }

# Minimal ltx reader: section -> ordered key/value pairs.
$plan = @{}; $section = $null
foreach ($line in Get-Content $planPath -Encoding Default) {
    $text = ($line -split ";", 2)[0].Trim()
    if ($text -match "^\[(.+)\]$") { $section = $Matches[1]; $plan[$section] = [ordered]@{}; continue }
    if ($section -and $text -match "^([^=]+?)\s*=\s*(.+)$") { $plan[$section][$Matches[1]] = $Matches[2] }
}
$perServer = if ($plan["cluster"] -and $plan["cluster"]["per_server"]) { [int]$plan["cluster"]["per_server"] } else { 128 }
$local = @("127.0.0.1", "localhost", $env:COMPUTERNAME.ToLower())
try { $local += (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | ForEach-Object { $_.IPAddress }) } catch {}

$servers = @()
foreach ($map in $plan["locations"].Keys) {
    if ($Maps.Count -and $Maps -notcontains $map) { continue }
    $address = $plan["locations"][$map]
    $hostName, $port = $address -split ":"
    if ($local -notcontains $hostName.ToLower()) { continue }
    $start = $plan["launch"][$map]
    if (-not $start) { Write-Host "skip $map`: no [launch] start section"; continue }
    # The first two servers keep the worlds they had before the full plan.
    $world = switch ($map) { "k00_marsh" { "zone" } "l01_escape" { "zone_escape" } default { "zone_$map" } }
    $servers += @{ Name = $map; Port = [int]$port; Start = $start; World = $world }
}
if (-not $servers.Count) { throw "no maps of this machine in $planPath" }

function Find-Log($s) {
    $log = if ($s.Name -eq "k00_marsh") { "srv" } else { "srv_$($s.Name)" }
    Get-ChildItem (Join-Path $Runtime "appdata\server\logs") -Filter "xray_$log`_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^xray_$([regex]::Escape($log))_[^_]+\.log$" } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Start-Location($s) {
    $log = if ($s.Name -eq "k00_marsh") { "srv" } else { "srv_$($s.Name)" }
    $arguments = "-nosplashwindow -netcoop -dbg -multi_instance -logname $log -fsltx fsgame_server.ltx " +
        "-netport $($s.Port) -netcoop_start_location=$($s.Start) -netcoop_world=$($s.World) " +
        "-start `"server(all/single/alife/new/portsv=$($s.Port)/maxplayers=$perServer)`" " +
        "`"client(localhost/name=serverauthority/port=$($s.Port)/portcl=$($s.Port + 1))`""
    $p = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
    Write-Host ("{0:HH:mm:ss} started {1} (port {2}, pid {3})" -f (Get-Date), $s.Name, $s.Port, $p.Id)
    # Wait until it runs (its clock line) before loading the next one.
    $since = Get-Date
    while (((Get-Date) - $since).TotalSeconds -lt $LoadTimeoutSeconds -and -not $p.HasExited) {
        $file = Find-Log $s
        if ($file -and $file.LastWriteTime -gt $since -and (Select-String -Path $file.FullName -Pattern "\[world\] saved \S+ \(bootstrap\)|loading saved world" -Quiet)) { break }
        Start-Sleep -Seconds 5
    }
    return $p
}

Write-Host ("{0} map(s) on this machine: {1}" -f $servers.Count, (($servers | ForEach-Object { $_.Name }) -join ", "))
$running = @{}
foreach ($s in $servers) { $running[$s.Name] = Start-Location $s }
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
