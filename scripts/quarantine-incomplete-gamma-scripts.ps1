param(
    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot
)

$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimeRoot).Path.TrimEnd('\')
$prefix = $runtime + '\'

function Assert-RuntimePath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes the prepared runtime: $full"
    }
    return $full
}

# These fragments cannot load in the prepared profile: their required modules
# are absent, or their Lua source is not valid. Keep them in the runtime for
# restoration; never change the user's source GAMMA installation.
$fragments = @(
    @{ Name = 'a_faction_prices.script'; Dependency = 'faction_stocks.script' },
    @{ Name = 'mags_patches.script'; Dependency = 'magazine_binder.script' },
    @{ Name = 'zz_ui_inventory_better_stats_bars.script'; Dependency = 'better_stats_bars_mcm.script' },
    @{ Name = 'zzz_mspizza_Godis_ZoomCalc.script'; Dependency = $null }
)

foreach ($role in @('server', 'client')) {
    $scripts = Assert-RuntimePath (Join-Path $runtime "$role\scripts")
    foreach ($fragment in $fragments) {
        $source = Assert-RuntimePath (Join-Path $scripts $fragment.Name)
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        if ($fragment.Dependency -and
            (Test-Path -LiteralPath (Join-Path $scripts $fragment.Dependency) -PathType Leaf)) {
            continue
        }
        $quarantine = Assert-RuntimePath (Join-Path $runtime "$role\scripts_disabled\netanomaly")
        New-Item -ItemType Directory -Path $quarantine -Force | Out-Null
        $destination = Assert-RuntimePath (Join-Path $quarantine $fragment.Name)
        if (Test-Path -LiteralPath $destination) {
            throw "Quarantine destination already exists: $destination"
        }
        Move-Item -LiteralPath $source -Destination $destination
        Write-Host "Quarantined incomplete GAMMA module: $role/$($fragment.Name)"
    }
}
