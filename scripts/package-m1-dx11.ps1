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

# Engine imports (ICU, TBB, Discord) and network transport must be next to
# both executables, rather than hidden beside an obsolete GAMMA executable.
$sdkBin = Join-Path (Split-Path -Parent $PSScriptRoot) 'sdk/binaries'
foreach ($name in @('GameNetworkingSockets.dll', 'libprotobuf.dll', 'libcrypto-3-x64.dll', 'discord_game_sdk.dll', 'icuuc65.dll', 'icudt65.dll', 'tbb.dll', 'soft_oal.dll')) {
    $dll = Join-Path $sdkBin $name
    if (Test-Path -LiteralPath $dll -PathType Leaf) {
        Copy-Item -LiteralPath $dll -Destination (Join-Path $serverBin $name) -Force
        Copy-Item -LiteralPath $dll -Destination (Join-Path $clientBin $name) -Force
    } else { throw "SDK runtime missing: $name" }
}

# Both the exe and transport import VC143. Ship Microsoft's app-local x64
# runtime from the same GHA toolchain, so a friend needs no Visual Studio.
if ($env:GITHUB_ACTIONS -eq 'true') {
    # Microsoft's side-by-side D3DX redistributable, pinned by package hash.
    # Do not rely on legacy DirectX having been installed on the friend's PC.
    $dxPackage = Join-Path $DestinationRoot 'microsoft.dxsdk.d3dx.nupkg'
    Invoke-WebRequest -Uri 'https://api.nuget.org/v3-flatcontainer/microsoft.dxsdk.d3dx/9.29.952.8/microsoft.dxsdk.d3dx.9.29.952.8.nupkg' -OutFile $dxPackage
    if ((Get-FileHash -LiteralPath $dxPackage -Algorithm SHA256).Hash -ne 'EAD0906AE8A26C18A7525DA7490127A2110F7C58F18293738283E30E97C6EA4B') {
        throw 'Microsoft D3DX package hash mismatch'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $dxZip = [IO.Compression.ZipFile]::OpenRead($dxPackage)
    try {
        foreach ($name in @('D3DX9_43.dll', 'd3dx11_43.dll', 'D3DCompiler_43.dll')) {
            $entry = $dxZip.GetEntry("build/native/release/bin/x64/$name")
            if (-not $entry) { throw "D3DX runtime missing: $name" }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $clientBin $name), $true)
            Copy-Item -LiteralPath (Join-Path $clientBin $name) -Destination (Join-Path $serverBin $name) -Force
        }
        $notices = Join-Path $DestinationRoot 'notices'
        New-Item -ItemType Directory -Force -Path $notices | Out-Null
        [IO.Compression.ZipFileExtensions]::ExtractToFile($dxZip.GetEntry('LICENSE.txt'), (Join-Path $notices 'Microsoft-D3DX-LICENSE.txt'), $true)
    } finally { $dxZip.Dispose() }
    Remove-Item -LiteralPath $dxPackage
    $redistRoot = Join-Path ${env:ProgramFiles} 'Microsoft Visual Studio\2022\Enterprise\VC\Redist\MSVC'
    $crt = Get-ChildItem -LiteralPath $redistRoot -Directory | Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'x64\Microsoft.VC143.CRT' } |
        Where-Object { Test-Path -LiteralPath (Join-Path $_ 'vcruntime140_1.dll') -PathType Leaf } |
        Select-Object -First 1
    if (-not $crt) { throw 'The x64 Visual C++ redistributable runtime was not found' }
    foreach ($dll in Get-ChildItem -LiteralPath $crt -Filter '*.dll' -File) {
        Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $serverBin $dll.Name) -Force
        Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $clientBin $dll.Name) -Force
    }
    foreach ($name in @('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')) {
        if (-not (Test-Path -LiteralPath (Join-Path $clientBin $name) -PathType Leaf)) {
            throw "Portable runtime missing: $name"
        }
    }
}

Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $serverBin 'LostZoneServerDX11.exe'), (Join-Path $clientBin 'LostZoneClientDX11.exe') |
    Select-Object Path, Hash
