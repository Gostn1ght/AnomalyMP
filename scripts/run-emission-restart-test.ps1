# An emission resumes at its phase after a server restart, with the real game
# binaries (doc 43 J05/J10). The Great Swamp server runs in cluster mode (the
# Zone's shared emission schedule); through its debug channel the emission
# frequency is set to one per game hour so the next one comes within minutes.
# Once it runs (and a world save has recorded it) the server is killed; the
# restarted server must resume the same emission at about the same phase (not
# from 0, not skipped) and then finish it.
#   powershell -File scripts\run-emission-restart-test.ps1 -Runtime ..\gamma-runtime
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
# Cluster mode: one map in the plan is enough for the shared schedule.
Set-Content -Encoding ascii (Join-Path $appdata "netcoop_cluster.ltx") "[locations]`r`nk00_marsh = 127.0.0.1:1367`r`n"

function Start-Marsh($tag) {
    $script:stamp = Get-Date
    $script:logname = "selftest_emission_$tag"
    $arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname $script:logname -fsltx fsgame_selftest_server.ltx " +
        "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_emission -netcoop_world_save_period=15 " +
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
function Run-Lua($code, $what) {
    $before = (Log-Text).Length
    Set-Content -Path $debugFile -Value $code -Encoding ascii
    $m = Wait-For "\[Lost Zone\]\[debug\] (result|error): ([^\r\n]*)" $what $before
    if ($m[1] -ne "result") { throw "$what failed on the server: $($m[2])" }
    return $m[2]
}
$frequency = "ui_options.set('alife/event/emission_frequency', 1); ui_options.set('alife/event/emission_state', true); return 'frequency ' .. tostring(ui_options.get('alife/event/emission_frequency'))"
$phase = "local s = alife_storage_manager.get_state(); return 'PHASE ' .. string.format('%.0f', netcoop_emission.current_elapsed()) .. ' slot ' .. tostring(s.netcoop_emission_slot) .. ' done ' .. tostring(s.netcoop_emission_done)"

$p = Start-Marsh "a"
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the first world save" | Out-Null
    Write-Host (Run-Lua $frequency "emission frequency")
    Wait-For "\[Lost Zone\] emission started" "the emission (up to one game hour)" | Out-Null
    $len = (Log-Text).Length
    Wait-For "\[world\] saved \S+ \(periodic\)" "a world save during the emission" $len | Out-Null
    Start-Sleep -Seconds 20
    $before = Run-Lua $phase "phase before the kill"
    Write-Host "before kill: $before"
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 3 }
if ($before -notmatch "PHASE (\d+) slot (\d+)") { throw "no running emission: $before" }
$killedAt = [int]$Matches[1]; $slot = $Matches[2]

$p = Start-Marsh "b"
try {
    Wait-For "loading saved world" "the saved world" | Out-Null
    Write-Host (Run-Lua $frequency "emission frequency after restart")
    Wait-For "\[Lost Zone\] emission started" "the resumed emission" | Out-Null
    $after = Run-Lua $phase "phase after restart"
    Write-Host "after restart: $after"
    Wait-For "\[Lost Zone\] emission finished" "the end of the resumed emission" | Out-Null
    $end = Run-Lua $phase "state after the end"
    Write-Host "after the end: $end"
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
Set-Content -Path $debugFile -Value "" -Encoding ascii
if ($after -notmatch "PHASE (\d+) slot $slot") { "FAIL: not the same emission after the restart: $after"; exit 1 }
$resumedAt = [int]$Matches[1]
if ($resumedAt -lt 10) { "FAIL: the emission started over (phase $resumedAt s, it was at $killedAt s)"; exit 1 }
if ($end -notmatch "done $slot") { "FAIL: the resumed emission was not recorded as finished: $end"; exit 1 }
"PASS: emission of slot $slot was at $killedAt s when the server died; the restarted server resumed it at $resumedAt s and finished it"
