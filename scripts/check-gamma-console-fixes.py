"""Compile overlay Lua and exercise radiation vertices, squad aliases and Ogg headers."""
import importlib.util
from pathlib import Path
import re
import struct
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixes = module("gamma_fixes", ROOT / "scripts/make-gamma-overlay-fixes.py")
ogg = module("xray_ogg", ROOT / "scripts/resample-xray-ogg.py")
lua = LuaRuntime(unpack_returned_tuples=True)
compile_lua = lua.eval("function(s) local f,e=loadstring(s); return f~=nil,e end")
for side in ("client", "server"):
    for name in fixes.FIXES:
        data = (fixes.O / side / name).read_bytes()
        assert b"\n" not in data.replace(b"\r\n", b""), name
        ok, error = compile_lua(data.decode("latin-1"))
        assert ok, (name, error)
    radiation = (fixes.O / side / "gamma_dynamic_radiation_areas_from_arzsi.script").read_text(encoding="latin-1")
    start = radiation.index("function spawn_radiation_fields_for_level(")
    end = radiation.index("--Creates a new radiation field", start)
    lua.execute('''
      run_script=1; blacklisted_smarts={foreign={}}
      level={vertex_id=function() error("foreign-map vertex lookup") end}
      function printf() end
      function get_smart_terrains_of_level()
       return {{name=function() return "foreign_smart" end,position="foreign_position",m_game_vertex_id=27,m_level_vertex_id=8123}}
      end
      created=0
      function create_radiation_field(section,position,gvid,lvid,radius)
       assert(section=="radiation" and position=="foreign_position" and gvid==27 and lvid==8123 and radius==20)
       created=created+1
      end
    ''')
    lua.execute(radiation[start:end])
    lua.execute('spawn_radiation_fields_for_level({Name="foreign",Chance_to_spawn=100,Radiation_field="radiation",Radius=20}); assert(created==1)')
    population = (fixes.O / side / "smr_pop.script").read_text(encoding="latin-1")
    aliases = re.search(r"local retarded_squad_names = (\{.*?\n\})", population, re.S).group(1)
    lua.execute("aliases=" + aliases)
    lua.execute('''
      assert(aliases.ecolog_sim_squad_alpha=="ecolog_sim_squad_veteran")
      assert(aliases.zombied_sim_squad_alpha=="zombied_sim_squad_veteran")
      assert(aliases.duty_sim_squad_alpha=="dolg_sim_squad_alpha")
    ''')
    audio = (fixes.O / side / "gamedata/sounds/anomaly/teleport_work_2.ogg").read_bytes()
    headers = list(ogg.packets(audio))[:3]
    assert headers[0][:7] == b"\x01vorbis" and struct.unpack_from("<I", headers[0], 12)[0] == 48000
    assert headers[1] == (ROOT / "scripts/fixtures/gamma-console/teleport-vorbis-comments.bin").read_bytes()
    for page in ogg.pages(audio):
        raw = bytearray(page)
        checksum = struct.unpack_from("<I", raw, 22)[0]
        raw[22:26] = bytes(4)
        assert ogg.crc(raw) == checksum

compat = (fixes.O / "server/netcoop_server_compat.script").read_text(encoding="latin-1")
start = compat.index('\tif type(db.storage) == "table" and db.storage[STORY_AC_ID] == nil then', compat.index('function install()'))
block = compat[start:compat.index('\n\tinstall_actor_conditions()', start)]
lua.execute('STORY_AC_ID=0; db={storage={}}')
lua.execute(block)
lua.execute('assert(db.actor==nil); db.storage[0].pstor.nightvision="saved"; original=db.storage[0]')
lua.execute(block)
lua.execute('assert(db.actor==nil and db.storage[0]==original and original.pstor.nightvision=="saved")')
print("PASS GAMMA console fixes: Lua 5.1 syntax/CRLF, foreign-map radiation vertex, valid squad aliases, anchor storage without player, 48 kHz Ogg checksums and exact binary X-Ray comments")
