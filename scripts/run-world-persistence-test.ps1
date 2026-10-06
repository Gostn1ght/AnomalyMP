# The world across a server restart, with the real game binaries (doc 43
# L05 L18, corpses per the owner 2026-10-06). On a fresh Great Swamp world the
# server (through its local debug channel, netcoop_debug.lua):
#   - gives the nearest ordinary NPC an artefact and kills it (the corpse
#     holds its freeplay loot and the artefact),
#   - puts an item into a container and an artefact on the ground.
# After a world save the server is killed and started again: the container
# and the ground artefact come back id for id; the corpse is removed with its
# loot (corpses go on a restart). Then another NPC is killed with the corpse
# lifetime lowered from 40 minutes to 1 s: it goes with its loot too.
#   powershell -File scripts\run-world-persistence-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$TimeoutMinutes = 15
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

function Start-Marsh($tag) {
    $script:stamp = Get-Date
    $script:logname = "selftest_persist_$tag"
    $arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname $script:logname -fsltx fsgame_selftest_server.ltx " +
        "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_persist -netcoop_world_save_period=20 " +
        "-start `"server(all/single/alife/new/portsv=1367/maxplayers=4)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
    Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
}
function Log-Text {
    $log = Get-ChildItem $logs -Filter "*$($script:logname)*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $script:stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
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
# Runs Lua on the server; returns the text after "[debug] result: ".
function Run-Lua($code, $what) {
    $before = (Log-Text).Length
    Set-Content -Path $debugFile -Value $code -Encoding ascii
    $m = Wait-For "\[Lost Zone\]\[debug\] (result|error): ([^\r\n]*)" $what $before
    if ($m[1] -ne "result") { throw "$what failed on the server: $($m[2])" }
    return $m[2]
}

$setup = @'
local sim = alife()
local a = sim:actor()
local best, bd
for i = 1, 65534 do
    local o = level.object_by_id(i)
    if o and IsStalker(o) and o:alive() and not o:is_actor() and not get_object_story_id(i) then
        local d = o:position():distance_to(a.position)
        if not best or d < bd then best, bd = o, d end
    end
end
if not best then return "no npc" end
local art = alife_create_item("af_medusa", best)
local box
for i = 1, 65534 do
    local o = level.object_by_id(i)
    if o and o:is_inventory_box() and not get_object_story_id(i) then box = o break end
end
local boxid = -1
if box then alife_create_item("af_blood", box); boxid = box:id() end
local ground = alife_create_item("af_soul", {a.position, a.m_level_vertex_id, a.m_game_vertex_id})
best:kill(best)
return "SETUP npc=" .. best:id() .. " art=" .. tostring(art and art.id) .. " box=" .. boxid .. " ground=" .. tostring(ground and ground.id)
'@

function State-Lua($npc, $box, $ground) {
@"
local sim = alife()
local function children(pid)
    local t = {}
    if pid < 0 then return "" end
    for i = 1, 65534 do
        local s = sim:object(i)
        if s and s.parent_id == pid then t[#t + 1] = i .. ":" .. s:section_name() end
    end
    table.sort(t)
    return table.concat(t, ",")
end
local n = sim:object($npc)
local alive = n and n.alive and n:alive()
local g = sim:object($ground)
return "STATE corpse=" .. tostring(n ~= nil) .. " alive=" .. tostring(alive) .. " items=[" .. children($npc) ..
    "] box=[" .. children($box) .. "] ground=" .. (g and (g.id .. ":" .. g:section_name() .. "@" .. tostring(g.parent_id)) or "none")
"@
}

function Item-Ids($state) {
    ([regex]::Matches($state, "items=\[([^\]]*)\]")[0].Groups[1].Value -split "," | Where-Object { $_ } | ForEach-Object { ($_ -split ":")[0] }) -join ","
}
function Missing-Lua($ids) {
    "local s = alife(); local left = {} for _, id in ipairs({$ids}) do if s:object(id) then left[#left + 1] = tostring(id) end end; return 'LEFT ' .. table.concat(left, ',')"
}

$p = Start-Marsh "a"
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the first world save" | Out-Null
    $setupResult = Run-Lua $setup "setup"
    Write-Host $setupResult
    if ($setupResult -notmatch "npc=(\d+) art=(\d+) box=(-?\d+) ground=(\d+)") { throw "setup: $setupResult" }
    $npc = $Matches[1]; $art = $Matches[2]; $box = $Matches[3]; $ground = $Matches[4]
    Start-Sleep -Seconds 8 # death loot is made at death
    $before = Run-Lua (State-Lua $npc $box $ground) "state before"
    Write-Host "before:   $before"
    if ($before -notmatch "corpse=true alive=false" -or $before -notmatch "$art`:af_medusa") { throw "the corpse does not hold the artefact: $before" }
    $len = (Log-Text).Length
    Wait-For "\[world\] saved \S+ \(periodic\)" "a world save after the setup" $len | Out-Null
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 3 }

$p = Start-Marsh "b"
try {
    Wait-For "loading saved world" "the saved world" | Out-Null
    Wait-For "\[corpses\] server start: \d+" "corpse removal at the start" | Out-Null
    Start-Sleep -Seconds 10
    $after = Run-Lua (State-Lua $npc $box $ground) "state after restart"
    Write-Host "after:    $after"
    $leftA = Run-Lua (Missing-Lua (Item-Ids $before)) "loot of the first corpse"
    Write-Host "loot:     $leftA"
    # 40 minutes without a player, shortened to 1 s.
    $second = Run-Lua $setup "second NPC"
    if ($second -notmatch "npc=(\d+)") { throw "second setup: $second" }
    $npc2 = $Matches[1]
    Start-Sleep -Seconds 8
    $before2 = Run-Lua (State-Lua $npc2 -1 $ground) "second corpse"
    Write-Host "second:   $before2"
    Run-Lua "netcoop_corpses.corpse_time = 1; return 'corpse time 1 s'" "corpse time" | Out-Null
    Start-Sleep -Seconds 45
    $gone2 = Run-Lua (State-Lua $npc2 -1 $ground) "second corpse after its time"
    Write-Host "removed:  $gone2"
    $leftB = Run-Lua (Missing-Lua (Item-Ids $before2)) "loot of the second corpse"
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
Set-Content -Path $debugFile -Value "" -Encoding ascii
$kept = ($before -replace "^STATE corpse=true alive=false items=\[[^\]]*\] ", "")
if ($after -ne "STATE corpse=false alive=nil items=[] $kept") { "FAIL: after the restart expected the corpse gone and '$kept', got: $after"; exit 1 }
if ($leftA -ne "LEFT ") { "FAIL: the first corpse's loot was not removed with it: $leftA"; exit 1 }
if ($gone2 -notmatch "^STATE corpse=false alive=nil items=\[\]") { "FAIL: the second corpse did not go after its time: $gone2"; exit 1 }
if ($leftB -ne "LEFT ") { "FAIL: the second corpse's loot was not removed with it: $leftB"; exit 1 }
"PASS: container and ground artefact came back id for id after a restart; corpses went with their loot on the restart and after their time without players"
