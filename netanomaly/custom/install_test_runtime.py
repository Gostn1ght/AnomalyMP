"""Install the small Custom test overlay into an already prepared isolated copy."""
import argparse
import re
import shutil
from pathlib import Path


def install(root):
    if not (root / 'custom-test-manifest.json').is_file():
        raise ValueError('Expected a prepared Custom test directory')
    scripts = root / 'gamedata/scripts'
    axr = scripts / 'axr_main.script'
    data = axr.read_bytes()
    if b'imgui_on_render' not in data:
        anchor = b'local intercepts = {'
        if data.count(anchor) != 1:
            raise ValueError('Custom callback table not found')
        data = data.replace(anchor, anchor + b'\n\timgui_on_render = {},')
        axr.write_bytes(data)
    for source in (Path(__file__).parent / 'runtime').glob('*.script'):
        shutil.copy2(source, scripts / source.name)

    # Optional Custom class aliases are absent in some Monolith/NetAnomaly builds.
    patches = scripts / '_g_patches.script'
    data = patches.read_bytes()
    # This Custom patch assumes a global registry, whereas the supplied callback
    # module keeps its registry in callbacks_gameobject's namespace. Query the
    # engine's live object list, also used by the original function as fallback.
    data = data.replace(b'local obj = gameobjects_registry[id] or level.object_by_id(id)',
                        b'local obj = level.object_by_id(id)')
    data = data.replace(b'if (id == nil or id > 65535) then',
                        b'if type(id) ~= "number" or id ~= id or id < 0 or id > 65535 or id % 1 ~= 0 then')
    # The optional registry is only used to print per-section diagnostics here.
    data = data.replace(b'for id, obj in pairs(server_objects_registry) do',
                        b'for id, obj in pairs(server_objects_registry or {}) do')
    for name in (b'weapon_classes', b'launcher'):
        pattern = rb'local ' + name + rb' = \{\s*\[clsid.wpn_ssrs\]\s*= true,\s*\[clsid.wpn_ssrs_s\]\s*= true,\s*\}'
        replacement = (b'local ' + name + b' = {}\n'
                       b'\tif clsid.wpn_ssrs then ' + name + b'[clsid.wpn_ssrs] = true end\n'
                       b'\tif clsid.wpn_ssrs_s then ' + name + b'[clsid.wpn_ssrs_s] = true end')
        data = re.sub(pattern, lambda _: replacement, data)
    patches.write_bytes(data)

    # Both mods replace the same native-derived INI class; reapplying the wrapper
    # methods recurses through self.ini == self. Keep Anomaly's composition-based
    # ini_file_ex instead. Explicit native base calls also fail with this luabind.
    for name in ('_g_patches.script', 'aaaa_script_fixes_mp.script'):
        file = scripts / name
        if file.is_file():
            data = file.read_bytes()
            start = b'-- Disable caching of ini values'
            end = b'_G.ini_file_ex = new_ini_file_ex'
            if start in data:
                if data.count(start) != 1 or data.count(end) != 1:
                    raise ValueError('Unexpected INI override block in ' + name)
                begin = data.index(start)
                finish = data.index(end, begin) + len(end)
                data = data[:begin] + b'-- Custom multiplayer: retain the original Anomaly ini_file_ex.\n' + data[finish:]
            file.write_bytes(data)

    # The supplied radiation patch lost its sleep method declaration and outer if.
    file = scripts / 'aaarszi_radiation_monkeypatches.script'
    if file.is_file():
        data = file.read_bytes()
        anchor = b'\t\tlocal bleeding = db.actor.bleeding > 0'
        if b'function ui_sleep_dialog.UISleep:TestAndShow(force)' not in data and data.count(anchor) == 1:
            data = data.replace(anchor, b'function ui_sleep_dialog.UISleep:TestAndShow(force)\n\tif force ~= true then\n' + anchor)
            end = b'\tself:Initialize()'
            if data.count(end) != 1:
                raise ValueError('Unexpected radiation sleep patch')
            data = data.replace(end, b'\tend\n' + end)
            file.write_bytes(data)

    # These disabled XML patches contain [[...]] strings inside --[[...]] comments.
    # A higher-level long comment preserves their disabled state and parses correctly.
    for name in ('modxml_al_mapspots', 'modxml_al_questarrow'):
        for suffix in ('', '_219', '_43'):
            file = scripts / (name + suffix + '.script')
            if not file.is_file():
                continue
            data = file.read_bytes()
            if data.startswith(b'--[[') and data.rstrip().endswith(b'--]]'):
                data = b'--[=[' + data[4:]
                end = data.rfind(b'--]]')
                data = data[:end] + b'--]=]' + data[end + 4:]
                file.write_bytes(data)

    file = scripts / 'utjan_mag_check.script'
    if file.is_file():
        data = file.read_bytes().replace(
            b'if ammo_check_mcm.actor_on_hud_animation_play then',
            b'if ammo_check_mcm and ammo_check_mcm.actor_on_hud_animation_play then')
        file.write_bytes(data)

    # Lua sorting requires an irreflexive comparator, including the pinned MCM row.
    file = scripts / 'ui_mcm.script'
    if file.is_file():
        data = file.read_bytes().replace(b'if a.id == "mcm" then return true end',
                                         b'if a.id == "mcm" then return b.id ~= "mcm" end')
        file.write_bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('root', type=Path)
    install(parser.parse_args().root)
