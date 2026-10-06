# NPCs and the emission on the real server (doc 43 J06/J07): online NPCs go
# to shelter (GAMMA's covers and surge-safe smarts), and at the end the
# emission kills only those left outside; nobody in a shelter dies.
#   powershell -File scripts\run-emission-cover-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$TimeoutMinutes = 20
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
$debugFile = Join-Path $Runtime "netcoop_debug.lua"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force $logs | Out-Null
Set-Content -Encoding ascii (Join-Path $appdata "netcoop_cluster.ltx") "[locations]`r`nk00_marsh = 127.0.0.1:1367`r`n"
$stamp = Get-Date
$arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_cover -fsltx fsgame_selftest_server.ltx " +
    "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_cover " +
    "-start `"server(all/single/alife/new/portsv=1367/maxplayers=4)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
function Log-Text {
    $log = Get-ChildItem $logs -Filter "*selftest_cover*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $stamp } | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw -Encoding Default }
    return ""
}
function Wait-For($pattern, $what, $after = 0) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = Log-Text
        if ($text.Length -gt $after -and $text.Substring($after) -match $pattern) { return $Matches }
        if ($text -match "FATAL ERROR") { throw "server crashed while waiting for $what" }
        Start-Sleep -Seconds 3
    }
    throw "timed out waiting for $what"
}
function Run-Lua($code, $what) {
    $before = (Log-Text).Length
    Set-Content -Path $debugFile -Value $code -Encoding ascii
    $m = Wait-For "\[Lost Zone\]\[debug\] (result|error): ([^\r\n]*)" $what $before
    if ($m[1] -ne "result") { throw "$what failed on the server: $($m[2])" }
    return $m[2]
}
# Online stalkers: in a cover zone, in a surge-safe smart, exposed (mortal and
# outside both), immune (monolith, zombied, story). Remembers the sheltered.
$probe = @'
-- GAMMA helpers (vector lib) expect db.actor: the hidden anchor Actor, as in the world tick.
local previous_actor = rawget(db, 'actor')
if not previous_actor then db.actor = level.object_by_id(0) end
local ok, result = pcall(function()
local mgr = surge_manager.get_surge_manager()
local sim, board = alife(), SIMBOARD
local cover, safe, exposed, immune, dead, alive = 0, 0, 0, 0, 0, 0
netcoop_cover_test = netcoop_cover_test or {sheltered = {}}
local covers = 0 for _ in pairs(mgr.covers or {}) do covers = covers + 1 end
for i = 1, 65534 do
    local npc = level.object_by_id(i)
    if npc and IsStalker(npc) and not npc:is_actor() then
        if not npc:alive() then dead = dead + 1 else
            alive = alive + 1
            local comm = npc:character_community()
            local se = sim:object(i)
            local squad = se and se.group_id and sim:object(se.group_id)
            local smart = squad and squad.smart_id and board.smarts[squad.smart_id] and board.smarts[squad.smart_id].smrt
            local surge_smart = smart and smart.props and (tonumber(smart.props["surge"]) or 0) > 0
            if comm == "monolith" or comm == "zombied" or get_object_story_id(i) then immune = immune + 1
            elseif mgr:pos_in_cover(npc:position()) then cover = cover + 1; netcoop_cover_test.sheltered[i] = true
            elseif surge_smart then safe = safe + 1; netcoop_cover_test.sheltered[i] = true
            else exposed = exposed + 1 end
        end
    end
end
local lost = 0
for id in pairs(netcoop_cover_test.sheltered) do
    local npc = level.object_by_id(id)
    local se = sim:object(id)
    if (npc and not npc:alive()) or (se and se.alive and not se:alive()) then lost = lost + 1 end
end
return string.format("COVER covers=%d alive=%d dead=%d in_cover=%d safe_smart=%d exposed=%d immune=%d sheltered_dead=%d", covers, alive, dead, cover, safe, exposed, immune, lost)
end)
db.actor = previous_actor
return ok and result or ('probe error ' .. tostring(result))
'@

$p = Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the loaded world" | Out-Null
    Run-Lua "ui_options.set('alife/event/emission_frequency', 1); return 'frequency 1'" "emission frequency" | Out-Null
    $before = Run-Lua $probe "before the emission"
    Write-Host "before:  $before"
    Wait-For "\[Lost Zone\] emission started" "the emission" | Out-Null
    Start-Sleep -Seconds 10
    $start = Run-Lua $probe "emission start"
    Write-Host "start:   $start"
    Start-Sleep -Seconds 150
    $late = Run-Lua $probe "late in the emission"
    Write-Host "late:    $late"
    Wait-For "\[Lost Zone\] emission finished" "the end of the emission" | Out-Null
    Start-Sleep -Seconds 8
    $after = Run-Lua $probe "after the emission"
    Write-Host "after:   $after"
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
Set-Content -Path $debugFile -Value "" -Encoding ascii
function Field($s, $name) { if ($s -match "$name=(\d+)") { [int]$Matches[1] } else { -1 } }
if ((Field $start "covers") -le 0) { "FAIL: no shelters loaded on the server"; exit 1 }
if ((Field $after "sheltered_dead") -gt 0) { "FAIL: NPCs died in a shelter: $after"; exit 1 }
"PASS: shelters loaded, exposed NPCs $(Field $start 'exposed') -> $(Field $late 'exposed') during the emission, nobody in a shelter died (dead $(Field $start 'dead') -> $(Field $after 'dead'))"
