"""Mutant butchering online (actual netcoop_mutant_loot server module and
netcoop_mutant_loot_view client adapter, Lua 5.1): the server rolls GAMMA's
parts once per body and keeps them; a decayed, already looted, living or
non-mutant body gives nothing; taking checks the counts against the server's
list, creates the parts for the player with GAMMA's condition rule, wears the
knife, marks the body looted when empty; the client window shows the server's
list and sends the chosen counts in the server's order."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
store = {}
function se_save_var(id, name, var, val) store[id] = store[id] or {}; store[id][var] = val end
function se_load_var(id, name, var) return store[id] and store[id][var] end
now = 1000
local time_mt = {}
time_mt.__index = time_mt
function time_mt:diffSec(o) return self.v - o.v end
game = {get_game_time = function() return setmetatable({v = now}, time_mt) end}
function ini_file() return {r_float_ex = function() return 7200 end} end
db = {storage = {}}
rolls = 0
ui_mutant_loot = {loot_mutant = function(sec, cls, loot, npc, dont_create, victim)
    rolls = rolls + 1
    loot.mutant_part_dog_tail = {count = 1}
    loot.meat_dog = {count = 2}
end}
knife = 0
item_knife = {degradate = function() knife = knife + 1 end}
made = {}
function alife_create_item(sec, actor, props) made[#made + 1] = sec; assert(props.cond_ct == "part") end
sent = {}
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = {id, ch, data} end
valuable = {}
xr_corpse_detection = {set_valuable_loot = function(id, v) valuable[id] = v end}
clsid = {crow = 99}
function body(id, alive, monster)
    local o = {}
    function o:id() return id end
    function o:name() return "body" .. id end
    function o:section() return "dog_weak" end
    function o:clsid() return 1 end
    function o:alive() return alive end
    function o:is_monster() return monster end
    return o
end
player = {id = function() return 7 end}
''')
g.netcoop_mutant_loot = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_mutant_loot, (root / "server/netcoop_mutant_loot.script").read_text(encoding="utf-8"))
act = g.netcoop_mutant_loot.action
last = lambda: lua.eval("sent[#sent][3]")

lua.execute("dog = body(10, false, true); db.storage[10] = {death_time = setmetatable({v = 900}, getmetatable(game.get_game_time()))}")
assert act(g.player, g.dog, "mloot_open") == "" and last() == "10|ok|meat_dog*2;mutant_part_dog_tail*1"
assert act(g.player, g.dog, "mloot_open") == "" and g.rolls == 1  # rolled once, kept with the body
# Take: counts in the server's order (meat_dog, tail).
assert act(g.player, g.dog, "mloot_take 3,0") == "the list changed"
assert act(g.player, g.dog, "mloot_take 1") == "the list changed"
assert act(g.player, g.dog, "mloot_take 0,0") == "nothing selected"
assert act(g.player, g.dog, "mloot_take 1,1") == ""
assert list(g.made.values()) == ["meat_dog", "mutant_part_dog_tail"] or sorted(g.made.values()) == ["meat_dog", "mutant_part_dog_tail"]
assert g.knife == 2 and last() == "10|ok|meat_dog*1" and g.valuable[10] is True
assert lua.eval("store[10].looted") is False
assert act(g.player, g.dog, "mloot_take all") == "" and last() == "10|empty|"
assert lua.eval("store[10].looted") is True and g.valuable[10] is False
assert act(g.player, g.dog, "mloot_open") == "" and last() == "10|empty|"
# Decayed, looted by an NPC, alive, not a mutant.
lua.execute("old = body(11, false, true); db.storage[11] = {death_time = setmetatable({v = -9000}, getmetatable(game.get_game_time()))}")
assert act(g.player, g.old, "mloot_open") == "" and last() == "11|decayed|"
lua.execute("npc_looted = body(12, false, true); store[12] = {looted = true}")
assert act(g.player, g.npc_looted, "mloot_open") == "" and last() == "12|empty|"
assert act(g.player, lua.eval("body(13, true, true)"), "mloot_open") == "this is not a mutant body"
assert act(g.player, lua.eval("body(14, false, false)"), "mloot_open") == "this is not a mutant body"
assert g.rolls == 1

# Client window.
lua.execute(r'''
requests = {}
function netcoop_item_action(kind, id, target, action) requests[#requests + 1] = {kind, id, target, action} end
msgs = {}
actor_menu = {set_msg = function(_, m) msgs[#msgs + 1] = m end}
game.translate_string = function(s) return s end
UI = {}
UI.__index = UI
function UI.new() return setmetatable({shown = false}, UI) end
function UI:IsShown() return self.shown end
function UI:ShowDialog() self.shown = true end
function UI:Reset(obj) self.id = obj:id(); return self:FillList() end
reinit = nil
-- GAMMA's window class: instances read methods from UI, the adapter writes them there.
ui_mutant_loot = {}
ui_mutant_loot.UIMutantLoot = setmetatable({}, {__call = function() local u = UI.new(); u.CC = {cell = {}, Reinit = function(_, inv) reinit = inv end}; return u end, __index = UI, __newindex = UI})
registered = 0
function Register_UI() registered = registered + 1 end
level = {object_by_id = function(id) return body(id, false, true) end}
''')
g.netcoop_mutant_loot_view = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_mutant_loot_view, (root / "client/netcoop_mutant_loot_view.script").read_text(encoding="utf-8"))
lua.execute(r'''
netcoop_mutant_loot_view.install()
ui_mutant_loot.start(body(20, false, true))
assert(requests[1][1] == 2 and requests[1][2] == 20 and requests[1][4] == "mloot_open")
netcoop_mutant_loot_view.receive("21|ok|meat_dog*2")     -- not asked: ignored
assert(registered == 0)
netcoop_mutant_loot_view.receive("20|ok|meat_dog*2;mutant_part_dog_tail*1")
assert(registered == 1 and #reinit == 3 and reinit[1] == "meat_dog" and reinit[3] == "mutant_part_dog_tail")
local req = netcoop_mutant_loot_view.take_request({meat_dog = {count = 2}, mutant_part_dog_tail = {count = 1}}, {mutant_part_dog_tail = 1}, false)
assert(req == "0,1")
assert(netcoop_mutant_loot_view.take_request({}, {}, true) == "all")
assert(netcoop_mutant_loot_view.take_request({meat_dog = {count = 1}}, {}, false) == nil)
ui_mutant_loot.start(body(22, false, true)); netcoop_mutant_loot_view.receive("22|decayed|")
assert(msgs[#msgs] == "st_body_decayed")
''')
print("netcoop mutant loot: OK")
