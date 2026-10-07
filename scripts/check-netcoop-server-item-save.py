"""Actual installer and GAMMA personal inventory save: no blanket exception skip."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
source = (root / 'scripts/fixtures/server-item-save/save_state.lua').read_bytes().replace(b'\r\n', b'\n')
assert hashlib.sha256(source).hexdigest() == '92e77460b865ff8209f38f8419b1c70cc2ab228155953aa7f11cc5159c3c09ed'
shell = shutil.which('pwsh') or shutil.which('powershell')
assert shell, 'PowerShell is required to test the actual installer'
guard = b'\tif not db.actor then return end -- Lost Zone: no local player inventory in world save\n'

def patch(folder, succeeds=True):
    result = subprocess.run([shell, '-NoProfile', '-File', str(root / 'scripts/patch-netcoop-server-item-save.ps1'),
                             '-ServerScripts', str(folder)], capture_output=True)
    assert (result.returncode == 0) == succeeds, result.stderr.decode(errors='replace')

def runtime(code):
    lua = LuaRuntime()
    lua.execute('''
      db={}; calls=0; slot=nil
      function item(sec) return { section=function() return sec end } end
      items={item('bolt'),item('bolt'),item('bolt_bullet'),item('bread')}
      actor={
        inventory_for_each=function(self, callback)
          calls=calls+1
          for _, obj in ipairs(items) do assert(callback(obj)==false) end
        end,
        item_in_slot=function(self, n) assert(n==6); return slot end
      }
      data={untouched={value=123}, bolts={bolt=17}, bolt_slot='previous'}
    ''')
    lua.execute(code.decode('latin1'))
    return lua

old = runtime(source)
try:
    old.execute('save_state(data)')
except Exception as error:
    assert 'nil value' in str(error)
else:
    raise AssertionError('Unpatched nil-actor save must reproduce the observed failure')

with tempfile.TemporaryDirectory(prefix='lostzone-item-save-') as temp:
    folder = Path(temp)
    target = folder / 'itms_manager.script'
    for newline in (b'\n', b'\r\n'):
        original = (b'-- \xe1\xee\xeb\xf2\xfb\n' + source + b'\nfunction unrelated() return 42 end\n').replace(b'\n', newline)
        target.write_bytes(original)
        patch(folder)
        patched = target.read_bytes()
        assert patched.replace(guard.replace(b'\n',newline), b'') == original
        patch(folder)
        assert target.read_bytes() == patched, 'Idempotent installation'
        lua = runtime(patched)
        lua.execute('''
          local old_bolts=data.bolts; local old_other=data.untouched
          save_state(data)
          assert(data.bolts==old_bolts and data.bolt_slot=='previous' and data.untouched==old_other)
          assert(calls==0)
          local empty={}; save_state(empty); assert(next(empty)==nil)
        ''')
        for scenario in ('db.actor=actor; slot=nil', "db.actor=actor; slot=item('bolt_bullet')",
                         "db.actor=actor; items={}; slot=item('bolt')"):
            expected = runtime(source)
            actual = runtime(patched)
            for instance in (expected, actual):
                instance.execute(scenario + '; save_state(data)')
                instance.execute('assert(data.untouched.value==123 and calls==1)')
            assert dict(actual.globals().data.bolts.items()) == dict(expected.globals().data.bolts.items())
            assert actual.globals().data.bolt_slot == expected.globals().data.bolt_slot
        lua.execute("db.actor=actor; slot=item('bolt'); save_state(data); db.actor=nil; save_state(data)")
        assert lua.globals().data.bolt_slot == 'bolt' and lua.globals().calls == 1
        lua.execute("db.actor=actor; items={item('bolt_bullet')}; slot=nil; save_state(data)")
        assert dict(lua.globals().data.bolts.items()) == {'bolt_bullet': 1}, 'Rebind must use current inventory'
        lua.execute("actor.inventory_for_each=function() error('inventory API failure') end")
        try:
            lua.execute('save_state(data)')
        except Exception as error:
            assert 'inventory API failure' in str(error)
        else:
            raise AssertionError('Real actor save errors must remain visible')
    for unsupported in (b'function unrelated() end\n', source + source,
                        source.replace(b'db.actor:inventory_for_each(itr)', b'custom_inventory()')):
        target.write_bytes(unsupported)
        patch(folder, succeeds=False)
        assert target.read_bytes() == unsupported

print('PASS actual GAMMA Lua5.1: reproduced empty-world save failure; guarded nil actor preserves state; original inventory/bolt counts/slot, rebinding, API errors, bytes and installer idempotency checked')
