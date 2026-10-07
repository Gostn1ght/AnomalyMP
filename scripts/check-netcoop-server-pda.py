"""Execute the actual installer patch and pinned GAMMA timer/PDA code."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
refs = root / 'scripts/fixtures/server-pda'
def reference(name, digest):
    data = (refs / name).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(data).hexdigest() == digest, name
    return data

pda = reference('discover_spots.lua', 'e156cbb382af1c4cf0e644031af7a2e55ef5a30c3c8142b4710d8e7d8274efa9')
queue = reference('event_queue.lua', '1dbcaf7139d5f4e3a2450b7cc90650b92f82ebaf2c26a3aea3fb00fd201e7aba')
shell = shutil.which('pwsh') or shutil.which('powershell')
assert shell, 'PowerShell is needed to exercise the real installer'
guard = b'\tif not actor then return end -- Lost Zone: no local Actor on dedicated\n'

def patch(folder, succeeds=True):
    result = subprocess.run([shell, '-NoProfile', '-File', str(root / 'scripts/patch-netcoop-server-pda.ps1'),
                             '-ServerScripts', str(folder)], capture_output=True)
    assert (result.returncode == 0) == succeeds, result.stderr.decode(errors='replace')

def runtime(source):
    lua = LuaRuntime()
    lua.execute('''
        now = 0; db = { storage = {} }; trace = {}; world_ticks = 0
        function time_global() return now end
        function has_alife_info() return false end
        primary_objects_tbl = {one = {target='spot', hint='hint'}}
        distance_tbl = {marsh=40}; level = {name=function() return 'marsh' end}
        function get_story_object_id() return 7 end
        local position = { distance_to=function() return 5 end }
        db.storage[7] = {object={position=function() return position end}}
        test_actor = {dont_has_info=function() return true end, position=function() return position end}
        function give_info(id) trace[#trace+1]='info:'..id end
        game_statistics = {increment_rank=function(n) trace[#trace+1]='rank:'..n end}
        game = {translate_string=function(s) return s end}
        actor_menu = {set_fade_msg=function(h,t,n,s) trace[#trace+1]=h..':'..t..':'..s end}
        function fill_primary_objects() trace[#trace+1]='fill' end
    ''')
    lua.execute(queue.decode('latin1') + '\nfunction queue_state() return ev_queue end')
    lua.execute(source.decode('latin1'))
    lua.execute('''
        CreateTimeEvent(0, 'ScanForSpots', 2, discover_spots)
        CreateTimeEvent(0, 'WorldTick', 2, function() world_ticks=world_ticks+1; return true end)
    ''')
    return lua

def trace(lua):
    return list(lua.globals().trace.values())

before = runtime(pda)
before.globals().now = 2000
try:
    before.eval('ProcessEventQueue')()
except Exception as error:
    assert 'nil value' in str(error)
else:
    raise AssertionError('Unpatched empty-world PDA must reproduce the observed failure')

with tempfile.TemporaryDirectory(prefix='lostzone-pda-') as temp:
    folder = Path(temp)
    for newline in (b'\n', b'\r\n'):
        # Include CP1251 and another function: the patch must preserve all other bytes.
        prefix = b'-- \xcf\xe4\xe0\nfunction unrelated()\n local actor = db.actor\nend\n'
        original = (prefix + pda).replace(b'\n', newline)
        target = folder / 'pda.script'
        target.write_bytes(original)
        patch(folder)
        patched = target.read_bytes()
        assert patched == original.replace(b'\tlocal actor = db.actor' + newline,
                    b'\tlocal actor = db.actor' + newline + guard.replace(b'\n', newline))
        patch(folder)
        assert target.read_bytes() == patched, 'Installer must be idempotent'
        healthy = runtime(patched)
        healthy.globals().now = 2000
        healthy.eval('ProcessEventQueue')()
        assert healthy.globals().world_ticks == 1 and trace(healthy) == []
        assert healthy.eval('queue_state()[0].ScanForSpots.timer') == 5000
        healthy.execute('db.actor=test_actor; now=4999; ProcessEventQueue()')
        assert trace(healthy) == [], 'Original three-second reset must remain'
        healthy.execute('now=5000; ProcessEventQueue()')
        stock = runtime(pda)
        stock.execute('db.actor=test_actor; now=2000; ProcessEventQueue()')
        assert trace(healthy) == trace(stock) and len(trace(stock)) == 4
        healthy.execute('db.actor=nil; now=8000; ProcessEventQueue()')
        assert healthy.eval('queue_state()[0].ScanForSpots.timer') == 11000
        healthy.execute('db.actor=test_actor; now=11000; ProcessEventQueue()')
        assert trace(healthy) == trace(stock) * 2, 'Leave/rejoin must use current actor'
    for unsupported in (b'function unrelated()\n local actor = db.actor\nend\n',
                        pda.replace(b'ResetTimeEvent(0,"ScanForSpots",3)', b'-- no reset')):
        target.write_bytes(unsupported)
        patch(folder, succeeds=False)
        assert target.read_bytes() == unsupported, 'Fail closed without damaging scripts'

print('PASS actual GAMMA Lua 5.1: reproduced nil actor; patched timer and world callback survive; actor discovery unchanged; leave/rejoin, bytes, idempotency and unsupported input checked')
