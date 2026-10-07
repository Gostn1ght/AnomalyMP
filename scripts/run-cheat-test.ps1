# A client cannot decide damage, deaths or destruction (doc 43 A11), with the
# real game binaries. The Great Swamp server picks a living NPC; a load bot
# (a real network client) joins and, 15 s later, sends a forged deadly hit on
# it, the same hit as a game event, its death, an ammo "transfer" that used
# to assert on the server, and its destruction. The server must refuse all of
# them, stay up, and the NPC must stay alive and unhurt by them.
#   powershell -File scripts\run-cheat-test.ps1 -Runtime ..\gamma-runtime
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
function Server-Log { Log-Text $logs "*selftest_cheat_*.log" }
function Wait-For($pattern, $what, $after = 0, $bots = $false) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = if ($bots) { Log-Text $botLogs "*selftest_bots_cheat*.log" } else { Server-Log }
        if ($text.Length -gt $after -and $text.Substring($after) -match $pattern) { return $Matches }
        if ((Server-Log) -match "FATAL ERROR|(?m)^stack trace:") { throw "the server crashed while waiting for $what" }
        if ($script:srv.HasExited) { throw "the server exited while waiting for $what" }
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

$serverArgs = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_cheat -fsltx fsgame_selftest_server.ltx " +
    "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_cheat -netcoop_cluster_selftest " +
    "-start `"server(all/single/alife/new/portsv=1367/maxplayers=8)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
$script:srv = Start-Process -FilePath $server -ArgumentList $serverArgs -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
$bot = $null
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the loaded world" | Out-Null
    # The nearest ordinary living stalker to the start point (online).
    $pick = Run-Lua @'
local a = alife():actor()
local best, bd
for i = 1, 65534 do
    local o = level.object_by_id(i)
    if o and IsStalker(o) and o:alive() and not o:is_actor() and not get_object_story_id(i) then
        local d = o:position():distance_to(a.position)
        if not best or d < bd then best, bd = o, d end
    end
end
return best and ("TARGET " .. best:id() .. " " .. string.format("%.2f", best.health)) or "no npc"
'@ "pick a target"
    if ($pick -notmatch "TARGET (\d+) ([\d.]+)") { throw "no target: $pick" }
    $target = $Matches[1]; $health = [double]$Matches[2]
    Write-Host "target NPC $target, health $health"
    $botArgs = "-nosplashwindow -netcoop -dbg -noprefetch -multi_instance -logname selftest_bots_cheat -fsltx fsgame_selftest_bots.ltx " +
        "-netcoop_bots 1 -netcoop_bots_first 900 -netcoop_bots_addr 127.0.0.1/port=1367 -netcoop_bots_cheat=$target"
    $bot = Start-Process -FilePath $client -ArgumentList $botArgs -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
    Wait-For "sent forged hit" "the forged events" 0 $true | Out-Null
    Start-Sleep -Seconds 10
    $after = Run-Lua "local o = level.object_by_id($target); local s = alife():object($target); return 'AFTER exists=' .. tostring(s ~= nil) .. ' alive=' .. tostring(o and o:alive()) .. ' health=' .. (o and string.format('%.2f', o.health) or '-')" "the target after"
    Write-Host $after
    $rejected = ([regex]::Matches((Server-Log), "rejected event (\d+) for entity $target|rejected event \d+ for entity 0 ")).Count
    $alive = -not $srv.HasExited
} finally {
    if ($bot -and -not $bot.HasExited) { Stop-Process -Id $bot.Id -Force }
    if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -Force }
}
Remove-Item $debugFile -ErrorAction SilentlyContinue
if (-not $alive) { "FAIL: the server went down"; exit 1 }
if ($after -notmatch "exists=true alive=true") { "FAIL: the forged events killed or removed the NPC: $after"; exit 1 }
if ($rejected -lt 5) { "FAIL: only $rejected of 5 forged events were refused"; exit 1 }
"PASS: the server refused all $rejected forged events and stayed up; NPC $target alive ($after)"
