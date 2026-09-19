import importlib.util
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


profile = module('prepare_profile')
launch = module('launch_settings')
engine_patch = module('make_engine_patch')
gamma_content = module('materialize_gamma')
callbacks = module('callback_scripts')


class ToolsTest(unittest.TestCase):
    def test_meet_setup_resumes_after_actor_becomes_available(self):
        sys.path.insert(0, str(profile.REPO / '.work/python-lua'))
        from lupa.luajit21 import LuaRuntime
        source = (ROOT / 'tests/fixtures/meet_setup.lua').read_bytes()
        patched = callbacks.patch_meet(source)
        self.assertEqual(callbacks.patch_meet(patched), patched)
        lua = LuaRuntime()
        lua.execute('''
            db={}; evaluator_contact={}; Cmeet_manager={}; starts=0
            function character_community(o) return o.community end
            game_relations={is_factions_enemies=function() return false end,
                            get_npcs_relation=function() return 0 end}
            game_object={enemy=2}
            xr_logic={parse_condlist=function(n,s,k,v) return v end}
            ini={r_string_ex=function() return 'true' end}
            npc={community='csky',alive=function() return false end}
            st={meet_manager={set_start_distance=function() starts=starts+1 end}}
            evaluator={a=st,object=npc}
        ''')
        lua.execute(patched.decode())
        lua.execute("init_meet(npc,ini,'no_meet',st,'walker')")
        self.assertFalse(lua.globals().st.meet_set)
        self.assertEqual(lua.globals().starts, 0)
        lua.execute('Cmeet_manager.update({a=st})')
        self.assertFalse(lua.globals().evaluator_contact.evaluate(lua.globals().evaluator))
        lua.execute("db.actor={community='actor_csky'}; evaluator_contact.evaluate(evaluator)")
        self.assertTrue(lua.globals().st.meet_set)
        self.assertIsNone(lua.globals().st.gamma_pending_meet)
        self.assertEqual(lua.globals().starts, 1)
        self.assertEqual(lua.globals().st.use, 'false')

    def test_combat_conditions_tolerate_spawn_and_disappearing_enemy(self):
        sys.path.insert(0, str(profile.REPO / '.work/python-lua'))
        from lupa.luajit21 import LuaRuntime
        original = (ROOT / 'tests/fixtures/combat_schemes.lua').read_bytes()
        patched = callbacks.patch_combat_schemes(original)
        self.assertEqual(callbacks.patch_combat_schemes(patched), patched)
        lua = LuaRuntime()
        lua.execute('''
            db={storage={}}
            function IsActor(o) return o and o.is_actor or false end
            function IsStalker() return true end
            function time_global() return 100 end
            local p={distance_to_sqr=function() return 400 end}
            npc={id=function() return 1 end,position=function() return p end,
                 memory_time=function() return 0 end,active_item=function() return nil end,health=1}
            enemy={id=function() return 2 end,position=function() return p end,health=1}
            level={object_by_id=function() return nil end}
        ''')
        lua.execute(patched.decode())
        state = lua.globals()
        for condition in (state.scheme_camper, state.scheme_cover):
            self.assertFalse(condition(None, state.npc, None))
            self.assertFalse(condition(state.enemy, state.npc, None))
        lua.execute('db.storage[1]={enemy_id=2}')
        self.assertFalse(state.scheme_camper(state.enemy, state.npc, None))
        self.assertFalse(state.scheme_cover(state.enemy, state.npc, None))
        self.assertFalse(state.pure_enemy_distance(state.npc, state.enemy))
        lua.execute('level.object_by_id=function() return enemy end')
        self.assertTrue(state.pure_enemy_distance(state.npc, state.enemy))

    def test_dynamic_anomaly_without_actor_preserves_npc_and_base_updates(self):
        sys.path.insert(0, str(profile.REPO / '.work/python-lua'))
        from lupa.luajit21 import LuaRuntime
        original = (ROOT / 'tests/fixtures/dynamic_anomaly_update.lua').read_bytes()
        patched = callbacks.patch_dynamic_anomalies(original)
        self.assertEqual(callbacks.patch_dynamic_anomalies(patched), patched)
        lua = LuaRuntime()
        lua.execute('''
            base_calls=0; npc_calls=0; actor_calls=0; db={}; AC_ID=0
            bind_anomaly_field={anomaly_field_binder={update=function() base_calls=base_calls+1 end}}
            anomalies_near_actor_functions={test=function() actor_calls=actor_calls+1 end}
            additional_articles_to_category={encyclopedia_anomalies={}}
            opened_articles={encyclopedia_anomalies={}}
            npc_on_near_anomalies_functions={test=function() npc_calls=npc_calls+1 end}
            anomaly_detector_ignore={test=true}
            function open_anomaly_article() end
            function IsStalker() return true end
            function IsMonster() return false end
            local pos={distance_to_sqr=function() return 0 end}
            local npc={alive=function() return true end,id=function() return 5 end,position=function() return pos end}
            level={iterate_nearest=function(p,r,fn) fn(npc) end}
            zone={section='test',radius=4,radius_sqr=16,object={position=function() return pos end}}
            player={position=function() return pos end}
        ''')
        lua.execute(patched.decode())
        lua.execute('bind_anomaly_field.anomaly_field_binder.update(zone,100)')
        state = lua.globals()
        self.assertEqual((state.base_calls, state.npc_calls, state.actor_calls), (1, 1, 0))
        lua.execute('db.actor=player; bind_anomaly_field.anomaly_field_binder.update(zone,100)')
        self.assertEqual((state.base_calls, state.npc_calls, state.actor_calls), (2, 2, 1))

    def test_dedicated_font_getters_do_not_require_ui_manager(self):
        patch = (ROOT / 'engine/gamma.patch').read_text(encoding='utf-8')
        self.assertIn('extern ENGINE_API bool g_dedicated_server;', patch)
        self.assertEqual(patch.count('return g_dedicated_server ? nullptr : mngr().pFont'), 10)

    def test_netcoop_level_and_console_help_guards_are_in_engine_patch(self):
        patch = (ROOT / 'engine/gamma.patch').read_text(encoding='utf-8')
        self.assertIn('if (!tok)', patch)
        self.assertIn('[NetAnomaly] server level %s version %s', patch)
        self.assertIn('game->level_name(Level().m_caServerOptions)', patch)
        self.assertIn('-\t\tMsg("[NetAnomaly] map sync forced OK', patch)
        self.assertNotIn('+\t\tMsg("[NetAnomaly] map sync forced OK', patch)
        self.assertIn('!strstr(Core.Params, "-netcoop") && !Level().IsChecksumsEqual', patch)
        self.assertIn('dedicated authority initial level forced to k00_marsh/hidden_base', patch)
        self.assertIn('actor()->m_tGraphID = GameGraph::_GRAPH_ID(136)', patch)
        self.assertIn('actor()->m_tNodeID = 75660', patch)
        self.assertIn('CObject* control_entity = Level().CurrentControlEntity()', patch)
        self.assertIn('const float act_distance = zone_reference ?', patch)
        self.assertIn('CActor* actor = Actor()', patch)
        self.assertIn('if (actor && luaObject)', patch)
        self.assertNotIn('+\t\t\t\tfloat distance = Actor()->Position().distance_to(Position());', patch)
        self.assertIn('GAMMA Dedicated Server Console [DEBUG]', patch)
        self.assertIn('WM_MOUSEWHEEL', patch)

    def test_ubgl_menu_close_without_actor_completes_callback(self):
        sys.path.insert(0, str(profile.REPO / '.work/python-lua'))
        from lupa.luajit21 import LuaRuntime
        source = b'local obj = db.actor:active_item()\nif not obj then return end\nreturn obj'
        source = b'function first()\n' + source + b'\nend\nfunction second()\n' + source + b'\nend'
        patched = callbacks.patch_ubgl(source)
        self.assertEqual(callbacks.patch_ubgl(patched), patched)
        lua = LuaRuntime()
        lua.execute('db = {}')
        lua.execute(patched.decode())
        self.assertTrue(lua.globals().first())
        lua.execute('db.actor = {active_item = function() return nil end}')
        self.assertTrue(lua.globals().second())
        lua.execute('db.actor = {active_item = function() return 42 end}')
        self.assertEqual(lua.globals().first(), 42)

    def test_ledge_waits_for_actor_not_loading_prompt(self):
        sys.path.insert(0, str(profile.REPO / '.work/python-lua'))
        from lupa.luajit21 import LuaRuntime
        lua = LuaRuntime()
        lua.execute('''
            callbacks = {}
            db = {}
            function RegisterScriptCallback(name, fn) callbacks[name] = fn end
            function actor_on_first_update() initialized = db.actor:position() end
        ''')
        source = b'RegisterScriptCallback("on_loading_screen_key_prompt", actor_on_first_update)'
        patched = callbacks.patch_ledge(source)
        self.assertEqual(callbacks.patch_ledge(patched), patched)
        lua.execute(patched.decode())
        self.assertIsNone(lua.globals().callbacks.on_loading_screen_key_prompt)
        lua.execute('db.actor = { position = function() return 42 end }; callbacks.actor_on_first_update()')
        self.assertEqual(lua.globals().initialized, 42)

    def test_profile_priorities_and_duplicates(self):
        text = '+A\n+A\n+G.A.M.M.A. Books Pass Time\n-B\n+GAMMA NetAnomaly - server\n'
        result, disabled = profile.transform_modlist(text, 'client')
        self.assertEqual(result.splitlines()[1], '+GAMMA NetAnomaly - client')
        self.assertEqual(result.count('+A\n'), 1)
        self.assertIn('-G.A.M.M.A. Books Pass Time\n', result)
        self.assertEqual(disabled, ['G.A.M.M.A. Books Pass Time'])
        self.assertNotIn('+GAMMA NetAnomaly - server', result)

    def test_source_preserved_and_existing_output_rejected(self):
        modlist = profile.REPO / 'G.A.M.M.A/modpack_data/modlist.txt'
        axr = profile.REPO / 'G.A.M.M.A/modpack_patches/gamedata/scripts/axr_main.script'
        before = modlist.read_bytes(), axr.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'bundle'
            profile.prepare(modlist, output, 'server', axr)
            with self.assertRaises(ValueError):
                profile.prepare(modlist, output, 'server', axr)
            patched = next(output.rglob('axr_main.script')).read_bytes()
            self.assertEqual(patched.count(b'gamma_net_compat.install()'), 1)
            self.assertEqual(profile.patch_axr(patched), patched)
            self.assertIn(b'imgui_on_render = {}', patched)
            menu = next(output.rglob('ui_main_menu.script')).read_bytes()
            self.assertEqual(menu.count(b'gamma_net_compat.unavailable()'), 4)
            self.assertEqual(profile.patch_menu(menu), menu)
        self.assertEqual(before, (modlist.read_bytes(), axr.read_bytes()))

    def test_launcher_injection_and_capacity(self):
        for nickname in ['bad/name', 'name) -start server(', 'a"b', 'a b', 'a' * 33]:
            with self.assertRaises(ValueError):
                launch.settings('client', nickname=nickname)
        for players in (0, 129, -1):
            with self.assertRaises(ValueError):
                launch.settings('server', players=players)
        with self.assertRaises(ValueError):
            launch.settings('server', port=65535, client_port=65535)
        args = launch.settings('server')['arguments']
        self.assertIn('/maxplayers=128)', args)
        self.assertIn('/portsv=1237/', args)
        self.assertIn('client(localhost/', args)
        self.assertNotIn('server(', launch.settings('client')['arguments'])

    def test_both_roles_block_single_player_menu(self):
        menu = (profile.REPO / 'G.A.M.M.A/modpack_addons/109- MCM Mod Configuration Menu - RavenAscendant/gamedata/scripts/ui_main_menu.script').read_bytes()
        result = profile.patch_menu(menu)
        for name in ('OnButton_save_clicked', 'OnButton_load_clicked', 'OnButton_last_save', 'OnButton_new_game'):
            entry = result.index(('function main_menu:' + name + '(').encode())
            first_statement = result[entry:].splitlines()[1].strip()
            self.assertEqual(first_statement, b'do return gamma_net_compat.unavailable() end')

    def test_save_callback_blocks_server_and_client(self):
        # Exercise the actual Lua module, including role lookup and callback registration.
        sys.path.insert(0, str(profile.REPO / '.work/python-lua'))
        try:
            from lupa import LuaRuntime
        except ImportError:
            self.skipTest('Lua runtime unavailable')
        script = (ROOT / 'runtime/gamedata/scripts/gamma_net_compat.script').read_text()
        for role in ('server', 'client'):
            lua = LuaRuntime()
            lua.globals().test_role = role
            lua.execute('''
                function ini_file(path) return {r_string=function() return test_role end} end
                function printf(...) end
                callbacks = {}
                function RegisterScriptCallback(name, fn) callbacks[name] = fn end
            ''')
            lua.execute(script)
            lua.globals().install()
            flags = lua.table_from({'ret': False})
            lua.globals().callbacks['on_before_save_input'](flags)
            self.assertTrue(flags.ret, role)

    def test_gamma_content_priorities_and_role_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, engine, output = root / 'GAMMA', root / 'engine/gamedata', root / 'runtime'
            mods = game / 'GAMMA RC3.7/mods'
            source_profile = game / 'GAMMA RC3.7/profiles/G.A.M.M.A'
            source_profile.mkdir(parents=True)
            (source_profile / 'modlist.txt').write_text('+High\n+Low\n', encoding='utf-8')
            for mod, value in [('High', 'gamma-unique-npc'), ('Low', 'lower-priority-npc')]:
                folder = mods / mod / 'gamedata/meshes'
                folder.mkdir(parents=True)
                (folder / 'npc.ogf').write_text(value)
            scripts = game / 'gamedata/scripts'
            scripts.mkdir(parents=True)
            (scripts / 'axr_main.script').write_bytes(b'local intercepts = {\n}\nfunction on_game_start()\nend\n')
            menu = b''
            for name in ('OnButton_save_clicked', 'OnButton_load_clicked', 'OnButton_last_save', 'OnButton_new_game'):
                menu += ('function main_menu:' + name + '()\nend\n').encode()
            (scripts / 'ui_main_menu.script').write_bytes(menu)
            (game / 'gamedata/configs').mkdir()
            (game / 'gamedata/configs/system.ltx').write_text('[gamma]\n')
            (game / 'gamedata/configs/axr_options.ltx').write_text(
                '[character_creation]\nnew_game_faction =\nnew_game_map =\n[other]\nvalue = kept\n')
            engine.mkdir(parents=True)
            (engine / 'engine-only.txt').write_text('engine content')
            base = root / 'extracted-base'
            (base / 'scripts').mkdir(parents=True)
            (base / 'scripts/base-only.script').write_text('base callback')
            (base / 'configs').mkdir()
            (base / 'configs/system.ltx').write_text('[base]\n')
            (game / 'fsgame.ltx').write_text('\n'.join([
                '$app_data_root$ = true | false | $fs_root$ | appdata\\',
                '$game_data$ = true | true | $fs_root$ | gamedata\\',
                '$arch_dir$ = false | false | $fs_root$ | db\\',
                '$game_scripts$ = true | false | $game_data$ | scripts\\',
                '$game_config$ = true | false | $game_data$ | configs\\',
            ]))
            result = gamma_content.materialize(game, engine, output, copy=True, base_data=[base])
            self.assertTrue(result['content_prepared'])
            self.assertFalse(result['multiplayer_ready'])
            self.assertEqual((output / 'gamedata/meshes/npc.ogf').read_text(), 'gamma-unique-npc')
            self.assertEqual((output / 'gamedata/engine-only.txt').read_text(), 'engine content')
            self.assertEqual((scripts / 'ui_main_menu.script').read_bytes(), menu)
            for process_role, expected_role in [('server', 'server'), ('p1', 'client'), ('p2', 'client')]:
                fs = (output / ('fsgame_' + process_role + '.ltx')).read_text()
                self.assertIn(str(output / 'appdata' / process_role), fs)
                self.assertIn(str(output / expected_role / 'scripts'), fs)
                self.assertIn(str(output / 'gamedata'), fs)
                self.assertIn(str(game), fs)
                self.assertEqual(fs.splitlines()[0], '$fs_root$ = false | false | ' + str(output) + '\\')
                self.assertEqual(fs.count('$fs_root$ ='), 1)
                self.assertIn('$game_arch_mp$ = false | false | ' + str(output / 'mp') + '\\', fs)
                self.assertIn('role = ' + expected_role, (output / expected_role / 'configs/gamma_net_role.ltx').read_text())
                self.assertEqual((output / expected_role / 'configs/system.ltx').read_text(), '[gamma]\n')
                self.assertEqual((output / expected_role / 'scripts/base-only.script').read_text(), 'base callback')
            gamma_content.finalize(output)
            self.assertEqual((output / 'fsgame_p2.ltx').read_text(), fs)
            server_options = (output / 'server/configs/axr_options.ltx').read_text()
            client_options = (output / 'client/configs/axr_options.ltx').read_text()
            self.assertIn('new_game_faction = csky', server_options)
            self.assertIn('new_game_map = hidden_base', server_options)
            self.assertIn('value = kept', server_options)
            self.assertIn('new_game_faction =\n', client_options)


if __name__ == '__main__':
    unittest.main()
