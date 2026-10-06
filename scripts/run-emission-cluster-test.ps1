# One emission over two location servers, with a restart in the middle, on
# the real game binaries (doc 43 J10). The Great Swamp and Cordon servers run
# as one cluster (the Zone's shared emission schedule) with an emission every
# game hour. Both must run the same emission (same slot) at about the same
# phase; then the Cordon server is killed during it and started again: it
# must resume that emission at its phase while the Great Swamp server goes
# on undisturbed, and both must record it as finished, once.
#   powershell -File scripts\run-emission-cluster-test.ps1 -Runtime ..\gamma-runtime
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
$maps = @{ marsh = @{ map = "k00_marsh"; port = 1367 }; cordon = @{ map = "l01_escape"; port = 1377 } }
# Start sections from the cluster plan.
$launch = @{}; $section = $null
foreach ($line in Get-Content (Join-Path $PSScriptRoot "netcoop-cluster\netcoop_cluster.ltx.full")) {
    $text = ($line -split ";", 2)[0].Trim()
    if ($text -match "^\[(.+)\]$") { $section = $Matches[1]; continue }
    if ($section -eq "launch" -and $text -match "^(\S+)\s*=\s*(\S+)$") { $launch[$Matches[1]] = $Matches[2] }
}
Set-Content -Encoding ascii (Join-Path $appdata "netcoop_cluster.ltx") ("[locations]`r`n" +
    (($maps.Values | ForEach-Object { "$($_.map) = 127.0.0.1:$($_.port)" }) -join "`r`n") + "`r`n")
$started = @{}; $proc = @{}

function Start-Location($name, $tag) {
    $m = $maps[$name]
    $script:started[$name] = @{ stamp = Get-Date; log = "selftest_ecl_$name$tag" }
    $arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_ecl_$name$tag -fsltx fsgame_selftest_server.ltx " +
        "-netport $($m.port) -netcoop_start_location=$($launch[$m.map]) -netcoop_world=selftest_ecl_$name -netcoop_world_save_period=15 " +
        "-start `"server(all/single/alife/new/portsv=$($m.port)/maxplayers=4)`" `"client(localhost/name=serverauthority/port=$($m.port)/portcl=$($m.port + 1))`""
    $script:proc[$name] = Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
}
function Log-Text($name) {
    $s = $started[$name]
    $log = Get-ChildItem $logs -Filter "*$($s.log)_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $s.stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw -Encoding Default }
    return ""
}
function Wait-For($name, $pattern, $what, $after = 0) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = Log-Text $name
        if ($text.Length -gt $after -and $text.Substring($after) -match $pattern) { return $Matches }
        if ($text -match "FATAL ERROR|(?m)^stack trace:") { throw "$name server crashed while waiting for $what" }
        Start-Sleep -Seconds 3
    }
    throw "timed out waiting for $what on $name"
}
# The debug file is read by every server of the runtime: one write, one
# answer from each running server named in $names.
function Run-Lua($code, $what, $names) {
    $before = @{}; foreach ($n in $names) { $before[$n] = (Log-Text $n).Length }
    Set-Content -Path $debugFile -Value $code -Encoding ascii
    $out = @{}
    foreach ($n in $names) {
        $m = Wait-For $n "\[Lost Zone\]\[debug\] (result|error): ([^\r\n]*)" "$what" $before[$n]
        if ($m[1] -ne "result") { throw "$what failed on $n`: $($m[2])" }
        $out[$n] = $m[2]
    }
    return $out
}
$frequency = "ui_options.set('alife/event/emission_frequency', 1); ui_options.set('alife/event/emission_state', true); return 'frequency ' .. tostring(ui_options.get('alife/event/emission_frequency'))"
$phase = "local s = alife_storage_manager.get_state(); return 'PHASE ' .. string.format('%.0f', netcoop_emission.current_elapsed()) .. ' slot ' .. tostring(s.netcoop_emission_slot) .. ' done ' .. tostring(s.netcoop_emission_done) .. ' count ' .. tostring(s.netcoop_emissions or 0)"
function Field($s, $name) { if ($s -match "$name (\d+)") { [int]$Matches[1] } else { -1 } }

Start-Location "marsh" "a"
Start-Location "cordon" "a"
try {
    foreach ($n in @("marsh", "cordon")) { Wait-For $n "\[world\] saved \S+ \(bootstrap\)" "the first world save" | Out-Null }
    Run-Lua $frequency "emission frequency" @("marsh", "cordon") | Out-Null
    foreach ($n in @("marsh", "cordon")) { Wait-For $n "\[Lost Zone\] emission started" "the emission (up to one game hour)" | Out-Null }
    $len = (Log-Text "cordon").Length
    Wait-For "cordon" "\[world\] saved \S+ \(periodic\)" "a world save during the emission" $len | Out-Null
    Start-Sleep -Seconds 10
    $both = Run-Lua $phase "phase on both" @("marsh", "cordon")
    Write-Host "marsh:  $($both.marsh)"
    Write-Host "cordon: $($both.cordon)"
    $slot = Field $both.marsh "slot"
    if ($slot -lt 0 -or $slot -ne (Field $both.cordon "slot")) { throw "the servers run different emissions: $($both.marsh) / $($both.cordon)" }
    $gap = [Math]::Abs((Field $both.marsh "PHASE") - (Field $both.cordon "PHASE"))
    $killedAt = Field $both.cordon "PHASE"
    Stop-Process -Id $proc.cordon.Id -Force; Start-Sleep -Seconds 3
    Write-Host "cordon killed at phase $killedAt s"
    Start-Location "cordon" "b"
    Wait-For "cordon" "loading saved world" "the saved world" | Out-Null
    Run-Lua $frequency "emission frequency after restart" @("cordon", "marsh") | Out-Null
    Wait-For "cordon" "\[Lost Zone\] emission started" "the resumed emission" | Out-Null
    $after = Run-Lua $phase "phase after restart" @("marsh", "cordon")
    Write-Host "after restart marsh:  $($after.marsh)"
    Write-Host "after restart cordon: $($after.cordon)"
    foreach ($n in @("marsh", "cordon")) { Wait-For $n "\[Lost Zone\] emission finished" "the end of the emission" | Out-Null }
    Start-Sleep -Seconds 5
    $end = Run-Lua $phase "state after the end" @("marsh", "cordon")
    Write-Host "end marsh:  $($end.marsh)"
    Write-Host "end cordon: $($end.cordon)"
} finally {
    foreach ($p in $proc.Values) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
}
Set-Content -Path $debugFile -Value "" -Encoding ascii
if ($gap -gt 30) { "FAIL: the servers are $gap s apart in the same emission"; exit 1 }
if ((Field $after.cordon "slot") -ne $slot) { "FAIL: the restarted Cordon server runs another emission: $($after.cordon)"; exit 1 }
$resumedAt = Field $after.cordon "PHASE"
if ($resumedAt -lt 10) { "FAIL: the emission started over on Cordon (phase $resumedAt s, it was at $killedAt s)"; exit 1 }
if ((Field $after.marsh "slot") -ne $slot -or (Field $after.marsh "PHASE") -lt $resumedAt - 30) { "FAIL: the Great Swamp server was disturbed: $($after.marsh)"; exit 1 }
foreach ($n in @("marsh", "cordon")) {
    if ((Field $end[$n] "done") -ne $slot) { "FAIL: $n did not record the emission as finished: $($end[$n])"; exit 1 }
}
"PASS: emission of slot $slot on both servers ($gap s apart); Cordon killed at $killedAt s resumed at $resumedAt s while the Great Swamp went on; both finished it"
