"""Overlay copies of GAMMA scripts with the console-error fixes (owner 2026-10-12:
no errors in the consoles). Each change is the smallest one that removes the
cause; the header line names it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT.parent / "gamma-runtime" / "gamedata" / "scripts"
O = ROOT / "scripts" / "netcoop-overlay"

FIXES = {
    "ui_mcm.script": [(
        '\tif not opt_val[id] then\r\n\t\tprinte("!MCM given bad path:%s",id)\r\n\t\treturn\r\n\tend',
        '\t-- Lost Zone: mods read options they never put in the menu, with their own\r\n'
        '\t-- default (PAW, Faction ID, MilPDA, EA): not an error, no console line.\r\n'
        '\tif not opt_val[id] then\r\n\t\treturn\r\n\tend')],
    "callbacks_gameobject.script": [(
        'AddScriptCallback("imgui_on_render")\r\n',
        '-- Lost Zone: axr_main already declares imgui_on_render; adding it again was an error.\r\n')],
    "liz_fdda_redone_consumables_ssfx_dof.script": [(
        '    RegisterScriptCallback("on_fddar_consumable_anim_start", on_fddar_consumable_anim_start)\r\n'
        '    RegisterScriptCallback("on_fddar_consumable_anim_end", on_fddar_consumable_anim_end)\r\n',
        '    -- Lost Zone: nothing in GAMMA declares or sends on_fddar_consumable_anim_start/end;\r\n'
        '    -- registering them was an error on every start.\r\n')],
    "mosin_carbine_reload_script.script": [(
        '\tRegisterScriptCallback("actor_on_first_update", actor_on_first_update)\r\n',
        '\t-- Lost Zone: this script defines no actor_on_first_update (a nil callback).\r\n'
        '\tif actor_on_first_update then RegisterScriptCallback("actor_on_first_update", actor_on_first_update) end\r\n')],
    "ui_hud_dotmarks.script": [(
        '\t\tRegisterScriptCallback("physic_object_on_use_callback")\t\t\r\n',
        '\t\t-- Lost Zone: registered without a function (an error on every start).\r\n')],
    "treasure_manager.script": [(
        '                local tier = alternative_tiers:r_float_ex(sec_p, "tier") -- Grok\'s Stash Craft Repair Overhaul Tells the treasure manager to look for the tier code in the above config\r\n',
        '                local tier = alternative_tiers:r_float_ex(sec_p, "tier") -- Grok\'s Stash Craft Repair Overhaul Tells the treasure manager to look for the tier code in the above config\r\n'
        '                -- Lost Zone: the tier file lists multi-use items by their variant\r\n'
        '                -- (cigarettes__1), the lookup used the base section only.\r\n'
        '                tier = tier or alternative_tiers:r_float_ex(section, "tier")\r\n'), (
        '\t\t\t\telse\r\n\t\t\t\t\tprintf("!WARNING treasure_manager.init_settings | item [%s] is missing info | kind: %s - tier: %s", section, kind, tier)',
        '\t\t\t\telse\r\n\t\t\t\t\t-- Lost Zone: an item without a tier stays out of stashes, as GAMMA\r\n'
        '\t\t\t\t\t-- intends; not a console error.')],
}


def apply(name, pairs):
    text = (G / name).read_bytes().decode("latin-1")
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"{name}: pattern found {text.count(old)} times: {old[:60]!r}")
        text = text.replace(old, new)
    data = text.encode("latin-1")
    for side in ("client", "server"):
        (O / side / name).write_bytes(data)
    print("fixed", name)


for name, pairs in FIXES.items():
    apply(name, pairs)

STUB = '''-- Lost Zone server: Screen Space Shaders' {what} settings are client graphics.
-- A dedicated server renders nothing and has no MCM values for them: it sent
-- "{command}" with zeros, an invalid console command, on every start.
-- Other scripts only test that the module is present.
module_installed = true
function on_game_start() end
'''
for name, what, command in (("ssfx_water.script", "water", "ssfx_water (0,0,0,0)"),
                            ("ssfx_wetness.script", "wetness/gloss", "ssfx_gloss_minmax (0,0,0)")):
    (O / "server" / name).write_bytes(STUB.format(what=what, command=command).replace("\n", "\r\n").encode("ascii"))
    print("server stub", name)
