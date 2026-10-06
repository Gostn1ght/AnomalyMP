# A game day of the world on the real server, no players (doc 43 M08/M09).
# The Great Swamp server runs in cluster mode with an emission every few game
# hours; every -Every minutes the test records the game time, the living
# NPCs and mutants of the map, corpses, artefacts lying in the map, the
# server's memory and the script errors so far. It fails on a crash, on
# script errors that keep growing, or on memory that keeps growing.
#   powershell -File scripts\run-world-day-test.ps1 -Runtime ..\gamma-runtime -Minutes 150
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$Minutes = 150,
    [int]$Every = 10,
    [int]$EmissionHours = 6
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
$debugFile = Join-Path $Runtime "netcoop_debug.lua"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $logs | Out-Null
Set-Content -Encoding ascii (Join-Path $appdata "netcoop_cluster.ltx") "[locations]`r`nk00_marsh = 127.0.0.1:1367`r`n"
$stamp = Get-Date
$arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_day -fsltx fsgame_selftest_server.ltx " +
    "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_day " +
    "-start `"server(all/single/alife/new/portsv=1367/maxplayers=4)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
function Log-Path { (Get-ChildItem $logs -Filter "*selftest_day*.log" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $stamp } | Select-Object -First 1).FullName }
function Log-Text { $p = Log-Path; if ($p) { Get-Content $p -Raw -Encoding Default } else { "" } }
function Wait-For($pattern, $what, $after = 0) {
    $deadline = (Get-Date).AddMinutes(20)
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
    return $m[2]
}
$probe = @'
local previous = rawget(db, 'actor'); if not previous then db.actor = level.object_by_id(0) end
local ok, res = pcall(function()
local sim, gg, here = alife(), game_graph(), level.name()
local npcs, mutants, corpses, arts = 0, 0, 0, 0
for i = 1, 65534 do
    local se = sim:object(i)
    if se and se.m_game_vertex_id and gg:vertex(se.m_game_vertex_id) and sim:level_name(gg:vertex(se.m_game_vertex_id):level_id()) == here then
        local cls = se:clsid()
        if IsStalker(nil, cls) and se.id ~= 0 then if se:alive() then npcs = npcs + 1 else corpses = corpses + 1 end
        elseif IsMonster(nil, cls) then if se:alive() then mutants = mutants + 1 else corpses = corpses + 1 end
        elseif se.parent_id == 65535 and IsArtefact(nil, cls) then arts = arts + 1 end
    end
end
local s = alife_storage_manager.get_state()
return string.format("DAY %s npcs=%d mutants=%d corpses=%d artefacts=%d emissions=%s", game.get_game_time():dateToString(game.CTime.DateToDay) .. " " .. game.get_game_time():timeToString(game.CTime.TimeToMinutes), npcs, mutants, corpses, arts, tostring(s.netcoop_emissions or 0))
end)
db.actor = previous
return ok and res or ('probe error ' .. tostring(res))
'@

$p = Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
$rows = @()
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the loaded world" | Out-Null
    Run-Lua "ui_options.set('alife/event/emission_frequency', $EmissionHours); return 'frequency'" "emission frequency" | Out-Null
    $end = (Get-Date).AddMinutes($Minutes)
    while ((Get-Date) -lt $end) {
        if ($p.HasExited) { throw "the server exited" }
        $state = Run-Lua $probe "probe"
        $p.Refresh()
        $text = Log-Text
        $errors = ([regex]::Matches($text, "world update error|SCRIPT ERROR|weather update error")).Count
        $row = "{0:HH:mm} {1} private={2}MB errors={3}" -f (Get-Date), $state, [int]($p.PrivateMemorySize64 / 1MB), $errors
        Write-Host $row
        $rows += $row
        Start-Sleep -Seconds ($Every * 60)
    }
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
Set-Content -Path $debugFile -Value "" -Encoding ascii
$mem = $rows | ForEach-Object { if ($_ -match "private=(\d+)MB") { [int]$Matches[1] } }
$err = $rows | ForEach-Object { if ($_ -match "errors=(\d+)") { [int]$Matches[1] } }
$growth = $mem[-1] - $mem[[Math]::Min(2, $mem.Count - 1)]
if (($err[-1] - $err[0]) -gt 20) { "FAIL: script errors keep growing ($($err[0]) -> $($err[-1]))"; exit 1 }
if ($growth -gt 400) { "FAIL: memory grew by $growth MB over the run"; exit 1 }
"PASS: $($rows.Count) samples, memory change $growth MB after warm-up, script errors $($err[0]) -> $($err[-1])"
