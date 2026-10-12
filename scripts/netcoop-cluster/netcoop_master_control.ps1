# World master control for one server folder (owner 2026-10-12): the master
# is the authority of every map - weather, emissions, psi storms and the
# calendar come from it, and maps admit no players without it.
#   . netcoop_master_control.ps1                 (functions for the panel)
#   powershell -File netcoop_master_control.ps1 -MasterRoot <server folder> -StartMaster
# The master ships with its own Python in hoster\master; its private config
# and world DB live in hoster\master\runtime and never leave this PC.
param([string]$MasterRoot = '', [switch]$StartMaster, [switch]$StopMaster)

$masterDir = Join-Path $PSScriptRoot 'master'
$masterPython = Join-Path $masterDir 'python\python.exe'
$masterConfig = Join-Path $masterDir 'runtime\config.json'
$masterPort = 38477
# GAMMA's new game: 26.10.2018 08:00 in engine game milliseconds.
$masterDefaultCalendar = 63676137600000

function Master-Processes {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like '*lostzone*' -and $_.ExecutablePath -and $_.ExecutablePath -like "$masterDir*" })
}
function Master-Listening {
    $client = [Net.Sockets.TcpClient]::new()
    try { return $client.ConnectAsync('127.0.0.1', $masterPort).Wait(150) -and $client.Connected } catch { return $false } finally { $client.Dispose() }
}
function Master-Argument([string]$Argument) {
    # Start-Process joins an argument array without quoting on Windows PS 5.1.
    # Follow the CRT argv rules, including quotes and trailing backslashes.
    $escaped = [regex]::Replace($Argument, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}
function Master-Run([string[]]$Arguments) {
    $encoded = (@($Arguments | ForEach-Object { Master-Argument $_ }) -join ' ')
    $process = Start-Process -FilePath $masterPython -ArgumentList $encoded -WorkingDirectory $masterDir -WindowStyle Hidden -Wait -PassThru
    return $process.ExitCode
}
# The most advanced calendar the maps of this folder already reached (the
# old shared cluster clock files), so no map has to wait for the master.
function Master-InitialCalendar([string]$RuntimeRoot) {
    $best = [double]$masterDefaultCalendar
    $dir = Join-Path $RuntimeRoot 'appdata\server\netcoop_cluster'
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    foreach ($file in @(Get-ChildItem -LiteralPath $dir -Filter 'clock_*.txt' -ErrorAction SilentlyContinue)) {
        $parts = ((Get-Content -LiteralPath $file.FullName -TotalCount 1 -ErrorAction SilentlyContinue) -split '\s+')
        if ($parts.Count -ge 2) {
            $stamp = 0.0; $game = 0.0
            if ([double]::TryParse($parts[0], [ref]$stamp) -and [double]::TryParse($parts[1], [ref]$game) -and $game -gt $best) { $best = $game }
        }
    }
    return [string][math]::Floor($best)
}
# First start on this PC: a private configuration with an explicit world
# identity, every location of the plan and the maps' calendar.
function Initialize-Master([string]$RuntimeRoot, [string[]]$Locations) {
    if (-not (Test-Path -LiteralPath $masterPython)) { throw 'Мастер не установлен: нет hoster\master\python. Скопируйте папку сервера целиком.' }
    if (-not (Test-Path -LiteralPath $masterConfig)) {
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()
        $bytes = [byte[]]::new(16); $random.GetBytes($bytes)
        $worldId = [BitConverter]::ToUInt64($bytes, 0) -band [UInt64]0x3FFFFFFFFFFFFFFF; if ($worldId -eq 0) { $worldId = 1 }
        $seed = [BitConverter]::ToUInt64($bytes, 8) -band [UInt64]0x3FFFFFFFFFFFFFFF
        $arguments = @('-m','lostzone','init','--config','runtime\config.json','--world-id',"$worldId",'--seed',"$seed",
            '--initial-ms',(Master-InitialCalendar $RuntimeRoot),'--scale','10') + @($Locations | ForEach-Object { '--location'; $_ })
        $code = Master-Run $arguments
        if ($code -ne 0) { throw "Мастер не смог создать конфигурацию (код $code)." }
    }
    # The maps' key to the master: one file for every map of this folder.
    $bridge = Join-Path $RuntimeRoot 'appdata\server\netcoop_world_bridge.json'
    [IO.Directory]::CreateDirectory((Split-Path $bridge)) | Out-Null
    $fresh = -not (Test-Path -LiteralPath $bridge) -or (Get-Item -LiteralPath $bridge).LastWriteTimeUtc -lt (Get-Item -LiteralPath $masterConfig).LastWriteTimeUtc -or
        -not (Select-String -LiteralPath $bridge -Pattern '"authority"' -Quiet)
    if ($fresh) {
        $code = Master-Run @('-m','lostzone','bridge-config','--config','runtime\config.json','--destination',$bridge,'--authority','--replace')
        if ($code -ne 0) { throw "Мастер не смог выдать картам ключ доступа (код $code)." }
    }
    foreach ($location in $Locations) {
        $writer = Join-Path $RuntimeRoot "appdata\server\netcoop_world_writer_$location.json"
        $code = Master-Run @('-m','lostzone','writer-config','--config','runtime\config.json','--location',$location,'--destination',$writer,'--replace')
        if ($code -ne 0) { throw "Мастер не смог выдать карте $location доступ к журналу (код $code)." }
    }
}
function Start-Master([string]$RuntimeRoot, [string[]]$Locations) {
    if (@(Master-Processes).Count) { return 'Мастер уже работает.' }
    Initialize-Master $RuntimeRoot $Locations
    $title = 'Lost Zone - мастер мира'
    Start-Process -FilePath 'cmd.exe' -WorkingDirectory $masterDir -ArgumentList "/c title $title & color 07 & python\python.exe -m lostzone console --config runtime\config.json || pause"
    return 'Мастер запускается в своём окне.'
}
function Stop-Master {
    $processes = @(Master-Processes)
    if (-not $processes.Count) { return 'Мастер не запущен.' }
    # Every change is an SQLite transaction (WAL, synchronous FULL): stopping
    # the process cannot leave half a write behind.
    foreach ($p in $processes) {
        foreach ($parent in @(Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)" -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'cmd.exe' })) {
            try { Stop-Process -Id $parent.ProcessId -Force -ErrorAction Stop } catch {}
        }
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    return 'Мастер остановлен.'
}
function Plan-Locations([string]$RuntimeRoot) {
    $plan = Join-Path $RuntimeRoot 'appdata\server\netcoop_cluster.ltx'
    $section = ''; $maps = @()
    foreach ($line in @(Get-Content -LiteralPath $plan -Encoding Default -ErrorAction SilentlyContinue)) {
        $text = ($line -split ';',2)[0].Trim()
        if ($text -match '^\[(.+)\]$') { $section = $Matches[1]; continue }
        if ($section -eq 'locations' -and $text -match '^(\w+)\s*=') { $maps += $Matches[1] }
    }
    return $maps
}

if ($StartMaster -or $StopMaster) {
    $ErrorActionPreference = 'Stop'
    try {
        if ($StopMaster) { Stop-Master; exit 0 }
        $root = [IO.Path]::GetFullPath($MasterRoot)
        Start-Master $root (Plan-Locations $root)
        for ($i = 0; $i -lt 60 -and -not (Master-Listening); $i++) { Start-Sleep -Milliseconds 500 }
        if (Master-Listening) { 'Мастер мира работает.' } else { 'Мастер мира ещё запускается - карты подождут его.' }
    } catch { Write-Host $_.Exception.Message; exit 1 }
}
