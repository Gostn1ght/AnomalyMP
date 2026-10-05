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
class CActor;
class CSE_Abstract;

// Console: netcoop_smooth (0 = old network presentation, 1 = doc 38 stage 1),
// netcoop_interp_ms (interpolation delay for remote objects on a client),
// netcoop_metrics (10 s network summary in the log).
extern int g_netcoop_smooth;
extern int g_netcoop_interp_ms;
extern int g_netcoop_metrics;
// Other players shown at the present moment (prediction from the newest
// snapshot and the owner's velocity) instead of ~0.1 s in the past.
extern int g_netcoop_player_predict;

namespace netcoop
{
bool server_inventory_can_take(xrServer* server,u16 owner_id,u16 item_id);
bool server_reset_device(LPCSTR login);
void client_capture_pda();
void server_on_pda_screen(xrServer* server, xrClientData* client, NET_Packet& packet);
void client_on_pda_screen(NET_Packet& packet);
void pda_forget(u16 id);
void replicate_mark(CObject* object, u32 element, const Fvector& position, const Fvector& direction, float size, LPCSTR textures);
void client_on_mark(NET_Packet& packet);
void client_marks_update();
void client_marks_reset();
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
	auth_auto = 2, // log in, or register when the account does not exist (load-test bots)
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
// The per-server key sent at login: hex PBKDF2-SHA256(password, "NetAnomaly/" + lower(login)).
bool derive_client_key(LPCSTR login, LPCSTR password, xr_string& key_hex);
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
bool client_admin_authorized();
int script_role();
LPCSTR script_account();
int script_account_state();
bool script_registration_decide(LPCSTR login, bool accept);
void script_preview_clear();
bool script_preview_model(LPCSTR model, int pose);
void script_preview_draw();
void script_command(LPCSTR text);
bool script_pure_client();

// ---- server ------------------------------------------------------------
void server_on_auth(xrServer* server, xrClientData* CL, NET_Packet& P);
// Every frame: applies logins whose password hash finished on a worker.
void server_auth_update(xrServer* server);
// True (and the packet kept) while the client's login is being checked.
bool server_defer_player_state(xrClientData* CL, NET_Packet& P);
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

// While a player's Actor on the server is hit: db.actor is that player, so
// GAMMA's hit scripts (armour, body parts, damage) hurt the right Actor.
// They zeroed the hit and took health from whatever db.actor was bound
// (the NPC's nearest player or the host Actor), s98.
struct ServerVictimScope
{
	bool active;
	CActor* previous;
	explicit ServerVictimScope(CActor* victim);
	~ServerVictimScope();
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
bool script_character(int slot, LPCSTR name, LPCSTR faction, int economy, LPCSTR loadout);
bool server_character_load_actor(xrClientData* CL, CSE_Abstract* actor);
void server_character_spawn_items(xrClientData* CL);
void server_character_save_actor(u16 actor_id);
void server_physics_update(xrServer* server);
// Every server frame: physics poses, PDA screens, bullet marks (own rates).
void server_frame_update(xrServer* server);
// Item instance state (netcoop_items.inc, gameplay plan stage 1): the server
// versions each item's condition/charge, portions, magazine, addons and box
// count and sends changed fields; carriers report their own wear and drain.
void server_items_update(xrServer* server);
void server_on_item_report(xrServer* server, xrClientData* CL, NET_Packet& P);
// A server-authored change of a carried item (trade, repair): its owner gets
// the predicted fields too.
void server_item_touch(u16 id);
void item_destroyed(u16 id); // both sides, from CInventoryItem::net_Destroy
void client_on_item_state(NET_Packet& P);
// Every frame (rate-limited); flush = report own item changes now, before an
// event that moves an item to someone else.
void client_items_update(bool flush = false);
void client_item_forget(u16 id);
LPCSTR script_item_info(u16 id);
// Atomic transfer of one item between the player and a corpse or a box
// (netcoop_transfer.inc, stage 2). Client: false outside a pure client.
bool client_transfer(u16 from, u16 to, u16 item);
// TransactionID for trade and transfer requests of this client.
u32 client_next_txid();
void client_on_transfer_result(NET_Packet& P);
void server_on_transfer(xrServer* server, xrClientData* CL, NET_Packet& P);
// Lua (client): netcoop_item_action(kind, item, target, action) - the server
// runs an item action (stage 3): kind 0 = menu functor "module.function",
// kind 1 = item dropped on item ("battery_swap"). Target 65535 = none.
bool script_item_action(int kind, u16 item, u16 target, LPCSTR action);
void server_on_item_action(xrServer* server, xrClientData* CL, NET_Packet& P);
void client_on_physics(NET_Packet& P);
// Server: the object is the Actor of a remote player. Local() is not used
// for this: on the dedicated server it did not tell these copies apart
// (s96: players' shots never reached FireStart).
bool server_player_copy(const CObject* object);
// A real-time millisecond clock of this process: never paused or scaled
// (the engine's global timer stops in menus and follows time_factor).
u32 real_time_ms();
// Interpolation clock of a pure client. Server time is not estimated from
// pings (that estimate moved by hundreds of ms and the engine timer drifted
// ~2 % against the server): it follows the newest server snapshots, the upper
// envelope of (snapshot time - real time), decaying 5 % so that a slower
// server clock is followed too. Falls back to Level().timeServer().
void snapshot_sample(u32 server_stamp);
u32 snapshot_now();
// How far behind the estimated server time a client shows remote objects.
u32 remote_interp_delay();
// Same, but at least 1.5 times the object's own last snapshot interval
// (area of interest sends far objects less often).
u32 remote_interp_delay(u32 last_interval);
// Metrics, summarised in the log every 10 s.
void metric_snapshot(u32 interval_ms);
void metric_snapshot_duplicate();
// lead_ms: estimated server time minus the newest snapshot's time; above the
// interpolation delay the object is extrapolated.
void metric_puppet_frame(u16 id, const Fvector& pos, bool extrapolating, s32 lead_ms);
// The same for other players only (logged separately on the [clock] line).
void metric_player_frame(bool extrapolating, s32 lead_ms, float step);
// Client: another player's Actor this frame (why it is or is not shown).
void metric_remote_actor(u16 id, bool remote, bool alive, u32 net_size, s32 age_ms);
void metric_actor_error(float error, bool applied);
void metric_owner_step_rejected(float step);
void metric_weapon_fire(CWeapon* weapon);
// Server: bytes of object updates sent this tick and objects serialised.
void metric_server_sent(u32 bytes, u32 objects);
// Server: a client's snapshot skipped because its send queue was late.
void metric_snapshot_blocked();
void metrics_update();

// Death and respawn of this client's player: after death the camera stays at
// the body with a blinking countdown (10 s), then SPACE asks the server for
// a new Actor ("respawn" command). The body stays in the world as a corpse.
void client_on_own_death();
void client_death_frame();
bool client_death_key(int key); // true when the key was used
// Lua (server): netcoop_respawn(actor_id) - a new Actor for a dead player.
bool script_respawn(u16 actor_id);

// Load test: bots connect to a server as players and walk (netcoop_bots.cpp).
// Console: netcoop_bots <count> [address]; command line -netcoop_bots <count>
// [-netcoop_bots_addr <address>]. Pumped every frame by the game.
void bots_set(u32 count, LPCSTR address);
void bots_frame();

// RP animations (player emotes) from configs/netcoop/rp_anims.ltx (stock
// stalker motions).
struct RpAnim
{
	shared_str name;
	shared_str title;
	xr_vector<shared_str> in, mid, out;
	bool loop = true;
};
const xr_vector<RpAnim>& rp_anims();
// Lua: netcoop_rp_list() -> "name=title;...", netcoop_rp_play(name),
// netcoop_rp_stop(), netcoop_rp_active() -> name or "".
LPCSTR script_rp_list();
bool script_rp_play(LPCSTR name);
void script_rp_stop();
LPCSTR script_rp_active();
} // namespace netcoop
