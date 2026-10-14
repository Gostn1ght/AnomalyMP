# Exercise the shipped hoster controller against the CI-built EXE, without Python fallback.
param([Parameter(Mandatory=$true)][string]$MasterArtifact)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'netcoop-cluster\netcoop_master_control.ps1')
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testDirectory = Join-Path $temporaryRoot "lz packaged master $([Guid]::NewGuid().ToString('N'))"
try {
    $masterDir = Join-Path $testDirectory 'hoster\master'
    [IO.Directory]::CreateDirectory($masterDir) | Out-Null
    $masterExe = Join-Path $masterDir 'LostZoneMaster.exe'
    $masterPython = Join-Path $masterDir 'python\python.exe'
    $masterConfig = Join-Path $masterDir 'runtime\config.json'
    Copy-Item -LiteralPath $MasterArtifact -Destination $masterExe
    if (-not (Master-Available)) { throw 'Packaged runtime was not detected.' }
    $invocation = Master-Invocation @('-m','lostzone','serve','--config','runtime\config.json')
    if ($invocation.File -cne $masterExe -or $invocation.Arguments[0] -cne 'serve' -or $invocation.Arguments.Count -ne 3) { throw 'EXE CLI prefix changed.' }
    Initialize-Master $testDirectory @('l01_escape','hidden_base')
    $config = [IO.File]::ReadAllText($masterConfig) | ConvertFrom-Json
    # Use an isolated loopback port; an already running owner's master is unrelated.
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
    $listener.Start(); $masterPort = $listener.LocalEndpoint.Port; $listener.Stop()
    $config.port = $masterPort
    [IO.File]::WriteAllText($masterConfig, ($config | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    $before = (Get-FileHash -LiteralPath $masterConfig -Algorithm SHA256).Hash
    Initialize-Master $testDirectory @('l01_escape','hidden_base')
    if ((Get-FileHash -LiteralPath $masterConfig -Algorithm SHA256).Hash -cne $before) { throw 'Existing private configuration changed.' }
    foreach ($name in @('netcoop_world_bridge.json','netcoop_world_writer_l01_escape.json','netcoop_world_writer_hidden_base.json')) {
        $path = Join-Path $testDirectory "appdata\server\$name"
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Engine credential export missing.' }
    }
    $encoded = (@($invocation.Arguments | ForEach-Object { Master-Argument $_ }) -join ' ')
    $process = Start-Process -FilePath $invocation.File -ArgumentList $encoded -WorkingDirectory $masterDir -WindowStyle Hidden -PassThru
    for ($index=0; $index -lt 100 -and -not (Master-Listening); $index++) { Start-Sleep -Milliseconds 100 }
    if (-not (Master-Listening)) { throw 'Packaged service did not listen.' }
    $owned = @(Master-Processes)
    if (-not $owned.Count -or @($owned | Where-Object { $_.ExecutablePath -ine $masterExe }).Count) { throw 'Process ownership detection failed.' }
    [void](Stop-Master)
    for ($index=0; $index -lt 50 -and @(Master-Processes).Count; $index++) { Start-Sleep -Milliseconds 100 }
    if (@(Master-Processes).Count -or (Master-Listening)) { throw 'Packaged bootloader/service survived stop.' }
    $log = Join-Path $masterDir 'runtime\logs\master.log'
    if (-not (Test-Path -LiteralPath $log -PathType Leaf) -or -not (Test-Path -LiteralPath (Join-Path $masterDir 'runtime\world.sqlite') -PathType Leaf)) { throw 'Durable database or log missing.' }
    $content = [IO.File]::ReadAllText($log)
    $privateValues = @($config.signing_key) + @($config.credentials.PSObject.Properties | ForEach-Object { $_.Value.token })
    foreach ($value in $privateValues) { if ($content.Contains($value)) { throw 'Private value leaked to audit log.' } }
    Write-Output 'PASS packaged hoster: no Python fallback, init/credential export, existing config preserved, paths with spaces, EXE process ownership/start/stop, SQLite and private-safe log'
} finally {
    # Only processes with the exact private fixture executable path are ours.
    if ($masterExe -and $masterExe.StartsWith($testDirectory + '\',[StringComparison]::OrdinalIgnoreCase)) { [void](Stop-Master) }
    $resolved = [IO.Path]::GetFullPath($testDirectory)
    if (-not $resolved.StartsWith($temporaryRoot,[StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path $resolved -Leaf) -notmatch '^lz packaged master [a-f0-9]{32}$') { throw 'Unsafe fixture cleanup target.' }
    if ([IO.Directory]::Exists($resolved)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
