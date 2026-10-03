param(
    [Parameter(Mandatory = $true)] [string] $BuildBin,
    [Parameter(Mandatory = $true)] [string] $DestinationRoot,
    [string] $DependencyBin
)

$ErrorActionPreference = 'Stop'
$sourceExe = Join-Path $BuildBin 'LostZoneDX11.exe'
if (-not (Test-Path -LiteralPath $sourceExe -PathType Leaf)) {
    throw "DX11 executable missing: $sourceExe"
}

$serverBin = Join-Path $DestinationRoot 'dedicated'
$clientBin = Join-Path $DestinationRoot 'bin'
New-Item -ItemType Directory -Force -Path $serverBin, $clientBin | Out-Null

Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $serverBin 'LostZoneServerDX11.exe') -Force
Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $clientBin 'LostZoneClientDX11.exe') -Force

foreach ($dependencySource in @($BuildBin, $DependencyBin)) {
    if (-not $dependencySource) { continue }
    Get-ChildItem -LiteralPath $dependencySource -Filter '*.dll' -File | ForEach-Object {
        $serverDll = Join-Path $serverBin $_.Name
        $clientDll = Join-Path $clientBin $_.Name
        if (-not [string]::Equals($_.FullName, $serverDll, [StringComparison]::OrdinalIgnoreCase)) {
            Copy-Item -LiteralPath $_.FullName -Destination $serverDll -Force
        }
        if (-not [string]::Equals($_.FullName, $clientDll, [StringComparison]::OrdinalIgnoreCase)) {
            Copy-Item -LiteralPath $_.FullName -Destination $clientDll -Force
        }
    }
}

# Network transport (GameNetworkingSockets) and its dependencies ship next to
# both executables.
$sdkBin = Join-Path (Split-Path -Parent $PSScriptRoot) 'sdk/binaries'
foreach ($name in @('GameNetworkingSockets.dll', 'libprotobuf.dll', 'libcrypto-3-x64.dll')) {
    $dll = Join-Path $sdkBin $name
    if (Test-Path -LiteralPath $dll -PathType Leaf) {
        Copy-Item -LiteralPath $dll -Destination (Join-Path $serverBin $name) -Force
        Copy-Item -LiteralPath $dll -Destination (Join-Path $clientBin $name) -Force
    }
}

Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $serverBin 'LostZoneServerDX11.exe'), (Join-Path $clientBin 'LostZoneClientDX11.exe') |
    Select-Object Path, Hash
