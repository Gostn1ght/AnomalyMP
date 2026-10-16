# Prepare only this kit's launch files after a downloaded ZIP was extracted.
# No registry/policy/antivirus changes and no recursive game-directory unblock.
param([string]$RuntimeRoot = '')

function Unblock-ServerLaunch([string]$Root) {
    $resolvedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $names = @('dedicated\LostZoneServerDX11.exe', 'hoster\master\LostZoneMaster.exe',
        'hoster\master\python\python.exe', 'Start Locations.cmd', 'Start Master.cmd', 'Start Server Panel.cmd')
    $changed = 0
    foreach ($name in $names) {
        $path = Join-Path $resolvedRoot $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        # Refuse junctions/symlinks that could redirect outside the chosen kit.
        $entry = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        $cursor = $entry
        while ($cursor.FullName -ine $resolvedRoot) {
            if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Launch file uses a reparse point: $name" }
            if ($cursor -is [IO.FileInfo]) { $cursor = $cursor.Directory } else { $cursor = $cursor.Parent }
            if ($null -eq $cursor) { throw 'Launch file escaped the server folder' }
        }
        $zone = Get-Item -LiteralPath $path -Stream Zone.Identifier -ErrorAction SilentlyContinue
        if ($zone) {
            Unblock-File -LiteralPath $path -ErrorAction Stop
            $changed++
        }
    }
    return $changed
}

if ($RuntimeRoot) {
    $ErrorActionPreference = 'Stop'
    try {
        $count = Unblock-ServerLaunch $RuntimeRoot
        if ($count) { Write-Output "Prepared $count downloaded server launch files." }
    } catch {
        Write-Error $_.Exception.Message
        exit 1
    }
}
