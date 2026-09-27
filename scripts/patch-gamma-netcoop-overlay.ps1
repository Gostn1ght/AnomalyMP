param(
    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot
)

# Installs the netcoop Lua overlay into the prepared runtime:
#   netcoop-overlay\client\*.script -> client\scripts
#   netcoop-overlay\server\*.script -> server\scripts
# and appends each role's install() call to that role's _g.script.
# The original GAMMA modpack is never modified.

$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$latin1 = [System.Text.Encoding]::GetEncoding(28591)

$roles = @(
    @{ Name = 'client'; Module = 'netcoop_client_compat' },
    @{ Name = 'server'; Module = 'netcoop_server_compat' }
)

# The server owns the world, so a client has no save games: remove the
# last-save, load and save buttons from every main menu layout.
Get-ChildItem -LiteralPath (Join-Path $runtime 'client\configs\ui') -Filter 'ui_mm_main*.xml' -File | ForEach-Object {
    $text = $latin1.GetString([System.IO.File]::ReadAllBytes($_.FullName))
    $newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines = $text -split "`r?`n"
    $kept = $lines | Where-Object { $_ -notmatch '<btn\s+name="btn_(lastsave|load|save)"' }
    if ($kept.Count -ne $lines.Count) {
        [System.IO.File]::WriteAllBytes($_.FullName, $latin1.GetBytes(($kept -join $newline)))
        Write-Host "Removed save/load menu buttons from $($_.Name)"
    }
}

foreach ($role in $roles) {
    $overlay = Join-Path $PSScriptRoot "netcoop-overlay\$($role.Name)"
    $scripts = Join-Path $runtime "$($role.Name)\scripts"
    if (-not (Test-Path -LiteralPath $scripts -PathType Container)) {
        throw "Script directory missing: $scripts"
    }

    Get-ChildItem -LiteralPath $overlay -Filter '*.script' -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $scripts $_.Name) -Force
        Write-Host "Installed $($role.Name)\$($_.Name)"
    }

    $g = Join-Path $scripts '_g.script'
    $content = $latin1.GetString([System.IO.File]::ReadAllBytes($g))
    $marker = "-- NetAnomaly netcoop $($role.Name) compatibility"
    if (-not $content.Contains($marker)) {
        $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
        $append = $newline + $marker + $newline +
            "if $($role.Module) then $($role.Module).install() end" + $newline
        [System.IO.File]::WriteAllBytes($g, $latin1.GetBytes($content + $append))
        Write-Host "Patched $g"
    }
}
