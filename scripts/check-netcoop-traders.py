"""A trader on every location (owner 2026-10-09): the actual netcoop_traders
script and traders.ltx. Every map without a GAMMA trader gets exactly one
neutral trader near its start point, once per world, never duplicated or
replaced after death; maps with GAMMA traders get none; the trader keeps its
own assortment over GAMMA's generic one."""
import re
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
ltx = (root / "scripts/netcoop-overlay/server/configs/netcoop/traders.ltx").read_text(encoding="ascii")
sections, cur = {}, None
for line in ltx.splitlines():
    line = line.split(";")[0].strip()
    m = re.match(r"^\[(.+)\]$", line)
    if m:
        cur = m.group(1); sections[cur] = {}; continue
    if cur and "=" in line:
        k, v = [x.strip() for x in line.split("=", 1)]
        sections[cur][k] = v

# The cluster catalogue: every map is either a GAMMA trader map or listed.
plan = (root / "scripts/netcoop-cluster/netcoop_cluster.ltx.full").read_text(encoding="utf-8", errors="replace")
maps = re.search(r"\[locations\](.*?)(\n\[|\Z)", plan, re.S).group(1)
cluster = [l.split("=")[0].strip() for l in maps.splitlines() if "=" in l and not l.strip().startswith(";")]
gamma_traders = {"jupiter", "jupiter_underground", "k00_marsh", "k01_darkscape", "k02_trucks_cemetery", "l01_escape",
                 "l02_garbage", "l03_agroprom", "l04_darkvalley", "l05_bar", "l07_military", "l08_yantar",
                 "l09_deadcity", "l10_red_forest", "pripyat", "zaton"}
added = set(sections["added"])
assert len(cluster) == 33, cluster
for m in cluster:
    assert (m in gamma_traders) != (m in added), "map %s: exactly one source of traders" % m

lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
g.cfg_sections = lua.table_from({k: lua.table_from(v) for k, v in sections.items()})
lua.execute(r'''
tick = 0
function time_global() return tick end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
function netcoop_enabled() return true end
function netcoop_pure_client() return false end
state = {}
alife_storage_manager = {get_state = function() return state end}
function ini_file() return {
    r_string_ex = function(_, s, k) local t = cfg_sections[s] return t and t[k] end,
    r_float_ex = function(_, s, k) local t = cfg_sections[s] return t and tonumber(t[k]) end} end
here = "l06_rostok"
created = {}
next_id = 100
function vector() local v = {x = 0, y = 0, z = 0}
    function v:setHP(h, p) self.h = h return self end
    function v:set(x, y, z) self.x, self.y, self.z = x, y, z return self end
    return v end
level = {present = function() return true end, name = function() return here end,
    valid_vertex = function(v) return v and v > 0 end,
    vertex_in_direction = function(v, dir, d) return v + 1 end,
    vertex_position = function(v) return vector():set(v, 0, 0) end}
anchor = {position = vector():set(0, 0, 0), m_level_vertex_id = 10, m_game_vertex_id = 5}
brain_calls = 0
sim = {actor = function() return anchor end}
function alife() return sim end
function alife_create(section, pos, lvid, gvid)
    next_id = next_id + 1
    local se = {id = next_id, section = section, lvid = lvid, gvid = gvid}
    se.brain = function() return {can_choose_alife_tasks = function(_, v) brain_calls = brain_calls + 1; se.stay = not v end} end
    created[#created + 1] = se
    return se
end
db = {actor = nil}
inits = {}
trade_manager = {trade_init = function(npc, cfg) inits[#inits + 1] = {npc:id(), cfg} end}
callbacks = {}
function RegisterScriptCallback(name, f) callbacks[name] = f end
''')
g.netcoop_traders = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_traders, (root / "scripts/netcoop-overlay/server/netcoop_traders.script").read_text(encoding="utf-8"))
lua.execute(r'''
local t = netcoop_traders
t.on_game_start()
local function frames(n) for _ = 1, n do tick = tick + 11000; t.update() end end
-- A listed map: one trader, next to the start point, told to stay.
frames(3)
assert(#created == 1, "one trader on a map without GAMMA traders")
local se = created[1]
assert(se.section == "stalker_silent" and se.lvid == 11 and se.gvid == 5 and se.stay, "near the start point, stays")
assert(state.netcoop_traders.l06_rostok == se.id and t.is_lost_zone_trader(se.id), "kept in the world state")
-- Killed or released: never replaced; a restart keeps the record.
created = {}
frames(3)
assert(#created == 0, "never replaced or duplicated")
-- A map with GAMMA traders: none.
here = "l01_escape"; frames(3)
assert(#created == 0, "maps with GAMMA traders get none")
-- Online: neutral, unkillable; its assortment wins over GAMMA's generic one.
local npc = {id = function() return se.id end,
    set_character_community = function(self, c) self.community = c end,
    invulnerable = function(self, v) self.inv = v end}
db.actor = {}
callbacks.npc_on_net_spawn(npc)
assert(npc.community == "trader" and npc.inv == true, "neutral and unkillable")
trade_manager.trade_init(npc, "items\\trade\\trade_generic.ltx")
assert(inits[#inits][2] == "items\\trade\\trade_stalker_basic.ltx", "own assortment kept")
local other = {id = function() return 5 end}
trade_manager.trade_init(other, "items\\trade\\trade_generic.ltx")
assert(inits[#inits][2] == "items\\trade\\trade_generic.ltx", "other NPCs untouched")
''')
print("Traders: one neutral unkillable trader on each of the %d maps without GAMMA traders, near the start point, "
      "once per world, never replaced; %d GAMMA trader maps untouched; own assortment kept PASS" % (len(added), len(gamma_traders)))
