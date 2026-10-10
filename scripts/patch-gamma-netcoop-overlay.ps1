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

# PDA discovery is a player action. Empty dedicated worlds still process
# timers, but have no db.actor; retain the timer reset without throwing.
& (Join-Path $PSScriptRoot 'patch-netcoop-server-pda.ps1') -ServerScripts (Join-Path $runtime 'server\scripts')
& (Join-Path $PSScriptRoot 'patch-netcoop-server-item-save.ps1') -ServerScripts (Join-Path $runtime 'server\scripts')

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
    $kept = $lines | Where-Object { $_ -notmatch '<btn\s+name="btn_(lastsave|load|save|originals|logout|internet|localnet)"' }
    if ($kept.Count -ne $lines.Count) {
        [System.IO.File]::WriteAllBytes($_.FullName, $latin1.GetBytes(($kept -join $newline)))
        Write-Host "Removed save/load menu buttons from $($_.Name)"
    }
}

# Preserve the stock dialog set; add a translucent modal with one OK button.
$unavailableDialog = @'
    <message_box_netcoop_server_unavailable type="ok" x="282" y="274" width="460" height="220" stretch="1">
        <texture a="210" r="225" g="225" b="225">ui_inGame2_message_box</texture>
        <message_text x="30" y="28" width="400" height="118" complex_mode="1">
            <text r="230" g="225" b="210" align="c" vert_align="c" font="letterica18">st_netcoop_server_unavailable</text>
        </message_text>
        <button_ok x="166" y="162" width="128" height="28" check_mode="0">
            <window_name>button_ok</window_name>
            <text font="letterica18">Btn_OK</text>
            <texture>ui_button_ordinary</texture>
        </button_ok>
    </message_box_netcoop_server_unavailable>
'@
Get-ChildItem -LiteralPath (Join-Path $runtime 'client\configs\ui') -Filter 'message_box*.xml' -File | ForEach-Object {
    $text = $latin1.GetString([IO.File]::ReadAllBytes($_.FullName))
    $text = [regex]::Replace($text, '(?s)\s*<message_box_netcoop_server_unavailable\b.*?</message_box_netcoop_server_unavailable>', '')
    if (-not $text.Contains('</w>')) { throw "Message box root missing: $($_.FullName)" }
    $text = $text.Replace('</w>', $unavailableDialog + "`r`n</w>")
    [IO.File]::WriteAllBytes($_.FullName, $latin1.GetBytes($text))
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

# Load our owned layout rather than the stock layout modified by legacy addons.
Replace-Once (Join-Path $runtime 'client\scripts\ui_main_menu.script') `
    '("ui_mm_main.xml")' `
    '("ui_netcoop_main.xml")'

# Reuse GAMMA's inventory and point picker for new multiplayer characters.
Replace-Once (Join-Path $runtime 'client\scripts\ui_main_menu.script') `
    'function main_menu:Update()' `
    "function main_menu:Update()`n`tif netcoop_login_ui.frontend_update(self) then return end"
Replace-Once (Join-Path $runtime 'client\scripts\ui_main_menu.script') `
    'function main_menu:OnButton_mcm_clicked()' `
    "function main_menu:OnButton_mcm_clicked()`n`tif not netcoop_login_ui.can_mcm() then return end"
Replace-Once (Join-Path $runtime 'client\scripts\ui_main_menu.script') `
    'game.open_originals_link()' 'do return end' -Optional
Replace-Once (Join-Path $runtime 'client\scripts\ui_mcm.script') `
    'function open_to(path)' "function open_to(path)`n`tif not netcoop_login_ui.can_mcm() then return end"
$mcmFile = Join-Path $runtime 'client\scripts\ui_mcm.script'
$mcmText = $latin1.GetString([IO.File]::ReadAllBytes($mcmFile))
if (-not $mcmText.Contains('-- NetAnomaly MCM access gate')) {
    $mcmText += "`n-- NetAnomaly MCM access gate`nfunction UI_MCM:ShowDialog(flag)`n`tif not netcoop_login_ui.can_mcm() then return end`n`tCUIScriptWnd.ShowDialog(self, flag)`nend`n"
    [IO.File]::WriteAllBytes($mcmFile, $latin1.GetBytes($mcmText))
}
$previewSource = Join-Path $PSScriptRoot 'netcoop-overlay\client\shaders\r3'
$previewDestination = Join-Path $runtime 'gamedata\shaders\r3'
foreach ($shader in Get-ChildItem -LiteralPath $previewSource -File) {
    Copy-Item -LiteralPath $shader.FullName -Destination (Join-Path $previewDestination $shader.Name) -Force
}

# Reuse GAMMA's inventory and point picker for new multiplayer characters.
Replace-Once (Join-Path $runtime 'client\scripts\ui_mm_faction_select.script') `
    "function UINewGame:OnStartGame()" `
    "function UINewGame:OnStartGame()`n`tif self.netcoop_creation_owner then return netcoop_login_ui.finish_creation(self) end"

# mcm_log flushes its log files from a per-frame call whose device() lookup
# Empty character loadouts and removed outfits have no item in slot 7.
foreach ($role in @('client','server')) {
    Replace-Once (Join-Path $runtime "$role\scripts\gameplay_disguise.script") `
        'if (id == AC_ID) or state then' `
        'if not item or (id == AC_ID) or state then'
}
Replace-Once (Join-Path $runtime 'server\scripts\gameplay_disguise.script') `
    'character_community(db.actor):sub(7)' `
    '(db.actor and character_community(db.actor):sub(7))'

# Level changer placement belongs to the authority. Pure clients lack the
# simulation smart terrain registry and cannot create server entities here.
foreach ($module in @('lc_custom', 'lc_extra_transitions')) {
    Replace-Once (Join-Path $runtime "client\scripts\$module.script") `
        'function actor_on_first_update()' `
        "function actor_on_first_update()`n`tif netcoop_pure_client and netcoop_pure_client() then return end"
}

# A replicated weapon can arrive before its server-owned parts metadata.
# Keep the generic weapon handling active without inventing random parts.
Replace-Once (Join-Path $runtime 'client\scripts\arti_jamming.script') `
    'local saved_parts = item_parts.get_parts_con(gun, nil, true)' `
    'local saved_parts = item_parts.get_parts_con(gun, nil, true) or {}'

# Emission visuals run on clients, but every damage event comes from the server.
# The two stock direct hits bypass the overridable manager mortality methods.
Replace-Once (Join-Path $runtime 'client\scripts\surge_manager.script') `
    'db.actor:hit(h)' `
    'if not (netcoop_pure_client and netcoop_pure_client()) then db.actor:hit(h) end'

# mcm_log flushes its log files from a per-frame call whose device() lookup
# fails on the dedicated server; logs are still flushed on its other events.
Replace-Once (Join-Path $runtime 'server\scripts\mcm_log.script') `
    "`tAddUniqueCall(timed_flush)" `
    "`tif not netcoop_server_compat then AddUniqueCall(timed_flush) end"

# AI evaluators also run while no player is connected, outside the temporary
# db.actor binding. Recognize every player's Actor by class rather than
# dereferencing a missing single-player Actor (xr_danger:eval_danger).
Replace-Once (Join-Path $runtime 'server\scripts\xr_danger.script') `
    "local from_actor = (danger:object() and (danger:object():id() == db.actor:id()))" `
    "local from_actor = (danger:object() and danger:object():clsid() == clsid.script_actor) or false"
Replace-Once (Join-Path $runtime 'server\scripts\xr_danger.script') `
    "best_danger:object():id() == db.actor:id()" `
    "best_danger:object():clsid() == clsid.script_actor"
Replace-Once (Join-Path $runtime 'server\scripts\xr_danger.script') `
    "if not xr_weight_torch_detection then return end" `
    "if not db.actor or not xr_weight_torch_detection then return end"

# Friendly-fire immunity applies to NPC shooters, not the second co-op Actor.
# db.actor may be the victim's nearest player rather than the actual attacker.
Replace-Once (Join-Path $runtime 'server\scripts\grok_no_npc_friendly_fire.script') `
    'if shit.draftsman:id() == db.actor:id() then return end' `
    'if shit and shit.draftsman and shit.draftsman:clsid() == clsid.script_actor then return end'

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

# Habitat weights apply to simulation squads; each ALife pack gets its own
# native team/squad/group membership instead of merging at the same smart.
$simBoard = Join-Path $runtime 'server\scripts\sim_board.script'
Replace-Once $simBoard `
    "function simulation_board:create_squad(spawn_smart, sq_id)" `
    "function simulation_board:create_squad(spawn_smart, sq_id)`n`tif netcoop_world then sq_id = netcoop_world.regional_squad(spawn_smart, sq_id) end"
Replace-Once $simBoard `
    "change_team_squad_group(se_obj, se_obj.team, smart and smart.squad_id or se_obj.squad, 1)" `
    "change_team_squad_group(se_obj, se_obj.team, smart and smart.squad_id or se_obj.squad, netcoop_world and netcoop_world.squad_group(se_obj, squad, smart) or 1)"

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
# A network item can have no replicated GAMMA parts table yet. The tooltip
# must retain its base description rather than call spairs(nil) or invent
# local random part conditions for an item owned by the server.
Replace-Once (Join-Path $runtime 'client\scripts\zzzz_arti_jamming_repairs.script') `
    "local parts = item_parts.get_parts_con(obj, nil, true)" `
    "local parts = item_parts.get_parts_con(obj, nil, true)`n`t`tif not parts and netcoop_pure_client and netcoop_pure_client() then return _str2 end"

Replace-Once $debugLauncher `
    "function on_game_start()`n`tif not gamma_net_compat.admin_allowed() then return end" `
    "local netcoop_admin_callbacks_registered = false`nfunction on_game_start()`n`tif netcoop_admin_callbacks_registered or not gamma_net_compat.admin_allowed() then return end"
Replace-Once $debugLauncher `
    "`tRegisterScriptCallback(`"on_localization_change`",on_localization_change)`nend" `
    "`tRegisterScriptCallback(`"on_localization_change`",on_localization_change)`n`tnetcoop_admin_callbacks_registered = true`nend"

foreach ($role in $roles) {
    $overlay = Join-Path $PSScriptRoot "netcoop-overlay\$($role.Name)"
    foreach ($assetKind in @('configs', 'textures', 'meshes', 'sounds')) {
        $assets = Join-Path $overlay $assetKind
        if (-not (Test-Path -LiteralPath $assets -PathType Container)) { continue }
        # Both role fsgame files resolve $game_textures$ to gamedata\textures.
        # Only configs and scripts have separate client/server roots. Putting
        # DDS files under client\textures leaves the engine using its missing
        # texture placeholder (a solid square instead of the RP wheel).
        $target = if ($assetKind -in @('textures', 'meshes', 'sounds')) {
            Join-Path $runtime ('gamedata\' + $assetKind)
        } else {
            Join-Path $runtime "$($role.Name)\$assetKind"
        }
        Get-ChildItem -LiteralPath $assets -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($assets.Length + 1)
            $destination = Join-Path $target $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
            Write-Host "Installed $destination"
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

# Restore the overview camera when the stock options dialog returns to our room.
Replace-Once (Join-Path $runtime 'client\scripts\ui_options.script') `
    "`tself.owner:ShowDialog(true)`n`tself:HideDialog()`n`tself.owner:Show(true)" `
    "`tif self.owner.CloseRoomView then self.owner:CloseRoomView() end`n`tself.owner:ShowDialog(true)`n`tself:HideDialog()`n`tself.owner:Show(true)"
