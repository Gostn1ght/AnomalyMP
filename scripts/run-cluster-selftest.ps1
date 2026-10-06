# Location cluster soak test (doc 43 H12) with the real game binaries.
#
# Two dedicated servers (Great Swamp, Cordon) and one client process with
# headless bots run from the GAMMA runtime with their own app data folders
# (appdata\selftest, appdata\selftest_bots): the owner's world, accounts and
# characters are not touched. With -netcoop_cluster_selftest every bot goes
# through a level changer to the other server 20 s after it appears there.
#
#   powershell -File scripts\run-cluster-selftest.ps1 -Runtime ..\gamma-runtime -Bots 4 -Minutes 10
#
# The summary counts handoffs, arrivals, refusals and errors in the logs.
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$Bots = 4,
    [int]$Minutes = 10,
    [int]$LoadTimeoutMinutes = 15,
    # Maps of the cluster under test (start sections from the cluster plan);
    # bots join the first one and walk the level changers from there.
    [string[]]$Maps = @("k00_marsh", "l01_escape"),
    # Load test: only the Great Swamp server, no cluster, bots stay there.
    [switch]$LoadOnly,
    # Load test on every map of -Maps at once: -Bots players on each, all in
    # one spot of their map (512 = 4 maps x 128).
    [switch]$Spread
)
$ErrorActionPreference = "Stop"
# "-Maps a,b" through -File arrives as one string.
$Maps = @($Maps | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$client = Join-Path $Runtime "bin\LostZoneClientDX11.exe"
foreach ($file in @($server, $client, (Join-Path $Runtime "fsgame_selftest_server.ltx"), (Join-Path $Runtime "fsgame_selftest_bots.ltx"))) {
    if (-not (Test-Path $file)) { throw "missing $file" }
}
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
# Every run starts a fresh world, accounts and characters of its own.
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx", "logs") } |
    Remove-Item -Recurse -Force
Remove-Item (Join-Path $Runtime "appdata\selftest_bots\logs") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $logs | Out-Null
if ($Spread) { $LoadOnly = $true }
elseif ($LoadOnly) { $Maps = @($Maps[0]) }
# The server counts its own local client as a player.
$maxPlayers = [Math]::Max(32, $Bots + 1)
# Start sections from the generated plan (GAMMA or netcoop\start_levels.ltx).
$launch = @{}; $section = $null
foreach ($line in Get-Content (Join-Path $PSScriptRoot "netcoop-cluster\netcoop_cluster.ltx.full")) {
    $text = ($line -split ";", 2)[0].Trim()
    if ($text -match "^\[(.+)\]$") { $section = $Matches[1]; continue }
    if ($section -eq "launch" -and $text -match "^(\S+)\s*=\s*(\S+)$") { $launch[$Matches[1]] = $Matches[2] }
}
$ports = @{}; $i = 0
foreach ($map in $Maps) { if (-not $launch[$map]) { throw "no start section for $map" }; $ports[$map] = 1367 + 10 * $i; $i++ }
if (-not $LoadOnly) {
    $plan = "[locations]`r`n" + (($Maps | ForEach-Object { "$_ = 127.0.0.1:$($ports[$_])" }) -join "`r`n") + "`r`n"
    Set-Content -Encoding ascii (Join-Path $appdata "netcoop_cluster.ltx") $plan
}
$stamp = Get-Date

function Start-LocationServer($name, $port, $start) {
    $arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_$name -fsltx fsgame_selftest_server.ltx " +
        "-netport $port -netcoop_start_location=$start -netcoop_world=selftest_$name -netcoop_cluster_selftest " +
        "-start `"server(all/single/alife/new/portsv=$port/maxplayers=$maxPlayers)`" `"client(localhost/name=serverauthority/port=$port/portcl=$($port + 1))`""
    Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -PassThru
}

function Find-Log($name) {
    Get-ChildItem $logs -Filter "*selftest_$name*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Wait-Loaded($name) {
    $deadline = (Get-Date).AddMinutes($LoadTimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $log = Find-Log $name
        # The periodic clock line starts once the level and ALife run.
        if ($log -and (Select-String -Path $log.FullName -Pattern "\[world\] saved \S+ \(bootstrap\)|loading saved world" -Quiet)) { return $log.FullName }
        if ($log -and (Select-String -Path $log.FullName -Pattern "FATAL ERROR" -SimpleMatch -Quiet)) { throw "server $name crashed while loading: $($log.FullName)" }
        Start-Sleep -Seconds 10
    }
    throw "server $name did not finish loading in $LoadTimeoutMinutes min"
}

$processes = @(); $serverLogs = @()
try {
    foreach ($map in $Maps) {
        $processes += Start-LocationServer $map $ports[$map] $launch[$map]
        $loaded = Wait-Loaded $map
        $serverLogs += $loaded
        Write-Host "$map loaded: $loaded"
    }
    $marsh = $serverLogs[0]
    # One bot process per loaded map in -Spread, logins nbot_<first+n> apart.
    $botMaps = if ($Spread) { $Maps } else { @($Maps[0]) }
    $first = 0
    foreach ($map in $botMaps) {
        $botArgs = "-nosplashwindow -netcoop -dbg -noprefetch -multi_instance -logname selftest_bots_$map -fsltx fsgame_selftest_bots.ltx " +
            "-netcoop_bots $Bots -netcoop_bots_first $first -netcoop_bots_addr 127.0.0.1/port=$($ports[$map])"
        $processes += Start-Process -FilePath $client -ArgumentList $botArgs -WorkingDirectory $Runtime -PassThru
        $first += $Bots
    }
    Write-Host "$($Bots * $botMaps.Count) bots started on $($botMaps -join ', '); running $Minutes min"
    Start-Sleep -Seconds ($Minutes * 60)
}
finally {
    foreach ($p in $processes) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
}

$botLogs = @(Get-ChildItem (Join-Path $Runtime "appdata\selftest_bots\logs") -Filter "*selftest_bots*.log" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt $stamp })
$serverLines = $serverLogs | ForEach-Object { Get-Content $_ }
$botLines = @($botLogs | ForEach-Object { Get-Content $_.FullName })
$summary = [ordered]@{
    leaves = @($serverLines | Select-String "\[cluster\] .* leaves for").Count
    arrivals = @($serverLines | Select-String "\[cluster\] .* arrived from").Count
    redirects = @($serverLines | Select-String "\[cluster\] .* is sent to").Count
    refused = @($serverLines | Select-String "\[cluster\] .*: (not inside|this passage|no server|the character|the server of that map)").Count
    lease_rejects = @($serverLines | Select-String "still on another location server").Count
    save_failures = @($serverLines | Select-String "character save failed").Count
    bot_moves = @($botLines | Select-String "\[bots\] .* goes to").Count
    bot_plays = @($botLines | Select-String "\[bots\] .* plays Actor").Count
    bot_failures = @($botLines | Select-String "^! \[Lost Zone\]\[bots\]").Count
    fatal = @($serverLines + $botLines | Select-String -CaseSensitive "FATAL ERROR|Expression\s*:").Count
}
$summary.GetEnumerator() | ForEach-Object { "{0,-14} {1}" -f $_.Key, $_.Value }
foreach ($log in $botLogs) {
    "last bot reports ($($log.Name)):"
    Get-Content $log.FullName | Select-String "wanted:" | Select-Object -Last 3 | ForEach-Object { $_.Line }
}
foreach ($log in $serverLogs) {
    "last server metrics ($(Split-Path $log -Leaf)):"
    Get-Content $log | Select-String "\[metrics\] server|\[profile\]" | Select-Object -Last 4 | ForEach-Object { $_.Line }
}
"logs: $($serverLogs -join ' ; ') ; $(($botLogs | ForEach-Object FullName) -join ' ; ')"
