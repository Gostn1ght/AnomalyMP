import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from admin_scripts import patch_debug
from lupa.luajit21 import LuaRuntime


class AdminScriptsTest(unittest.TestCase):
    def test_direct_calls_and_menu_are_server_requests(self):
        lua = LuaRuntime()
        lua.execute('''
            allowed=false; server=false; mutations=0; requests={}
            gamma_net_compat={admin_allowed=function() return allowed end,
                is_server=function() return server end,
                request_admin=function(text) table.insert(requests,text); return true end}
            UIDebugMain={}; UIDebug_ItemSpawn={}
        ''')
        source = b'''function kill_npc() mutations=mutations+1 end
function UIDebugMain:Execute(tab,index)
    mutations=mutations+1
end
function UIDebugMain:OnConsoleInput()
    mutations=mutations+1
end
function start_debug_main(owner)
    mutations=mutations+1
end
function UIDebug_ItemSpawn:Spawn(section)
    mutations=mutations+1
end
'''
        # Installed GAMMA declarations occupy a separate line from the body.
        source = source.replace(b'function kill_npc() mutations=mutations+1 end',
                                b'function kill_npc()\n mutations=mutations+1\nend')
        patched = patch_debug(source, 'ui_debug_launcher.script')
        self.assertEqual(patched, patch_debug(patched, 'ui_debug_launcher.script'))
        lua.execute(patched.decode())
        lua.execute('kill_npc(); UIDebugMain:Execute("toggle",1); UIDebugMain:OnConsoleInput(); start_debug_main(); UIDebug_ItemSpawn:Spawn("wpn_ak74")')
        self.assertEqual(lua.globals().mutations, 0)
        self.assertEqual(len(lua.globals().requests), 0)
        lua.execute('allowed=true; kill_npc(); UIDebugMain:Execute("toggle",1)')
        self.assertEqual(lua.globals().mutations, 0)
        self.assertEqual(lua.globals().requests[1], 'debug_named kill_npc')
        self.assertEqual(lua.globals().requests[2], 'debug_action toggle 1')
        lua.execute('UIDebug_ItemSpawn:Spawn("wpn_ak74")')
        self.assertEqual(lua.globals().mutations, 0)
        lua.execute('server=true; kill_npc()')
        self.assertEqual(lua.globals().mutations, 1)

    def test_dispatcher_rechecks_role_and_uses_server_action(self):
        lua = LuaRuntime()
        lua.execute('''
            allowed=false; mutations=0
            gamma_net_compat={is_server=function() return true end}
            gamma_admin_peer_allowed=function(cid) return allowed and cid=="12345678" end
            ui_debug_launcher={content={action={{functor={function() mutations=mutations+1 end}}}}}
            exec=function(fn,...) fn(...) end
        ''')
        lua.execute((ROOT / 'runtime/gamedata/scripts/gamma_admin.script').read_text())
        dispatch = lua.globals().on_client_command
        self.assertIn('required', dispatch('12345678', 'admin', 12, 'debug_action action 1'))
        lua.globals().allowed = True
        self.assertIn('executed', dispatch('12345678', 'admin', 12, 'debug_action action 1'))
        self.assertEqual(lua.globals().mutations, 1)
        self.assertIn('Invalid', dispatch('12345678', 'admin', 12, 'debug_action action 999'))
        self.assertIn('Recursive', dispatch('12345678', 'admin', 12, 'cmd sv_cmd help'))
        lua.globals().allowed = False
        self.assertIn('required', dispatch('12345678', 'admin', 12, 'debug_action action 1'))
        self.assertEqual(lua.globals().mutations, 1)


if __name__ == '__main__':
    unittest.main()
