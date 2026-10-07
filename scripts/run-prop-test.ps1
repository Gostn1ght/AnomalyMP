# Doors and physics props reach the players (doc 43 L29), with the real game
# binaries. A load bot (a real network client) joins the Great Swamp server;
# the server then pushes the nearest physics prop (a door, barrel, crate) to
# the start point. The prop must be followed by the server and the bot must
# receive its new pose: before 2026-10-07 props were never sent, so a door
# opened on the server stayed closed and solid on every client.
#   powershell -File scripts\run-prop-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$TimeoutMinutes = 15
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$client = Join-Path $Runtime "bin\LostZoneClientDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
$botLogs = Join-Path $Runtime "appdata\selftest_bots\logs"
$debugFile = Join-Path $Runtime "netcoop_debug_k00_marsh.lua"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force
Remove-Item $botLogs -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $logs | Out-Null
$stamp = Get-Date
function Log-Text($folder, $filter) {
    $log = Get-ChildItem $folder -Filter $filter -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw -Encoding Default }
    return ""
}
function Server-Log { Log-Text $logs "*selftest_prop_*.log" }
function Bot-Log { Log-Text $botLogs "*selftest_bots_prop*.log" }
function Wait-For($pattern, $what, $after = 0, $bots = $false) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = if ($bots) { Bot-Log } else { Server-Log }
        if ($text.Length -gt $after -and $text.Substring($after) -match $pattern) { return $Matches }
        if ((Server-Log) -match "FATAL ERROR|(?m)^stack trace:") { throw "the server crashed while waiting for $what" }
        Start-Sleep -Seconds 2
    }
    throw "timed out waiting for $what"
}
function Run-Lua($code, $what) {
    $before = (Server-Log).Length
    Set-Content -Path $debugFile -Value $code -Encoding ascii
    $m = Wait-For "\[Lost Zone\]\[debug\] (result|error): ([^\r\n]*)" $what $before
    if ($m[1] -ne "result") { throw "$what failed on the server: $($m[2])" }
    return $m[2]
}

$serverArgs = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_prop -fsltx fsgame_selftest_server.ltx " +
    "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_prop -netcoop_cluster_selftest " +
    "-start `"server(all/single/alife/new/portsv=1367/maxplayers=8)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
$srv = Start-Process -FilePath $server -ArgumentList $serverArgs -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
$bot = $null
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the loaded world" | Out-Null
    # The nearest physics prop to the start point (not an item, not a creature).
    $pick = Run-Lua @'
local a = alife():actor()
local best, bd
for i = 1, 65534 do
    local o = level.object_by_id(i)
    local cls = o and o:clsid()
    if (cls == clsid.obj_physic or cls == clsid.obj_phys_destroyable) and o:get_physics_shell() then
        local d = o:position():distance_to(a.position)
        if d < 150 and (not best or d < bd) then best, bd = o, d end
    end
end
return best and string.format("PROP %d %s %.0f", best:id(), best:section(), bd) or "no prop"
'@ "pick a prop"
    if ($pick -notmatch "PROP (\d+) (\S+)") { throw "no prop near the start: $pick" }
    $prop = $Matches[1]
    Write-Host "prop: $pick"
    $botArgs = "-nosplashwindow -netcoop -dbg -noprefetch -multi_instance -logname selftest_bots_prop -fsltx fsgame_selftest_bots.ltx " +
        "-netcoop_bots 1 -netcoop_bots_first 950 -netcoop_bots_addr 127.0.0.1/port=1367 -netcoop_bots_watch=$prop"
    $bot = Start-Process -FilePath $client -ArgumentList $botArgs -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
    Wait-For "plays Actor" "the bot in the game" 0 $true | Out-Null
    Start-Sleep -Seconds 40 # past the level's settling time
    $len = (Server-Log).Length
    Write-Host (Run-Lua "local o = level.object_by_id($prop); local s = o and o:get_physics_shell(); if not s then return 'no shell' end; s:apply_force(15000, 30000, 15000); return 'pushed ' .. string.format('%.2f %.2f %.2f', o:position().x, o:position().y, o:position().z)" "push the prop")
    Wait-For "\[physics\] prop \S+ \($prop\) moved" "the server following the prop" $len | Out-Null
    $got = Wait-For "got the pose of $prop`: ([^\r\n]*)" "the pose on the bot" 0 $true
    Write-Host "bot: $($got[0])"
} finally {
    if ($bot -and -not $bot.HasExited) { Stop-Process -Id $bot.Id -Force }
    if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -Force }
}
Remove-Item $debugFile -ErrorAction SilentlyContinue
"PASS: prop $prop pushed on the server, followed, and its pose reached the player"
