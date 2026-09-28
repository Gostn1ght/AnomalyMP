#pragma once

// NetAnomaly co-op: accounts, roles, server-owned money and trade.
//
// Passwords never leave the client. The client derives a per-server key with
// PBKDF2-SHA256(password, login) and sends that key once per connection. The
// server stores only PBKDF2-SHA256(key, random salt). The game transport is
// not encrypted, so the key is a password equivalent for this server only;
// a network observer on the path could replay it, but cannot recover the
// password for reuse on other services.

class NET_Packet;
class CObject;
class xrClientData;
class xrServer;
struct GAME_NEWS_DATA;
class CWeapon;

// Console: netcoop_smooth (0 = old network presentation, 1 = doc 38 stage 1),
// netcoop_interp_ms (interpolation delay for remote objects on a client),
// netcoop_metrics (10 s network summary in the log).
extern int g_netcoop_smooth;
extern int g_netcoop_interp_ms;
extern int g_netcoop_metrics;

namespace netcoop
{
enum ERole : u8
{
	role_none = 0,
	role_player = 1,
	role_admin = 2,
};

enum EAuthMode : u8
{
	auth_login = 0,
	auth_register = 1,
};

enum ETradeDirection : u8
{
	trade_actor_buys = 0,
	trade_actor_sells = 1,
};

bool enabled(); // -netcoop on the command line
bool pure_client(); // netcoop process without a local server
LPCSTR role_name(u8 role);

// Reads a zero-terminated string without asserting on malformed packets.
bool read_string(NET_Packet& P, LPSTR dest, u32 dest_size);

// ---- client ------------------------------------------------------------
// Derives the connection key and remembers it for the next connection.
bool client_set_credentials(LPCSTR login, LPCSTR password, bool register_account);
bool client_has_credentials();
LPCSTR client_login();
u8 client_role();
void client_write_auth(NET_Packet& P);
void client_on_auth_result(NET_Packet& P);
void client_on_trade_result(NET_Packet& P);
bool client_take_trade_refresh(); // true once after a server trade result
void client_on_server_text(LPCSTR text);
void client_send_command(LPCSTR text);

// Server-driven dialogue: the client talk window only shows what the server's
// dialogue run produced and sends the chosen phrase back.
struct TalkLine
{
	bool npc;
	shared_str text;
};

struct TalkChoice
{
	shared_str id;
	shared_str text;
	bool finalizer;
};

struct TalkState
{
	u16 npc;
	bool open;
	bool trade;
	xr_vector<TalkLine> lines;
	xr_vector<TalkChoice> choices;
};

void client_talk_start(u16 npc_id);
void client_talk_choose(LPCSTR id);
void client_talk_stop();
void client_on_talk_state(NET_Packet& P);
bool client_take_talk_state(TalkState& out); // oldest unapplied state

// HUD items (weapons, PDA, food, devices) held by the locally controlled Actor
// switch state on the owning client; the server does not drive their animations.
bool client_owns_hud_item(const CObject* item);

// Lua: netcoop_login(login, password, register), netcoop_role(),
// netcoop_account(), netcoop_command(text), netcoop_pure_client()
bool script_login(LPCSTR login, LPCSTR password, bool register_account);
int script_role();
LPCSTR script_account();
void script_command(LPCSTR text);
bool script_pure_client();

// ---- server ------------------------------------------------------------
void server_on_auth(xrServer* server, xrClientData* CL, NET_Packet& P);
bool server_requires_login(xrServer* server, xrClientData* CL);
void server_on_trade(xrServer* server, xrClientData* CL, NET_Packet& P);
// Remote clients may not change money, other players' inventories or living
// NPC inventories through raw events. P is left at its read position.
bool server_remote_event_allowed(xrServer* server, xrClientData* CL, NET_Packet& P, u16 type, u16 destination);
void server_on_talk(xrServer* server, xrClientData* CL, NET_Packet& P);
// An NPC answer produced during a server dialogue run; false outside a run.
bool talk_capture_answer(LPCSTR text);
// NPC/monster logic on the server refers to db.actor. For one binder update,
// bind it to the nearest player; false when no player is connected.
// Nested binds keep the outermost player until the outermost unbind.
bool server_bind_nearest_actor(CObject* npc);
void server_unbind_actor();

// For the whole update or event of a server NPC or monster: its AI planner,
// evaluators and callbacks run GAMMA scripts that use db.actor too.
struct ServerActorScope
{
	bool bound;
	explicit ServerActorScope(CObject* object);
	~ServerActorScope();
};
void server_on_client_disconnect(xrClientData* CL);
void server_update(xrServer* server); // periodic money persistence
bool server_account_money(LPCSTR login, u32& money);
// Per-player tasks: updates each player's tasks and sends changed lists.
void server_tasks_update(xrServer* server);
bool server_task_taken_by_other(u16 actor_id, LPCSTR task_id);
void client_on_tasks(NET_Packet& P);
// PDA news the server scripts give a player's Actor, shown on that player's client.
void server_forward_news(u16 actor_id, const GAME_NEWS_DATA& news);
void client_on_news(NET_Packet& P);

// Server Lua -> client Lua: netcoop_broadcast(channel, data) on the server
// calls netcoop_client_compat.on_script_message(channel, data) on every
// logged-in client.
void script_broadcast(LPCSTR channel, LPCSTR data);
// Same message to the client that owns one player Actor; false when the
// Actor is not a remote player's.
bool script_send_to_actor(u16 actor_id, LPCSTR channel, LPCSTR data);
// Server scripts open NPC trade/upgrade windows for a player: the player's
// client opens them (on_script_message "open_ui"). True when sent.
bool server_open_ui(u16 actor_id, LPCSTR kind, u16 partner_id);
// Lua: request a server-executed trade (see netcoop.cpp).
bool script_trade(u16 partner_id, bool actor_sells, LPCSTR ids);
// Starts the thread that reports and aborts a script call hanging a frame.
void script_watchdog_start();
void client_on_script(NET_Packet& P);
bool server_set_role(LPCSTR login, u8 role, xr_string& message);
void server_list_accounts(xr_string& out);

// Network smoothness (doc 38, stages 0 and 1).
bool smooth();
// How far behind the estimated server time a client shows remote objects.
u32 remote_interp_delay();
// Metrics, summarised in the log every 10 s.
void metric_snapshot(u32 interval_ms);
void metric_snapshot_duplicate();
void metric_puppet_frame(u16 id, const Fvector& pos, bool extrapolating);
void metric_actor_error(float error, bool applied);
void metric_owner_step_rejected(float step);
void metric_weapon_fire(CWeapon* weapon);
void metrics_update();
} // namespace netcoop
