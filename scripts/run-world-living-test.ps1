# Living NPCs and mutants across a server restart, with the real game binaries
# (doc 43 L35, F09). Right after a world save of a fresh Great Swamp world
# the server records every living stalker and mutant of the map: id, section,
# community, health, position, squad and the ids of the items they carry.
# The server is killed and started again: the same ids must be alive with the
# same section, community, squad and items, near the saved place (they walk
# a few seconds between the save and the record), and nobody is cloned.
# Bolts are not compared: the engine gives one to a stalker coming online.
#   powershell -File scripts\run-world-living-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$TimeoutMinutes = 15
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
$debugFile = Join-Path $Runtime "netcoop_debug_k00_marsh.lua"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force $logs | Out-Null

function Start-Marsh($tag) {
    $script:stamp = Get-Date
    $script:logname = "selftest_living_$tag"
    $arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname $script:logname -fsltx fsgame_selftest_server.ltx " +
        "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_living -netcoop_world_save_period=20 " +
        "-start `"server(all/single/alife/new/portsv=1367/maxplayers=4)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
    Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
}
function Log-Text {
    $log = Get-ChildItem $logs -Filter "*$($script:logname)_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $script:stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw -Encoding Default }
    return ""
}
function Wait-For($pattern, $what, $after = 0) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = Log-Text
        if ($text.Length -gt $after -and $text.Substring($after) -match $pattern) { return $Matches }
        if ($text -match "FATAL ERROR|(?m)^stack trace:") { throw "server crashed while waiting for $what" }
        Start-Sleep -Seconds 1
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
# One line per creature: id|section|community|health|x|y|z|squad|items
$record = @'
local sim, gg, here = alife(), game_graph(), level.name()
local carried = {}
for i = 1, 65534 do
    local s = sim:object(i)
    -- A bolt is given to every stalker that comes online, with a new id.
    if s and s.parent_id and s.parent_id ~= 65535 and s:section_name() ~= "bolt" then
        carried[s.parent_id] = carried[s.parent_id] or {}
        table.insert(carried[s.parent_id], i .. ":" .. s:section_name())
    end
end
local out = {}
for i = 1, 65534 do
    local se = sim:object(i)
    if se and i ~= 0 and se.alive and se:alive() and se:clsid() ~= clsid.actor and se:clsid() ~= clsid.script_actor then
        local v = se.m_game_vertex_id and gg:vertex(se.m_game_vertex_id)
        if v and sim:level_name(v:level_id()) == here then
            local items = carried[i] or {}
            table.sort(items)
            local comm, health = "-", -1
            pcall(function() comm = se:community() end)
            pcall(function() health = se.health end)
            out[#out + 1] = string.format("%d|%s|%s|%.2f|%.1f|%.1f|%.1f|%s|%s", i, se:section_name(), tostring(comm),
                tonumber(health) or -1, se.position.x, se.position.y, se.position.z, tostring(se.group_id or 65535), table.concat(items, ","))
        end
    end
end
return "LIVING " .. table.concat(out, ";")
'@
function Parse($text) {
    $map = @{}
    foreach ($row in ($text -replace "^LIVING ", "") -split ";") {
        if (-not $row) { continue }
        $f = $row -split "\|"
        $map[$f[0]] = @{ section = $f[1]; community = $f[2]; health = [double]$f[3]; x = [double]$f[4]; y = [double]$f[5]; z = [double]$f[6]
            squad = $f[7]; items = @($f[8] -split "," | Where-Object { $_ }) }
        $map[$f[0]].ids = @($map[$f[0]].items | ForEach-Object { ($_ -split ":")[0] })
    }
    return $map
}

$p = Start-Marsh "a"
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the first world save" | Out-Null
    Start-Sleep -Seconds 30 # NPCs settle into their jobs
    $len = (Log-Text).Length
    Wait-For "\[world\] saved \S+ \(periodic\)" "a periodic world save" $len | Out-Null
    $saved = Parse (Run-Lua $record "record after the save")
    # The record must describe the saved world: the next save must not have
    # started before the server is killed.
    $len = (Log-Text).Length
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 3 }
if ((Log-Text).Substring($len) -match "\[world\] saved") { throw "another save came before the kill; run again" }

$p = Start-Marsh "b"
try {
    Wait-For "loading saved world" "the saved world" | Out-Null
    Wait-For "\[Lost Zone\] world scripts running" "the loaded world" | Out-Null
    $loaded = Parse (Run-Lua $record "record after the restart")
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
Remove-Item $debugFile -ErrorAction SilentlyContinue

$missing = @(); $changed = @(); $moved = @(); $itemsLost = 0; $itemsTotal = 0; $lostList = @()
foreach ($id in $saved.Keys) {
    $a = $saved[$id]; $b = $loaded[$id]
    if (-not $b) { $missing += "$id($($a.section))"; continue }
    if ($a.section -ne $b.section -or $a.community -ne $b.community -or $a.squad -ne $b.squad) { $changed += "$id $($a.section)/$($a.community)/$($a.squad) -> $($b.section)/$($b.community)/$($b.squad)" }
    $d = [Math]::Sqrt([Math]::Pow($a.x - $b.x, 2) + [Math]::Pow($a.z - $b.z, 2))
    if ($d -gt 40) { $moved += "$id $([int]$d) m" }
    $itemsTotal += $a.items.Count
    $lostHere = @($a.items | Where-Object { $b.ids -notcontains (($_ -split ":")[0]) })
    $itemsLost += $lostHere.Count
    if ($lostHere.Count) { $lostList += "$id($($a.section)): $($lostHere -join ' ')" }
}
$new = @($loaded.Keys | Where-Object { -not $saved.ContainsKey($_) })
"saved $($saved.Count) living creatures with $itemsTotal items; after the restart $($loaded.Count) ($($new.Count) not in the record)"
if ($saved.Count -lt 10) { "FAIL: too few creatures recorded ($($saved.Count))"; exit 1 }
if ($missing.Count) { "FAIL: gone after the restart: $($missing -join ', ')"; exit 1 }
if ($changed.Count) { "FAIL: changed identity: $($changed -join '; ')"; exit 1 }
if ($moved.Count -gt [Math]::Max(1, $saved.Count / 10)) { "FAIL: far from the saved place: $($moved -join ', ')"; exit 1 }
$lostList | ForEach-Object { "  lost: $_" }
if ($itemsLost -gt [Math]::Max(2, $itemsTotal / 50)) { "FAIL: $itemsLost of $itemsTotal carried items are gone"; exit 1 }
"PASS: all $($saved.Count) living creatures came back with the same id, section, community and squad; $($itemsTotal - $itemsLost) of $itemsTotal carried items kept (eaten/used ones may go); moved > 40 m: $($moved.Count)"
