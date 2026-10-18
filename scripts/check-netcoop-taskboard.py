"""PDA task board, players' jobs (actual netcoop_taskboard with the actual
netcoop_transit serializer, Lua 5.1, owner 2026-10-18): posting takes the
reward from the poster at once; nobody takes his own job; one taker; the
poster confirms and the taker is paid through pda_pay (his location pays
it out); cancel returns the reward; a taker may drop it; per-player limit;
jobs expire after 7 days with a refund; never paid twice. The client's
board decodes the server's offers and jobs."""
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
clock = 1000000
os.time = function() return clock end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
players = {}
function netcoop_actor_character(id) return players[id] and players[id].char or "" end
level = {name = function() return "l01_escape" end}
function actor_of(id)
    local p = players[id]
    return {id = function() return id end, character_name = function() return p.name end,
            money = function() return p.money end, give_money = function(_, n) p.money = p.money + n end}
end
inbox = {}
function netcoop_send_to_actor(id, ch, data)
    assert(ch == "taskboard")
    inbox[id] = inbox[id] or {}
    table.insert(inbox[id], data)
end
''')
g.netcoop_transit = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_transit, (root / "server/netcoop_transit.script").read_text(encoding="utf-8"))
board = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            board, (root / "server/netcoop_taskboard.script").read_text(encoding="utf-8"))
lua.execute('players[1] = {char = "a_1", name = "Bashka", money = 5000}; players[2] = {char = "b_1", name = "Yura", money = 100}')


def cmd(pid, text):
    g.db = lua.eval("{}")
    g.db.actor = g.actor_of(pid)
    g.inbox[pid] = lua.table()
    board.command(pid, text)
    return list(g.inbox[pid].values())


def jobs(pid):
    msgs = cmd(pid, "list")
    body = [m for m in msgs if m.startswith("jobs|")][-1][5:]
    return list(g.netcoop_transit.deserialize(body).values())


def money(pid):
    return g.players[pid].money


assert "job|posted" in cmd(1, "post 3000|Kill the dog|Near the farm")
assert money(1) == 2000, "the reward leaves the poster at once"
assert "jobfail|money" in cmd(1, "post 9000|Too much|x"), "no job beyond his money"
assert "jobfail|bad" in cmd(1, "post 10|| empty title")
j = jobs(2)
assert len(j) == 1 and j[0].title == "Kill the dog" and j[0].by_name == "Bashka" and not j[0].mine and not j[0].taken
jid = j[0].id
assert jobs(1)[0].mine
assert "jobfail|own" in cmd(1, f"take {jid}"), "nobody takes his own job"
assert "jobfail|own" in cmd(2, f"done {jid}"), "only the poster confirms"
assert "jobfail|notaken" in cmd(1, f"done {jid}"), "nothing to confirm before someone took it"
assert "job|take" in cmd(2, f"take {jid}")
assert jobs(1)[0].taken and jobs(1)[0].taker_name == "Yura" and jobs(2)[0].by_me
lua.execute('players[3] = {char = "c_1", name = "Docent", money = 0}')
assert "jobfail|taken" in cmd(3, f"take {jid}"), "one taker"
assert "job|done" in cmd(1, f"done {jid}")
pay = g.netcoop_transit.deserialize(g.store.pda_pay.b_1)
assert pay.sum == 3000 and money(2) == 100, "the taker is paid through pda_pay, not twice in place"
assert "jobfail|gone" in cmd(1, f"done {jid}") and g.netcoop_transit.deserialize(g.store.pda_pay.b_1).sum == 3000, "never paid twice"
assert len(jobs(1)) == 0

# Cancel returns the reward; a taker may drop.
cmd(1, "post 500|Bring vodka|")
jid = jobs(2)[0].id
assert "job|take" in cmd(2, f"take {jid}") and "job|drop" in cmd(2, f"drop {jid}") and not jobs(1)[0].taken
assert money(1) == 1500 and "job|cancel" in cmd(1, f"cancel {jid}") and money(1) == 2000, "cancel refunds"

# Per-player limit; expiry after 7 days refunds through pda_pay.
for n in range(5):
    assert "job|posted" in cmd(1, f"post 10|Job {n}|")
assert "jobfail|limit" in cmd(1, "post 10|Job 6|")
lua.execute("clock = clock + 8 * 86400")
assert len(jobs(2)) == 0
assert g.netcoop_transit.deserialize(g.store.pda_pay.a_1).sum == 50, "expired jobs refund the poster"

# The client's board decodes the server's offers (pdanet decoder).
client = lua.table()
lua.execute("""local env = ...
env.game = {translate_string = function(s) return s end}
env.class = function(name) return function() env[name] = {} end end
env.netcoop_pdanet_client = {decode = function(t) return netcoop_transit.deserialize(t) end}
setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()""",
            client, (root / "client/netcoop_taskboard_client.script").read_text(encoding="utf-8"))
offers = lua.eval('{{c="fetch", n=7, t="esc_task_1", d="Bring 3 meat", tt="Meat", td="for Wolf", ti="", b=false}}')
client.receive("1/1|" + g.netcoop_transit.serialize(offers))
cmd(2, "post 0|x|y")  # a job for the client list
client.receive("jobs|" + g.netcoop_transit.serialize(g.netcoop_transit.deserialize(
    [m for m in cmd(2, "list") if m.startswith("jobs|")][-1][5:])))
rows = client.get_rows()
assert rows.fetch[1].task_id == "esc_task_1" and rows.fetch[1].details.task_title == "Meat" and rows.fetch[1].npc_id == 7
assert client.get_jobs()[1].title == "x"
print("PASS task board: players' jobs escrow, one taker, poster confirms, pda_pay reward once, cancel/drop/limit/expiry; client decodes offers")
