# Crash at every step of a world save (doc 43 G10/G13), with the real game
# binaries. A fresh Great Swamp world is saved once; then, for each crash
# point, the server loads it, saves again after -SavePeriod seconds and is
# terminated at that point of the save (-netcoop_world_crash). The next start
# must load the last complete commit:
#   before_alife, after_alife, pointer_temp -> the previous slot
#   after_pointer                           -> the new slot
# and run the world (the periodic clock line), with no corrupt-pointer refusal.
#   powershell -File scripts\run-world-crash-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$TimeoutMinutes = 15,
    [int]$SavePeriod = 20
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force $logs | Out-Null
$world = "selftest_crash"

function Start-Marsh($crash) {
    $name = if ($crash) { "crash_$crash" } else { "crash_run$script:run" }
    $script:run++
    $arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_$name -fsltx fsgame_selftest_server.ltx " +
        "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=$world -netcoop_world_save_period=$SavePeriod " +
        "-start `"server(all/single/alife/new/portsv=1367/maxplayers=4)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
    if ($crash) { $arguments += " -netcoop_world_crash=$crash" }
    $script:stamp = Get-Date
    $script:logname = "selftest_$name"
    Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
}
function Log-Text {
    $log = Get-ChildItem $logs -Filter "*$($script:logname)*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $script:stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw }
    return ""
}
function Wait-For($pattern, $what, $process) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = Log-Text
        if ($text -match $pattern) { return $Matches[0] }
        if ($text -match "FATAL ERROR") { throw "server crashed (not by the test) while waiting for $what" }
        if ($process -and $process.HasExited -and -not ((Log-Text) -match $pattern)) { throw "server exited while waiting for $what" }
        Start-Sleep -Seconds 5
    }
    throw "timed out waiting for $what"
}
function Committed {
    $pointer = Join-Path $appdata "savedgames\$world.current"
    if (-not (Test-Path $pointer)) {
        $found = Get-ChildItem $appdata -Recurse -Filter "$world.current" -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $found) { return "" }
        $pointer = $found.FullName
    }
    return (Get-Content $pointer -TotalCount 1).Trim()
}
function Stop-Server($p) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 3 }

$script:run = 0
$results = @()
$p = Start-Marsh $null
try { Write-Host (Wait-For "\[world\] saved $world`_\w+[^\r\n]*" "the first world save" $p) } finally { Stop-Server $p }

foreach ($point in @("before_alife", "after_alife", "pointer_temp", "after_pointer")) {
    $before = Committed
    $p = Start-Marsh $point
    try {
        Write-Host (Wait-For "loading saved world $world`_\w+" "the saved world ($point run)" $p)
        Write-Host (Wait-For "crash test: terminating at $point" "the crash at $point" $p)
        $p.WaitForExit(30000) | Out-Null
    } finally { Stop-Server $p }
    $after = Committed
    $expected = if ($point -eq "after_pointer") { if ($before -like "*_a") { "$world`_b" } else { "$world`_a" } } else { $before }
    $p = Start-Marsh $null
    try {
        $loaded = Wait-For "loading saved world $world`_\w+" "the world after the crash at $point" $p
        Wait-For "\[Lost Zone\]\[clock\] server game[^\r\n]*" "the world running after the crash at $point" $p | Out-Null
        $text = Log-Text
        $ok = $loaded -match "$expected\b" -and $after -eq $expected -and -not ($text -match "refusing save|is corrupt")
        $results += [pscustomobject]@{ point = $point; before = $before; pointer = $after; loaded = ($loaded -split " ")[-1]; expected = $expected; ok = $ok }
    } finally { Stop-Server $p }
}
$results | Format-Table -AutoSize | Out-String | Write-Host
if (@($results | Where-Object { -not $_.ok }).Count) { "FAIL"; exit 1 }
"PASS: after a crash at every step of a save the server loaded the last complete commit and ran"
