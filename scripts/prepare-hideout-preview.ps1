param([string]$Destination='')
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$workspace=Split-Path $repo -Parent
$base=Join-Path $workspace 'gamma-runtime'
if (-not $Destination) { $Destination=Join-Path $workspace 'LostZone-3D-Hideout' }
$target=[IO.Path]::GetFullPath($Destination)
if ($target -eq [IO.Path]::GetFullPath($base)) { throw 'Use a separate preview directory' }
$binary=Join-Path $repo '_build\_game\bin_dbg\LostZoneDX11.exe'
if (-not (Test-Path -LiteralPath $binary)) { throw 'Build DX11 first' }
New-Item -ItemType Directory -Path $target -Force | Out-Null
function Copy-Tree([string]$Source,[string]$To) {
    New-Item -ItemType Directory -Path $To -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | Copy-Item -Destination $To -Recurse -Force
}
foreach ($side in @('client','server')) {
    foreach ($dir in @('configs','scripts')) { Copy-Tree (Join-Path $base "$side\$dir") (Join-Path $target "$side\$dir") }
    $overlay=Join-Path $PSScriptRoot "netcoop-overlay\$side"
    # Preserve the owner's deployed email-code endpoint and project settings.
    $cloud=Join-Path $target "$side\configs\netcoop\firebase.ltx"
    $cloudConfig=if (Test-Path -LiteralPath $cloud) { [IO.File]::ReadAllBytes($cloud) } else { $null }
    Copy-Tree (Join-Path $overlay 'configs') (Join-Path $target "$side\configs")
    Get-ChildItem -LiteralPath $overlay -Filter '*.script' | Copy-Item -Destination (Join-Path $target "$side\scripts") -Force
    if ($cloudConfig) { [IO.File]::WriteAllBytes($cloud,$cloudConfig) }
}
foreach ($dir in @('bin','dedicated')) {
    $to=Join-Path $target $dir; New-Item -ItemType Directory -Path $to -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $base $dir) -File | Where-Object Extension -eq '.dll' | Copy-Item -Destination $to -Force
    $name=if ($dir -eq 'bin') {'LostZoneClientDX11.exe'} else {'LostZoneServerDX11.exe'}
    Copy-Item -LiteralPath $binary -Destination (Join-Path $to $name) -Force
}
Copy-Tree (Join-Path $base 'gamedata\shaders') (Join-Path $target 'shaders')
Copy-Tree (Join-Path $PSScriptRoot 'netcoop-overlay\client\shaders') (Join-Path $target 'shaders')
$meshRoot=Join-Path $target 'meshes';New-Item -ItemType Directory -Path $meshRoot -Force | Out-Null
foreach ($entry in Get-ChildItem -LiteralPath (Join-Path $base 'gamedata\meshes')) {
    $to=Join-Path $meshRoot $entry.Name
    if ($entry.Name -eq 'netcoop') { Copy-Tree $entry.FullName $to }
    elseif ($entry.PSIsContainer) { if (-not (Test-Path -LiteralPath $to)) { New-Item -ItemType Junction -Path $to -Value $entry.FullName | Out-Null } }
    else { Copy-Item -LiteralPath $entry.FullName -Destination $to -Force }
}
Copy-Tree (Join-Path $PSScriptRoot 'netcoop-overlay\client\meshes\netcoop') (Join-Path $meshRoot 'netcoop')
$gameData=Join-Path $target 'gamedata';New-Item -ItemType Directory -Path $gameData -Force | Out-Null
foreach ($entry in Get-ChildItem -LiteralPath (Join-Path $base 'gamedata')) {
    $to=Join-Path $gameData $entry.Name
    $source=if ($entry.Name -eq 'meshes') { $meshRoot } elseif ($entry.Name -eq 'shaders') { Join-Path $target 'shaders' } else { $entry.FullName }
    if ($entry.PSIsContainer) { if (-not (Test-Path -LiteralPath $to)) { New-Item -ItemType Junction -Path $to -Value $source | Out-Null } }
    else { Copy-Item -LiteralPath $entry.FullName -Destination $to -Force }
}
foreach ($profile in @('p1','p2','server')) {
    $to=Join-Path $target "appdata\$profile";New-Item -ItemType Directory -Path $to -Force | Out-Null
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $base "appdata\$profile") -File) {
        if ($file.Name -eq 'user.ltx' -or $file.Name -like 'netcoop_*' -or $file.Name -eq 'gamma_ticket.txt') {
            # Initial clone only: never overwrite preview saves on subsequent builds.
            if (-not (Test-Path -LiteralPath (Join-Path $to $file.Name))) { Copy-Item -LiteralPath $file.FullName -Destination $to }
        }
    }
    if ($profile -ne 'server') {
        $last=Join-Path $to 'netcoop_last_server.txt'
        $login=if (Test-Path -LiteralPath $last) { ([IO.File]::ReadAllText($last) -split '\|')[0] } else {''}
        [IO.File]::WriteAllText($last,"$login|127.0.0.1:1277`n",[Text.Encoding]::ASCII)
    }
    $side=if ($profile -eq 'server') {'server'} else {'client'}
    $fs=[IO.File]::ReadAllText((Join-Path $base "fsgame_$profile.ltx"))
    $fs=[regex]::Replace($fs,'(?m)^\$fs_root\$.*$',"`$fs_root`$ = false | false | $target\")
    $fs=[regex]::Replace($fs,'(?m)^\$game_data\$.*$',"`$game_data`$ = true | true | $gameData\")
    $fs=[regex]::Replace($fs,'(?m)^\$app_data_root\$.*$',"`$app_data_root`$ = true | false | $to\")
    $fs=[regex]::Replace($fs,'(?m)^\$game_config\$.*$',"`$game_config`$ = true | false | $target\$side\configs\")
    $fs=[regex]::Replace($fs,'(?m)^\$game_scripts\$.*$',"`$game_scripts`$ = true | false | $target\$side\scripts\")
    $fs=[regex]::Replace($fs,'(?m)^\$game_meshes\$.*$',"`$game_meshes`$ = true | true | $gameData\meshes\")
    $fs=[regex]::Replace($fs,'(?m)^\$game_shaders\$.*$',"`$game_shaders`$ = true | true | $gameData\shaders\")
    [IO.File]::WriteAllText((Join-Path $target "fsgame_$profile.ltx"),$fs,[Text.Encoding]::ASCII)
}
$server=@'
@echo off
cd /d "%~dp0"
start "" "dedicated\LostZoneServerDX11.exe" -nosplashwindow -netcoop -dbg -multi_instance -logname hideout_srv -fsltx fsgame_server.ltx -netport 1277 -netcoop_start_location=hidden_base -start "server(all/single/alife/new/portsv=1277/maxplayers=2)" "client(localhost/name=serverauthority/port=1277/portcl=1278)"
'@
[IO.File]::WriteAllText((Join-Path $target '1-Server.cmd'),$server,[Text.Encoding]::ASCII)
foreach ($profile in @('p1','p2')) {
    $command="@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" `"bin\LostZoneClientDX11.exe`" -nosplashwindow -netcoop -dbg -noprefetch -multi_instance -logname hideout_$profile -fsltx fsgame_$profile.ltx`r`n"
    [IO.File]::WriteAllText((Join-Path $target "2-Client-$profile.cmd"),$command,[Text.Encoding]::ASCII)
}
Write-Output "Independent 3D preview: $target"
Write-Output 'Server port: 1277. Main runtime assets reused; scripts, shaders, room, profiles and saves isolated.'
