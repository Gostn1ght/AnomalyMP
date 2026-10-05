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
    # Load test: only the Great Swamp server, no cluster, bots stay there.
    [switch]$LoadOnly
)
$ErrorActionPreference = "Stop"
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
if (-not $LoadOnly) { Set-Content -Encoding ascii (Join-Path $appdata "netcoop_cluster.ltx") "[locations]`r`nk00_marsh  = 127.0.0.1:1367`r`nl01_escape = 127.0.0.1:1377`r`n" }
$stamp = Get-Date

function Start-LocationServer($name, $port, $start) {
    $arguments = "-nosplashwindow -netcoop -dbg -multi_instance -logname selftest_$name -fsltx fsgame_selftest_server.ltx " +
        "-netport $port -netcoop_start_location=$start -netcoop_world=selftest_$name -netcoop_cluster_selftest " +
        "-start `"server(all/single/alife/new/portsv=$port/maxplayers=32)`" `"client(localhost/name=serverauthority/port=$port/portcl=$($port + 1))`""
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
        if ($log -and (Select-String -Path $log.FullName -Pattern "[Lost Zone][clock] server game" -SimpleMatch -Quiet)) { return $log.FullName }
        if ($log -and (Select-String -Path $log.FullName -Pattern "FATAL ERROR" -SimpleMatch -Quiet)) { throw "server $name crashed while loading: $($log.FullName)" }
        Start-Sleep -Seconds 10
    }
    throw "server $name did not finish loading in $LoadTimeoutMinutes min"
}

$processes = @()
try {
    $processes += Start-LocationServer "marsh" 1367 "hidden_base"
    $marsh = Wait-Loaded "marsh"
    Write-Host "marsh loaded: $marsh"
    $escape = $marsh
    if (-not $LoadOnly) {
        $processes += Start-LocationServer "escape" 1377 "rookie_village"
        $escape = Wait-Loaded "escape"
        Write-Host "escape loaded: $escape"
    }
    $botArgs = "-nosplashwindow -netcoop -dbg -noprefetch -multi_instance -logname selftest_bots -fsltx fsgame_selftest_bots.ltx " +
        "-netcoop_bots $Bots -netcoop_bots_addr 127.0.0.1/port=1367"
    $processes += Start-Process -FilePath $client -ArgumentList $botArgs -WorkingDirectory $Runtime -PassThru
    Write-Host "bots started; running $Minutes min"
    Start-Sleep -Seconds ($Minutes * 60)
}
finally {
    foreach ($p in $processes) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
}

$botLog = Get-ChildItem (Join-Path $Runtime "appdata\selftest_bots\logs") -Filter "*selftest_bots*.log" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$serverLines = @($marsh, $escape) | ForEach-Object { Get-Content $_ }
$botLines = if ($botLog) { Get-Content $botLog.FullName } else { @() }
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
    fatal = @($serverLines + $botLines | Select-String "FATAL ERROR|stack trace|Expression\s*:").Count
}
$summary.GetEnumerator() | ForEach-Object { "{0,-14} {1}" -f $_.Key, $_.Value }
"last bot reports:"; $botLines | Select-String "wanted:" | Select-Object -Last 3 | ForEach-Object { $_.Line }
"last server metrics:"; Get-Content $marsh | Select-String "\[metrics\] server" | Select-Object -Last 3 | ForEach-Object { $_.Line }
"logs: $marsh ; $escape ; $($botLog.FullName)"
