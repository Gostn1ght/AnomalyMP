"""PDA network (actual netcoop_pdanet with the actual netcoop_transit serializer,
Lua 5.1): two location servers share one store. UIDs are unique and stable;
strangers are UID-only; a contact shows name/avatar, and online status only
when both added each other; the general channel and chats keep history;
a message to a player on another server (or offline) arrives by polling;
unread counts; groups only from contacts, deleted for all; anonymous general
messages; points validated; a non-member cannot post."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
store = {}
function netcoop_store_read(b, k) return (store[b] or {})[k] or "" end
function netcoop_store_swap(b, k, old, new)
    store[b] = store[b] or {}
    if (store[b][k] or "") ~= old then return false end
    store[b][k] = new ~= "" and new or nil
    return true
end
clock, tg = 1000000, 0
os.time = function() return clock end
function time_global() return tg end
game = {CTime = function() return {set = function() end} end,
        get_game_time = function() return {diffSec = function() return 600000 end} end}
function command_line() return "" end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
-- players: id -> {char, name, server}
players = {}
function netcoop_actor_character(id) return players[id] and players[id].char or "" end
level = {object_by_id = function(id)
    local p = players[id]
    if not p then return nil end
    return {character_name = function() return p.name end, character_icon = function() return "icon_" .. p.char end}
end}
current_server = 1
function netcoop_players()
    local t = {}
    for id, p in pairs(players) do if p.server == current_server then t[#t + 1] = id end end
    table.sort(t)
    return table.concat(t, ",")
end
inbox = {}
function netcoop_send_to_actor(id, ch, data)
    assert(ch == "pdanet")
    inbox[id] = inbox[id] or {}
    table.insert(inbox[id], data)
end
''')
g.netcoop_transit = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_transit, (root / "server/netcoop_transit.script").read_text(encoding="utf-8"))
src = (root / "server/netcoop_pdanet.script").read_text(encoding="utf-8")
servers = []
for i in range(2):
    t = lua.table()
    lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()", t, src)
    servers.append(t)
lua.execute(r'''
function take(id)  -- reassemble chunked messages -> list of {verb, value}
    local out, buf = {}, {}
    for _, d in ipairs(inbox[id] or {}) do
        local n, total, rest = string.match(d, "^(%d+)/(%d+)|(.*)$")
        buf[#buf + 1] = rest
        if n == total then
            local all = table.concat(buf); buf = {}
            local verb, ser = string.match(all, "^(%a+)|(.*)$")
            local ok, v = pcall(netcoop_transit.deserialize, ser)
            out[#out + 1] = {verb, ok and v or ser}
        end
    end
    inbox[id] = {}
    return out
end
''')
take = g.take
def cmd(server, pid, text):
    g.current_server = server + 1
    assert text.startswith("pdanet ")
    servers[server].command(pid, text[7:])  # netanomaly_server passes the arguments
    return [tuple(x.values()) for x in take(pid).values()]
def poll(server):
    g.current_server = server + 1
    g.tg += 2500
    servers[server].update_world()
def last(msgs, verb):
    got = [v for k, v in msgs if k == verb]
    assert got, (verb, msgs)
    return got[-1]

lua.execute('players[1] = {char = "a_1", name = "Bashka", server = 1}; players[2] = {char = "b_1", name = "Yura", server = 2}; players[3] = {char = "c_1", name = "Docent", server = 1}')
sa = last(cmd(0, 1, "pdanet hello"), "state")
sb = last(cmd(1, 2, "pdanet hello"), "state")
sc = last(cmd(0, 3, "pdanet hello"), "state")
ua, ub, uc = sa.uid, sb.uid, sc.uid
assert len({ua, ub, uc}) == 3 and all(len(u) == 6 and u.isdigit() for u in (ua, ub, uc))
assert last(cmd(0, 1, "pdanet hello"), "state").uid == ua  # stable

poll(0); poll(1)  # servers running: the first poll takes the current point
take(1); take(2); take(3)
# General channel: stranger shows as UID only; anonymous has no UID.
cmd(1, 2, "pdanet say 0 Hello stalkers")
poll(0)
gen = last([tuple(x.values()) for x in take(1).values()], "general")
m = gen[len(gen)]
assert m.x == "Hello stalkers" and m.f == ub and m.n is None
cmd(0, 3, "pdanet say 1 nobody knows me")
poll(1)
m = last([tuple(x.values()) for x in take(2).values()], "general")
assert m[len(m)].f == "" and m[len(m)].x == "nobody knows me"

# Contacts: a adds b -> name for a; online status only when mutual.
assert last(cmd(0, 1, "pdanet add 000000"), "err") in ("invalid UID", "no such UID")
st = last(cmd(0, 1, f"pdanet add {ub}"), "state")
c = st.contacts[1]
assert c.uid == ub and c.name == "Yura" and c.online is None
st = last(cmd(1, 2, f"pdanet add {ua}"), "state")
assert st.contacts[1].online is True
st = last(cmd(0, 1, "pdanet hello"), "state")
assert st.contacts[1].online is True
g.clock += 200   # b silent for 200 s (no heartbeat): offline
st = last(cmd(0, 1, "pdanet hello"), "state")
assert st.contacts[1].online is False

# DM across servers, while b is "offline": stored, delivered on poll, unread counted.
r = cmd(0, 1, f"pdanet dm {ub}")
chat = last(r, "chat")
cid = chat.id
assert cid.startswith("d_")
cmd(0, 1, f"pdanet msg {cid} text Let's go hunting")
cmd(0, 1, f"pdanet msg {cid} point Hunting spot\tk00_marsh 10.5 0 -20")
assert last(cmd(0, 1, f"pdanet msg {cid} point Bad\tnope"), "err") == "bad point"
poll(1)  # b's server: first look after login takes the list as known
st = last(cmd(1, 2, "pdanet hello"), "state")
s = [x for x in st.chats.values() if x.id == cid][0]
assert s.unread == 2 and s.last.x.startswith("Hunting") and s.peer.name == "Bashka"
cmd(0, 1, f"pdanet msg {cid} text are you there?")
poll(1)
new = last([tuple(x.values()) for x in take(2).values()], "new")
assert new.id == cid and new.msgs[1].x == "are you there?" and new.msgs[1].n == "Bashka"
o = last(cmd(1, 2, f"pdanet open {cid}"), "chat")
assert [x.x for x in o.msgs.values()] == ["Let's go hunting", "Hunting spot", "are you there?"]
assert o.msgs[2].k == "point" and o.msgs[2].d == "k00_marsh 10.5 0 -20"
st = last(cmd(1, 2, "pdanet hello"), "state")
assert [x for x in st.chats.values() if x.id == cid][0].unread == 0

# A stranger cannot post into that chat.
assert last(cmd(0, 3, f"pdanet msg {cid} text intruder"), "err") == "no such chat"

# Groups: only contacts become members; deleting removes it for everybody.
cmd(0, 1, f"pdanet add {uc}")
st = last(cmd(0, 1, f"pdanet group Scientists|icon_sci|{ub},{uc},123456"), "state")
grp = [x for x in st.chats.values() if x.kind == "g"][0]
assert grp.name == "Scientists" and grp.members == 3
gid = grp.id
cmd(1, 2, f"pdanet msg {gid} text Reasonable!")
poll(0)
new = last([tuple(x.values()) for x in take(1).values()], "new")
assert new.id == gid and new.msgs[1].x == "Reasonable!"
st = last(cmd(0, 3, "pdanet hello"), "state")
assert any(x.id == gid for x in st.chats.values())
cmd(0, 3, f"pdanet delete {gid}")
for pid, srv in ((1, 0), (2, 1), (3, 0)):
    st = last(cmd(srv, pid, "pdanet hello"), "state")
    assert not any(x.id == gid for x in st.chats.values()), pid
# Deleting a private chat removes it from my list only.
cmd(1, 2, f"pdanet delete {cid}")
assert not any(x.id == cid for x in last(cmd(1, 2, "pdanet hello"), "state").chats.values())
assert any(x.id == cid for x in last(cmd(0, 1, "pdanet hello"), "state").chats.values())

# History survives a "restart": a fresh module instance reads the same store.
fresh = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()", fresh, src)
g.current_server = 1
fresh.command(1, f"open {cid}")
o = last([tuple(x.values()) for x in take(1).values()], "chat")
assert len(o.msgs) == 3

# Client: the server's real chunks through netcoop_pdanet_client.
client = lua.table()
lua.execute(r"""
listeners_fired = 0
function netcoop_pure_client() return true end
function RegisterScriptCallback() end
game.translate_string = function(id) return "<" .. id .. ">" end
""")
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            client, (root / "client/netcoop_pdanet_client.script").read_text(encoding="utf-8"))
g.netcoop_pdanet_client = client
lua.execute("netcoop_pdanet_client.on_change(function() listeners_fired = listeners_fired + 1 end)")
g.current_server = 1
servers[0].command(1, "hello")
servers[0].command(1, f"open {cid}")
for chunk in list(g.inbox[1].values()):
    client.receive(chunk)
g.inbox[1] = lua.table()
assert client.me.uid == ua and client.me.name == "Bashka"
assert client.contacts[1] is not None and len(client.general) >= 2
assert client.opened.id == cid and len(client.opened.msgs) == 3
m = client.opened.msgs[1]
assert m.own is True and client.sender_name(m) == "Bashka"
anon = [x for x in client.general.values() if x.f == ""][0]
assert client.sender_name(anon) == "<st_pdanet_anonymous>"
assert client.when(lua.eval("{g = 60 * 24 * 31 + 75}")) == "01:15, 01.02.2012"
assert g.listeners_fired >= 2
# a chunked message (> 7000 bytes) is reassembled
big = "x" * 9000
lua.execute(f"netcoop_send_to_actor = netcoop_send_to_actor")
sent = []
data = "err|" + big
for n in range(2):
    client.receive(f"{n+1}/2|" + data[n*7000:(n+1)*7000])
assert client.last_error == big

# UI and configs: the tab script compiles; the strip and the strings exist.
ui = (root / "client/netcoop_pdanet_ui.script").read_text(encoding="utf-8")
assert lua.eval("function(s) return loadstring(s) ~= nil end")(ui)
import re, xml.etree.ElementTree as ET
pda = (root / "client/configs/ui/pda_16.xml").read_bytes().decode("cp1251")
ET.fromstring(pda.split("?>", 1)[1] if pda.startswith("<?xml") else pda)
ids = re.findall(r'<button [^>]*id="(\w+)"', pda)
assert ids == ["eptTasks", "eptTaskboard", "eptRanking", "eptRelations", "eptEncyclopedia", "eptLogs"], ids
assert all('width="137"' in b for b in re.findall(r"<button [^>]*>", pda))
ET.fromstring((root / "client/configs/ui/ui_netcoop_pdanet.xml").read_bytes().decode("cp1251").split("?>", 1)[1])
used = set(re.findall(r'"(st_pdanet_[a-z_]+)"', ui + (root / "client/netcoop_pdanet_client.script").read_text(encoding="utf-8")))
used |= {t + "_soon" for t in used if t.startswith("st_pdanet_tab_") and t not in ("st_pdanet_tab_general", "st_pdanet_tab_chats", "st_pdanet_tab_contacts", "st_pdanet_tab_map")}
used.add("st_pdanet_tab_map")
for lang in ("rus", "eng"):
    table = (root / f"client/configs/text/{lang}/st_netcoop.xml").read_bytes().decode("cp1251")
    missing = [k for k in used if f'id="{k}"' not in table]
    assert not missing, (lang, missing)
print("netcoop pdanet: OK")
