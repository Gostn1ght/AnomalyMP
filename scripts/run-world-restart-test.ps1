# Persistent world across a server restart, with the real game binaries.
# Starts the Great Swamp server on a fresh world (appdata\selftest), waits for
# a committed world save, stops the server, starts it again and checks that
# it loads that saved world instead of creating a new one.
#   powershell -File scripts\run-world-restart-test.ps1 -Runtime ..\gamma-runtime
param(
    [string]$Runtime = (Join-Path $PSScriptRoot "..\..\gamma-runtime"),
    [int]$TimeoutMinutes = 20
)
$ErrorActionPreference = "Stop"
$Runtime = (Resolve-Path $Runtime).Path
$server = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$appdata = Join-Path $Runtime "appdata\selftest"
$logs = Join-Path $appdata "logs"
Get-ChildItem $appdata -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin @("user.ltx") } |
    Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force $logs | Out-Null

function Start-Marsh {
    $arguments = "-nosplashwindow -netcoop -dbg -multi_instance -logname selftest_restart -fsltx fsgame_selftest_server.ltx " +
        "-netport 1367 -netcoop_start_location=hidden_base -netcoop_world=selftest_restart " +
        "-start `"server(all/single/alife/new/portsv=1367/maxplayers=4)`" `"client(localhost/name=serverauthority/port=1367/portcl=1368)`""
    Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
}
function Log-Text {
    $log = Get-ChildItem $logs -Filter "*selftest_restart*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { return Get-Content $log.FullName -Raw }
    return ""
}
function Wait-For($pattern, $what) {
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $text = Log-Text
        if ($text -match $pattern) { return $Matches[0] }
        if ($text -match "FATAL ERROR") { throw "server crashed while waiting for $what" }
        Start-Sleep -Seconds 10
    }
    throw "timed out waiting for $what"
}

$p = Start-Marsh
try {
    Write-Host (Wait-For "\[world\] saved selftest_restart_\w+[^\r\n]*" "the first world save")
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 3 }
$p = Start-Marsh
try {
    Write-Host (Wait-For "loading saved world selftest_restart_\w+" "the saved world on restart")
    Write-Host (Wait-For "\[Lost Zone\]\[clock\] server game[^\r\n]*" "the restarted world running")
    "PASS: the world was saved, and the restarted server continued it"
} finally { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
