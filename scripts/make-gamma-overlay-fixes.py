"""Overlay copies of GAMMA scripts with the console-error fixes (owner 2026-10-12:
no errors in the consoles). Each change is the smallest one that removes the
cause; the header line names it."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
G = ROOT.parent / "gamma-runtime" / "gamedata" / "scripts"
O = ROOT / "scripts" / "netcoop-overlay"

FIXES = {
    "agdd_voiced_actor.script": [(
        'function monster_on_death_callback(victim, killer)\r\n'
        '    -- (EDITED FUNCTION - ADDED MORE CALLBACKS) adds combat_intensity when a mutant is killed\r\n\r\n'
        '    if not db.actor:alive() then\r\n',
        'function monster_on_death_callback(victim, killer)\r\n'
        '    -- Lost Zone: dedicated deaths can occur before a local actor exists.\r\n'
        '    if not db.actor or not db.actor:alive() then\r\n')],
    "grok_loot_claim.script": [(
        '\tlocal k_faction = killer and character_community(killer)\r\n',
        '\t-- Lost Zone: environmental deaths have no killer; no claim is created.\r\n'
        '\tif not v_id or not k_id then return end\r\n'), (
        '\tif k_id == db.actor:id() then\r\n',
        '\t-- Lost Zone: NPC fights also happen before a dedicated actor exists.\r\n'
        '\tif db.actor and k_id == db.actor:id() then\r\n')],
    "utils_catspaw_common.script": [(
        'logdiv = "~ ------------------------------------------------------------------------\\n"',
        '-- Lost Zone: feature-report separators are informational, not warnings.\r\n'
        'logdiv = "------------------------------------------------------------------------\\n"')],
    "gamma_dynamic_radiation_areas_from_arzsi.script": [(
        '          level.vertex_id(smart.position), ',
        '          -- Lost Zone: use the smart\'s own map vertex, never the currently loaded level.\r\n'
        '          smart.m_level_vertex_id, ')],
    "smr_pop.script": [(
        'local retarded_squad_names = {\r\n',
        'local retarded_squad_names = {\r\n'
        '    -- Lost Zone: GAMMA has no alpha sections for these factions.\r\n'
        '    ["ecolog_sim_squad_alpha"] = "ecolog_sim_squad_veteran",\r\n'
        '    ["zombied_sim_squad_alpha"] = "zombied_sim_squad_veteran",\r\n'), (
        '        trace("level %s not found, returning nil", level_name)',
        '        -- Lost Zone: maps without a monster spawn table use the caller\'s default.')],
    "craft_use_in_tooltip_mcm.script": [(
        'printf("1057 error fix")',
        '-- Lost Zone: an old update label, not an error.')],
    "grok_artefacts_random_condition.script": [(
        'printf("1057 error fix")',
        '-- Lost Zone: an old update label, not an error.')],
    "warfare.script": [(
        '\t\tprintf("~ Warfare is not loaded, unregistered warfare callbacks")',
        '\t\t-- Lost Zone: warfare is intentionally disabled in GAMMA; callbacks were removed.'), (
        'local new_surge = true\r\n',
        '-- Lost Zone: new_surge is declared before save_state.\r\n')],
    "release_restr_in_x16.script": [(
        '\t\t\talife_release(sobj, true)',
        '\t\t\t-- Lost Zone: second argument is the diagnostic release reason, not a boolean.\r\n'
        '\t\t\talife_release(sobj)')],
    "xrs_rnd_npc_loadout.script": [(
        '\t\t\t\tprinte("! ERROR: NPC Loadouts | wrong ammo_type set for [%s], missing value in ammo_class", section)',
        '\t\t\t\t-- Lost Zone: modded weapons can reduce ammo_class; the fallback above is valid.')],
    "smart_terrain.script": [(
        '\t\t\t\tprintf("validate_patrol_path WARNING: %s: invalid game_vertex_id for point %s",path_name,i)',
        '\t\t\t\t-- Lost Zone: invalid map patrol vertices reject this job via ret=false below.')],
    "ui_mcm.script": [(
        '\tif not opt_val[id] then\r\n\t\tprinte("!MCM given bad path:%s",id)\r\n\t\treturn\r\n\tend',
        '\t-- Lost Zone: mods read options they never put in the menu, with their own\r\n'
        '\t-- default (PAW, Faction ID, MilPDA, EA): not an error, no console line.\r\n'
        '\tif not opt_val[id] then\r\n\t\treturn\r\n\tend'), (
        'local GUI\r\n',
        '-- Lost Zone: GUI is declared before get_gui.\r\n')],
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
    if name in ("agdd_voiced_actor.script", "grok_loot_claim.script"):
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"{name}: pattern found {text.count(old)} times: {old[:60]!r}")
        text = text.replace(old, new)
    if name == "ui_mcm.script":
        text = '-- Lost Zone: get_gui must capture the same window used by UI_MCM.\r\nlocal GUI\r\n' + text
    elif name == "warfare.script":
        text = '-- Lost Zone: save_state must capture the same surge flag as actor_on_update.\r\nlocal new_surge = true\r\n' + text
    data = text.encode("latin-1")
    for side in ("client", "server"):
        (O / side / name).write_bytes(data)
    print("fixed", name)


STUB = '''-- Lost Zone server: Screen Space Shaders' {what} settings are client graphics.
-- A dedicated server renders nothing and has no MCM values for them: it sent
-- "{command}" with zeros, an invalid console command, on every start.
-- Other scripts only test that the module is present.
module_installed = true
function on_game_start() end
'''
def write_config(relative, text):
    data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("latin-1")
    for side in ("client", "server"):
        path = O / side / "configs" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def make_configs():
    # More z's than any GAMMA mod_system file: this correction wins DLTX order.
    name = "mod_system_" + "z" * 32 + "_lostzone_sound_fixes.ltx"
    assert all(name.lower() > p.name.lower() for p in (G.parent / "configs").glob("mod_system_*.ltx"))
    write_config(name, r'''; Lost Zone: fix missing sound paths; keep the weapons' existing sound layers.
![wpn_toz34_teivaz_snd_shoot]
snd_1_layer = weapons\toz34\mono\toz34_teivaz_mono_very_close1
snd_1_layer1 = weapons\toz34\mono\toz34_teivaz_mono_very_close2
snd_1_layer2 = weapons\toz34\mono\toz34_teivaz_mono_very_close3
snd_1_layer3 = weapons\toz34\mono\toz34_teivaz_mono_very_close4
![wpn_pm_custom]
snd_reload_empty = weapons\pm\pm_reload_empty
![wpn_glock]
snd_close = weapons\walther\walther_close
![wpn_glock_modern]
snd_close = weapons\walther\walther_close
![wpn_oc33]
snd_close = weapons\walther\walther_close
![wpn_m4_tac]
; Lost Zone: inherit wpn_m4_sounds instead of the nonexistent override sections.
!snd_shoot
!snd_silncer_shot
''')
    text = (G.parent / "configs/environment/effects.ltx").read_bytes().decode("latin-1")
    # The actual shipped sounds.db0 has wind1..4/storm1..3, no wind_01..10.
    # Keep the effect timing/strength and use the original wind recordings.
    winds = ("wind1", "wind2", "wind3", "wind4", "wind4",
             "wind_storm1", "wind_storm1", "wind_storm2", "wind_storm3", "wind_storm3")
    for index, name in enumerate(winds, 1):
        old, new = rf"nature\wind_{index:02}", rf"nature\{name}"
        assert old in text, old
        text = text.replace(old, new)
    write_config("environment/effects.ltx", "; Lost Zone: use existing wind sounds.\r\n" + text)
    write_config("scripts/military/smart/mod_mil_smart_terrain_7_7_zz_lostzone.ltx",
                 "; Lost Zone: MLR has no matching day_9 logic.\n![exclusive]\n!mil_7_7_xcvb_day_9\n")
    text = "; Lost Zone: MLR's copied 2_2 names do not match the 7_4 logic.\n![exclusive]\n"
    for period in ("day", "night"):
        for i in range(1, 7):
            text += f"!mil_2_2_xcvb_{period}_{i}\n"
            text += f"mil_7_4_xcvb_{period}_{i} = military\\mil_smart_terrain_7_4_smart_logic_xcvb.ltx\n"
    write_config("scripts/military/smart/mod_mil_smart_terrain_7_4_zz_lostzone.ltx", text)
    text = "; Lost Zone: MLR supplies day jobs only for this smart.\n![exclusive]\n"
    text += "".join(f"!cit_killers_vs_bandits_xcvb_night_{i}\n" for i in range(1, 8))
    write_config("scripts/dead_city/smart/mod_cit_killers_vs_bandits_zz_lostzone.ltx", text)


def make_sound_aliases():
    for src, dst in ((r"material/bullet/collide/bullet_hit_dirt_2.ogg", r"material/bullet/collide/bullet_hit_dirt_02.ogg"),
                     (r"material/bullet/collide/bullet_hit_dirt_3.ogg", r"material/bullet/collide/bullet_hit_dirt_03.ogg"),
                     (r"material/dropper/collide/water_1.ogg", r"material/dropper/collide/collide/water_1.ogg")):
        for side in ("client", "server"):
            target = O / side / "gamedata/sounds" / dst
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(G.parent / "sounds" / src, target)


def main():
    for name, pairs in FIXES.items():
        apply(name, pairs)
    for name, what, command in (("ssfx_water.script", "water", "ssfx_water (0,0,0,0)"),
                               ("ssfx_wetness.script", "wetness/gloss", "ssfx_gloss_minmax (0,0,0)")):
        (O / "server" / name).write_bytes(STUB.format(what=what, command=command).replace("\n", "\r\n").encode("ascii"))
        print("server stub", name)
    make_configs()
    make_sound_aliases()


if __name__ == "__main__":
    main()
