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
class xrClientData;
class xrServer;

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
void server_on_client_disconnect(xrClientData* CL);
void server_update(xrServer* server); // periodic money persistence
bool server_account_money(LPCSTR login, u32& money);
bool server_set_role(LPCSTR login, u8 role, xr_string& message);
void server_list_accounts(xr_string& out);
} // namespace netcoop
