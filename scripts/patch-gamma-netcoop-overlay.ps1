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

function Replace-Once {
    param([string]$File, [string]$Old, [string]$New, [switch]$Optional)
    $text = $latin1.GetString([System.IO.File]::ReadAllBytes($File))
    # GAMMA scripts mix line endings; use whichever form the file contains.
    if (-not $text.Contains($Old) -and -not $text.Contains($New)) {
        $Old = $Old.Replace("`n", "`r`n"); $New = $New.Replace("`n", "`r`n")
    }
    if ($text.Contains($New)) { return }
    if (-not $text.Contains($Old)) {
        if ($Optional) { return }
        throw "Expected GAMMA text missing in $File"
    }
    [System.IO.File]::WriteAllBytes($File, $latin1.GetBytes($text.Replace($Old, $New)))
    Write-Host "Patched $File"
}

# The main menu's new-game button opens the multiplayer login instead.
Get-ChildItem -LiteralPath (Join-Path $runtime 'client\configs\ui') -Filter 'ui_mm_main*.xml' -File | ForEach-Object {
    $text = $latin1.GetString([System.IO.File]::ReadAllBytes($_.FullName))
    if ($text.Contains('caption="ui_mm_newgame"')) {
        [System.IO.File]::WriteAllBytes($_.FullName, $latin1.GetBytes($text.Replace('caption="ui_mm_newgame"', 'caption="ui_mm_netcoop_play"')))
        Write-Host "Renamed the new game button in $($_.Name)"
    }
}
# Earlier overlay versions used the module name netcoop_login, which is also
# the engine's Lua login function.
Replace-Once (Join-Path $runtime 'client\scripts\ui_main_menu.script') `
    "do return netcoop_login.show_login(self) end" `
    "do return netcoop_login_ui.show_login(self) end" -Optional
Replace-Once (Join-Path $runtime 'client\scripts\ui_main_menu.script') `
    "function main_menu:OnButton_new_game()`n`tdo return gamma_net_compat.unavailable() end" `
    "function main_menu:OnButton_new_game()`n`tdo return netcoop_login_ui.show_login(self) end"

# Marsh smart terrains name spawn patrols that this level does not have;
# patrol() on a missing path raises in create_npc and the squad never spawns.
# Fall back to the smart terrain position like the rest of that function.
$squads = Join-Path $runtime 'server\scripts\sim_squad_scripted.script'
Replace-Once $squads `
    "local pat = patrol(p_path)" `
    "local pat = level.patrol_path_exists(p_path) and patrol(p_path)"
Replace-Once $squads `
    "local pat = patrol(spawn_smart.spawn_point)" `
    "local pat = level.patrol_path_exists(spawn_smart.spawn_point) and patrol(spawn_smart.spawn_point)"

# This GAMMA smart terrain lists spawn_isg but defines only spawn_greh.
# Use its existing Greh squad definition rather than dropping the respawn.
foreach ($role in @('server', 'client')) {
    $school = Join-Path $runtime "$role\configs\scripts\evac\smart\pri_a28_school.ltx"
    if (Test-Path -LiteralPath $school -PathType Leaf) {
        Replace-Once $school `
            "[respawn@pri_a28_school]`nspawn_chimera`nspawn_isg" `
            "[respawn@pri_a28_school]`nspawn_chimera`nspawn_greh"
    }
}

$debugLauncher = Join-Path $runtime 'client\scripts\ui_debug_launcher.script'
Replace-Once $debugLauncher `
    "function on_game_start()`n`tif not gamma_net_compat.admin_allowed() then return end" `
    "local netcoop_admin_callbacks_registered = false`nfunction on_game_start()`n`tif netcoop_admin_callbacks_registered or not gamma_net_compat.admin_allowed() then return end"
Replace-Once $debugLauncher `
    "`tRegisterScriptCallback(`"on_localization_change`",on_localization_change)`nend" `
    "`tRegisterScriptCallback(`"on_localization_change`",on_localization_change)`n`tnetcoop_admin_callbacks_registered = true`nend"

foreach ($role in $roles) {
    $overlay = Join-Path $PSScriptRoot "netcoop-overlay\$($role.Name)"
    $configs = Join-Path $overlay 'configs'
    if (Test-Path -LiteralPath $configs -PathType Container) {
        $target = Join-Path $runtime "$($role.Name)\configs"
        Get-ChildItem -LiteralPath $configs -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($configs.Length + 1)
            $destination = Join-Path $target $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
            Write-Host "Installed $($role.Name)\configs\$relative"
        }
    }
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

& (Join-Path $PSScriptRoot 'quarantine-incomplete-gamma-scripts.ps1') -RuntimeRoot $runtime
