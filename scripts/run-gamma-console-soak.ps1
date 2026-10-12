# Handoff 99: real dedicated executables, all maps, production flags and master.
# Restricted to the explicitly authorized test copy; never launches a player.
param(
    [string]$Runtime = 'J:\LostZone_Work\_work\srvtest',
    [int]$HoldSeconds = 45,
    [int]$LoadTimeoutSeconds = 300,
    [string[]]$Maps = @(),
    [string]$RunName = 'console_20261012',
    [string]$TraceSymbols = ''
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($Runtime).TrimEnd('\')
if ($root -ne 'J:\LostZone_Work\_work\srvtest') { throw 'Only the authorized srvtest copy may be used.' }
if ($RunName -notmatch '^console_[a-zA-Z0-9_]+$' -or $HoldSeconds -lt 30 -or $LoadTimeoutSeconds -lt 60) { throw 'Invalid test parameters.' }
$exe = Join-Path $root 'dedicated\LostZoneServerDX11.exe'
$master = Join-Path $root 'hoster\master'
$python = Join-Path $master 'python\python.exe'
$config = Join-Path $master 'runtime\config.json'
$logs = Join-Path $root 'appdata\server\logs'
$resultsFile = Join-Path $root "$RunName.results.json"
$masterPort = 38777
. (Join-Path $PSScriptRoot 'netcoop-cluster\netcoop_cluster_controls.ps1')

function Read-TestLog([string]$Path, [int]$Attempts = 1) {
    for ($attempt=0; $attempt -lt $Attempts; $attempt++) {
        $reader = $null; $stream = $null
        try {
            $sharing = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
            $stream = [IO.FileStream]::new($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,$sharing)
            $reader = [IO.StreamReader]::new($stream)
            return $reader.ReadToEnd()
        } catch [IO.IOException] {
            # The engine may reopen/flush its log during startup.
            if ($attempt+1 -lt $Attempts) { Start-Sleep -Milliseconds 200 }
        } finally { if ($reader) { $reader.Dispose() } elseif ($stream) { $stream.Dispose() } }
    }
    return $null
}

# Use the complete production map/start list, with isolated local test ports.
$sections = @{}; $section = ''
foreach ($raw in Get-Content (Join-Path $PSScriptRoot 'netcoop-cluster\netcoop_cluster.ltx.full')) {
    $line = ($raw -split ';',2)[0].Trim()
    if ($line -match '^\[(\w+)\]$') { $section = $Matches[1]; $sections[$section] = [ordered]@{} }
    elseif ($line -match '^(\w+)\s*=\s*(.+)$') { $sections[$section][$Matches[1]] = $Matches[2] }
}
$allMaps = @($sections.locations.Keys)
if ($allMaps.Count -ne 33) { throw 'Expected the complete 33-map plan.' }
if (-not $Maps.Count) { $Maps = $allMaps }
if (@($Maps | Where-Object { $_ -notin $allMaps }).Count) { throw 'Unknown test map.' }
if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $python)) { throw 'Install the CI dedicated and portable master in srvtest first.' }
if (Get-CimInstance Win32_Process -Filter "Name='LostZoneServerDX11.exe'" | Where-Object { $_.ExecutablePath -eq $exe }) { throw 'Another test server is running.' }
$plan = "[cluster]`r`nmax_players = 512`r`nper_server = 128`r`n[locations]`r`n"
$ports = @{}; $port = 28201
foreach ($map in $allMaps) { $ports[$map]=$port; $plan += "$map = 127.0.0.1:$port`r`n"; $port += 2 }
$plan += "[launch]`r`n"
foreach ($map in $allMaps) { $plan += "$map = $($sections.launch[$map])`r`n" }
Write-ClusterText (Join-Path $root 'appdata\server\netcoop_cluster.ltx') $plan

$masterProcess = $null; $serverProcess = $null; $traceProcess = $null; $results = @()
if ($TraceSymbols) {
    $TraceSymbols = [IO.Path]::GetFullPath($TraceSymbols).TrimEnd('\')
    if (-not (Test-Path -LiteralPath (Join-Path $TraceSymbols 'LostZoneServerDX11.pdb'))) { throw 'CI dedicated symbols are required.' }
}
try {
    Push-Location $master
    try {
        if (-not (Test-Path -LiteralPath $config)) {
            $arguments = @('-m','lostzone','init','--config','runtime\config.json','--world-id','901012','--seed','901012',
                           '--initial-ms','63676137600000','--scale','10')
            foreach ($map in $allMaps) { $arguments += @('--location',$map) }
            & $python @arguments | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Test master initialization failed.' }
            # Test endpoint only. Never print or export private configuration.
            $privateConfig = [IO.File]::ReadAllText($config) | ConvertFrom-Json
            $privateConfig.port = $masterPort
            [IO.File]::WriteAllText($config, ($privateConfig | ConvertTo-Json -Depth 15), [Text.UTF8Encoding]::new($false))
            $privateConfig = $null
        }
        & $python -m lostzone bridge-config --config runtime\config.json --authority --replace --destination (Join-Path $root 'appdata\server\netcoop_world_bridge.json') | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Test master bridge export failed.' }
    } finally { Pop-Location }
    $masterProcess = Start-Process -FilePath $python -ArgumentList '-X utf8 -m lostzone serve --config runtime\config.json' -WorkingDirectory $master -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "$RunName.master.log") -RedirectStandardError (Join-Path $root "$RunName.master.err")
    $listening = $false
    for ($attempt=0; $attempt -lt 60 -and -not $listening; $attempt++) {
        if ($masterProcess.HasExited) { throw 'Test master exited before listening.' }
        $connection = [Net.Sockets.TcpClient]::new()
        try { $listening = $connection.ConnectAsync('127.0.0.1',$masterPort).Wait(200) -and $connection.Connected } catch {} finally { $connection.Dispose() }
        if (-not $listening) { Start-Sleep -Milliseconds 500 }
    }
    if (-not $listening) { throw 'Test master did not become available.' }
    foreach ($map in $Maps) {
        # External orchestration can stop at a safe boundary without killing a map.
        if (Test-Path -LiteralPath (Join-Path $root "$RunName.stop")) {
            Write-Output 'Requested stop after the last completed map.'
            break
        }
        $port = $ports[$map]; $clientPort = $port+1
        $logName = "${RunName}_$map"
        $since = Get-Date
        $args = "-nosplashwindow -noprefetch -netcoop -multi_instance -logname $logName -fsltx fsgame_server.ltx " +
                "-netport $port -netcoop_start_location=$($sections.launch[$map]) -netcoop_world=${RunName}_$map -netcoop_hibernate=120 " +
                "-start `"server(all/single/alife/new/portsv=$port/maxplayers=129)`" `"client(localhost/name=serverauthority/port=$port/portcl=$clientPort)`""
        Write-Output "START $map port=$port"
        $serverProcess = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $root -WindowStyle Hidden -PassThru
        if ($TraceSymbols) {
            $traceTool = Join-Path (Split-Path $PSScriptRoot) 'tools\trace-srvtest-exit.py'
            $traceArgs = '"{0}" {1} "{2}"' -f $traceTool, $serverProcess.Id, $TraceSymbols
            $traceProcess = Start-Process -FilePath (Get-Command python).Source -ArgumentList $traceArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "$logName.trace.log") -RedirectStandardError (Join-Path $root "$logName.trace.err")
        }
        $ready = $false; $connected = $false; $log = $null
        $deadline = (Get-Date).AddSeconds($LoadTimeoutSeconds)
        while (-not $serverProcess.HasExited -and (Get-Date) -lt $deadline) {
            $log = Get-ChildItem -LiteralPath $logs -Filter "xray_${logName}_*.log" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $since } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($log) {
                $content = Read-TestLog $log.FullName
                if ($null -eq $content) { Start-Sleep -Milliseconds 200; continue }
                $ready = $content -match 'ALife switch distance|\[world\] saved \S+ \(bootstrap\)'
                $connected = $content -match '\[master\] connected to the world master'
                if ($ready -and $connected) { break }
            }
            Start-Sleep -Seconds 2
        }
        $loadSeconds = [math]::Round(((Get-Date)-$since).TotalSeconds,1)
        if ($ready -and $connected -and -not $serverProcess.HasExited) { Start-Sleep -Seconds $HoldSeconds }
        if (-not $serverProcess.HasExited) {
            Request-ClusterSavedStop (Join-Path $root 'appdata\server\netcoop_cluster') $port $serverProcess.Id
            $null = $serverProcess.WaitForExit(60000)
        }
        $savedExit = $serverProcess.HasExited
        if (-not $savedExit) { Stop-Process -Id $serverProcess.Id -Force; $serverProcess.WaitForExit() }
        if ($traceProcess -and -not $traceProcess.HasExited) {
            $null = $traceProcess.WaitForExit(10000)
            if (-not $traceProcess.HasExited) { Stop-Process -Id $traceProcess.Id -Force }
        }
        $traceProcess = $null
        $lines = @()
        if ($log) {
            $content = Read-TestLog $log.FullName 20
            if ($null -eq $content) { throw 'Completed test log cannot be read; no result accepted.' }
            $lines = $content -split "`r?`n"
        }
        $errors = @($lines | Where-Object { $_ -match '^!|^~|STACK TRACEBACK|\bERROR\b|\bWARNING\b| is missing\. Replace with stub|\bFATAL\b' })
        $savedExit = $savedExit -and [bool]($lines -match 'hoster requested stop: characters and world saved')
        $cleanExit = $savedExit -and $serverProcess.ExitCode -eq 0
        $row = [ordered]@{map=$map;ready=$ready;master=$connected;load_seconds=$loadSeconds;saved_exit=$savedExit;clean_exit=$cleanExit;exit_code=$serverProcess.ExitCode;errors=$errors.Count;log=$(if($log){$log.FullName}else{''});messages=$errors}
        $results += $row
        Write-ClusterText $resultsFile ($results | ConvertTo-Json -Depth 5)
        Write-Output "RESULT $map ready=$ready master=$connected saved=$savedExit errors=$($errors.Count) load=$loadSeconds"
        $serverProcess = $null
    }
} finally {
    if ($serverProcess -and -not $serverProcess.HasExited) { Stop-Process -Id $serverProcess.Id -Force }
    if ($traceProcess -and -not $traceProcess.HasExited) { Stop-Process -Id $traceProcess.Id -Force }
    if ($masterProcess -and -not $masterProcess.HasExited) { Stop-Process -Id $masterProcess.Id -Force }
}
