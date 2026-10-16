# Exercise the real download-mark preparation using inert files and NTFS ADS.
# No game, master, downloaded executable or Windows security policy is run/changed.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'netcoop-cluster\netcoop_unblock_launch.ps1')
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testDirectory = Join-Path $temporaryRoot "lz unblock [case] $([Guid]::NewGuid().ToString('N'))"
$launchFiles = @('dedicated\LostZoneServerDX11.exe', 'hoster\master\LostZoneMaster.exe',
    'hoster\master\python\python.exe', 'Start Locations.cmd', 'Start Master.cmd', 'Start Server Panel.cmd')
$untouched = @('unrelated.exe', 'appdata\server\account.txt', 'bin\LostZoneClientDX11.exe')
try {
    $hashes = @{}
    foreach ($name in ($launchFiles + $untouched)) {
        $path = Join-Path $testDirectory $name
        [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
        [IO.File]::WriteAllText($path, 'Inert fixture, never executable: ' + $name)
        Set-Content -LiteralPath $path -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3"
        $hashes[$name] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    $count = Unblock-ServerLaunch $testDirectory
    if ($count -ne $launchFiles.Count) { throw "Expected $($launchFiles.Count) files, got $count" }
    foreach ($name in $launchFiles) {
        if (Get-Item -LiteralPath (Join-Path $testDirectory $name) -Stream Zone.Identifier -ErrorAction SilentlyContinue) { throw "Download mark survived: $name" }
    }
    foreach ($name in $untouched) {
        if (-not (Get-Item -LiteralPath (Join-Path $testDirectory $name) -Stream Zone.Identifier -ErrorAction SilentlyContinue)) { throw "Unrelated download mark changed: $name" }
    }
    if ((Unblock-ServerLaunch $testDirectory) -ne 0) { throw 'Preparation is not idempotent' }
    foreach ($name in $hashes.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path $testDirectory $name) -Algorithm SHA256).Hash -cne $hashes[$name]) { throw "Main file bytes changed: $name" }
    }
    foreach ($name in @('Start Locations.cmd','Start Master.cmd','Start Server Panel.cmd')) {
        $text = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "dist\$name"))
        $prepare = $text.IndexOf('netcoop_unblock_launch.ps1')
        $launch = if ($name -eq 'Start Server Panel.cmd') { $text.IndexOf('netcoop_cluster_panel.ps1') } else { $text.IndexOf('-StartMaster') }
        if ($prepare -lt 0 -or $prepare -gt $launch) { throw "Preparation must precede launch: $name" }
    }
    Write-Output 'PASS real launch preparation: six downloaded kit files unblocked, bytes unchanged, unrelated/client/account files untouched, repeated call harmless, all three entry points prepare before launch; no server started'
} finally {
    $resolved = [IO.Path]::GetFullPath($testDirectory)
    if (-not $resolved.StartsWith($temporaryRoot,[StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path $resolved -Leaf) -notmatch '^lz unblock \[case\] [a-f0-9]{32}$') { throw 'Unsafe fixture cleanup target' }
    if ([IO.Directory]::Exists($resolved)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
