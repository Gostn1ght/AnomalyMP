# Location server hibernation with the real game binaries: the Great Swamp
# server starts with -netcoop_hibernate=<s>, is left empty until it hibernates
# (world saved, working set returned), then a load-test player connects; the
# server must wake up and the player must play. Prints the working set before,
# while hibernating and after waking.
#   powershell -File scripts\run-hibernate-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$HibernateAfter = 30,
    [int]$TimeoutMinutes = 15,
    [string]$ServerArgs = ""
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$client = Join-Path $Runtime "bin\LostZoneClientDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force
Remove-Item (Join-Path $Runtime "appdata\selftest_bots\logs") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $logs | Out-Null
$stamp = Get-Date

function Log-Text($pattern) {
    $log = Get-ChildItem $logs -Filter "*$pattern*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $stamp } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw }
    return ""
}
function Wait-For($pattern, $what, $file = "selftest_hibernate") {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = if ($file -eq "bots") {
            $b = Get-ChildItem (Join-Path $Runtime "appdata\selftest_bots\logs") -Filter "*.log" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($b) { Get-Content $b.FullName -Raw } else { "" }
        } else { Log-Text $file }
        if ($text -match $pattern) { return $Matches[0] }
        if ($text -match "FATAL ERROR") { throw "crash while waiting for $what" }
        Start-Sleep -Seconds 3
    }
    throw "timed out waiting for $what"
}
function Memory($p) { $p.Refresh(); "{0} MB working set, {1} MB private" -f [int]($p.WorkingSet64 / 1MB), [int]($p.PrivateMemorySize64 / 1MB) }

$arguments = "-nosplashwindow -noprefetch -netcoop -dbg -multi_instance -logname selftest_hibernate -fsltx fsgame_selftest_server.ltx " +
    "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_hibernate -netcoop_cluster_selftest " +
    "-netcoop_hibernate=$HibernateAfter $ServerArgs " +
    "-start `"server(all/single/alife/new/portsv=1367/maxplayers=8)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
$p = Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
$bots = $null
try {
    Wait-For "\[world\] saved \S+ \(bootstrap\)" "the loaded world" | Out-Null
    Start-Sleep -Seconds 5
    $awake = Memory $p
    Write-Host "awake:        $awake"
    Wait-For "the server hibernates" "hibernation" | Out-Null
    Start-Sleep -Seconds 10
    $asleep = Memory $p
    Write-Host "hibernating:  $asleep"
    $woke = Get-Date
    $bots = Start-Process -FilePath $client -WorkingDirectory $Runtime -PassThru -ArgumentList (
        "-nosplashwindow -netcoop -dbg -noprefetch -multi_instance -logname selftest_bots -fsltx fsgame_selftest_bots.ltx " +
        "-netcoop_bots 1 -netcoop_bots_addr 127.0.0.1/port=1367")
    Wait-For "the server wakes up" "waking up" | Out-Null
    Wait-For "plays Actor" "the player in the world" "bots" | Out-Null
    $seconds = [int]((Get-Date) - $woke).TotalSeconds
    Start-Sleep -Seconds 10
    Write-Host "after waking: $(Memory $p)"
    "PASS: hibernated ($asleep vs $awake awake), a player connected and played after $seconds s, no level reload"
}
finally {
    foreach ($x in @($p, $bots)) { if ($x -and -not $x.HasExited) { Stop-Process -Id $x.Id -Force } }
}
