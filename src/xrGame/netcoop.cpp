#include "pch_script.h"
#include "netcoop.h"

#include <bcrypt.h>
#pragma comment(lib, "bcrypt.lib")

#include "xrServer.h"
#include "game_sv_base.h"
#include "inventory_space.h"
#include "xrMessages.h"
#include "Level.h"
#include "Actor.h"
#include "InventoryOwner.h"
#include "inventory_item.h"
#include "entity_alive.h"
#include "trade.h"
#include "ai_space.h"
#include "script_engine.h"
#include "xrServer_Objects_ALife_Monsters.h"
#include "game_base_space.h"
#include "PhraseDialog.h"
#include "PhraseDialogManager.h"
#include "game_sv_single.h"
#include "GameTaskManager.h"
#include "GameTask.h"
#include "UIGameCustom.h"
#include "game_news.h"
#include <dbghelp.h>
#pragma comment(lib, "dbghelp.lib")

namespace netcoop
{
// ---------------------------------------------------------------------------
// common helpers
// ---------------------------------------------------------------------------
static const u32 client_key_iterations = 20000;
static const u32 server_hash_iterations = 60000;
static const u32 key_bytes = 32;
static const u32 salt_bytes = 16;
static const float trade_max_distance = 6.f;

bool enabled()
{
	static int state = -1;
	if (state < 0)
		state = strstr(Core.Params, "-netcoop") ? 1 : 0;
	return state == 1;
}

bool pure_client()
{
	return enabled() && g_pGameLevel && !Level().Server;
}

LPCSTR role_name(u8 role)
{
	switch (role)
	{
	case role_admin: return "admin";
	case role_player: return "player";
	default: return "none";
	}
}

bool read_string(NET_Packet& P, LPSTR dest, u32 dest_size)
{
	dest[0] = 0;
	if (P.r_pos >= P.B.count)
		return false;
	const u8* start = P.B.data + P.r_pos;
	const u32 available = P.B.count - P.r_pos;
	const void* end = memchr(start, 0, available);
	if (!end)
		return false;
	const u32 length = u32((const u8*)end - start);
	if (length + 1 > dest_size)
		return false;
	CopyMemory(dest, start, length + 1);
	P.r_pos += length + 1;
	return true;
}

static void to_lower(xr_string& s)
{
	for (u32 i = 0; i < s.size(); ++i)
		s[i] = (char)tolower((unsigned char)s[i]);
}

static bool login_valid(LPCSTR login)
{
	const u32 n = xr_strlen(login);
	if (n < 3 || n > 20)
		return false;
	for (u32 i = 0; i < n; ++i)
	{
		const char c = login[i];
		if (!isalnum((unsigned char)c) && c != '_' && c != '-' && c != '.')
			return false;
	}
	return true;
}

static bool key_valid(LPCSTR key)
{
	if (xr_strlen(key) != key_bytes * 2)
		return false;
	for (LPCSTR c = key; *c; ++c)
	{
		if (!((*c >= '0' && *c <= '9') || (*c >= 'a' && *c <= 'f')))
			return false;
	}
	return true;
}

static xr_string to_hex(const u8* data, u32 size)
{
	static const char digits[] = "0123456789abcdef";
	xr_string out;
	out.resize(size * 2);
	for (u32 i = 0; i < size; ++i)
	{
		out[i * 2] = digits[data[i] >> 4];
		out[i * 2 + 1] = digits[data[i] & 15];
	}
	return out;
}

static bool pbkdf2(const void* secret, u32 secret_size, const void* salt, u32 salt_size, u32 iterations, u8* out,
                   u32 out_size)
{
	BCRYPT_ALG_HANDLE alg = NULL;
	if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, BCRYPT_ALG_HANDLE_HMAC_FLAG)))
		return false;
	const NTSTATUS status = BCryptDeriveKeyPBKDF2(alg, (PUCHAR)secret, secret_size, (PUCHAR)salt, salt_size,
	                                              iterations, out, out_size, 0);
	BCryptCloseAlgorithmProvider(alg, 0);
	return BCRYPT_SUCCESS(status);
}

static bool random_bytes(u8* out, u32 size)
{
	return BCRYPT_SUCCESS(BCryptGenRandom(NULL, out, size, BCRYPT_USE_SYSTEM_PREFERRED_RNG));
}

static bool constant_time_equal(const xr_string& a, const xr_string& b)
{
	if (a.size() != b.size())
		return false;
	u8 diff = 0;
	for (u32 i = 0; i < a.size(); ++i)
		diff |= u8(a[i] ^ b[i]);
	return diff == 0;
}

static void call_lua(LPCSTR function, bool ok, u8 role, LPCSTR message)
{
	::luabind::functor<void> f;
	if (ai().script_engine().functor(function, f))
	{
		try
		{
			f(ok, int(role), message);
		}
		catch (...)
		{
			Msg("! [NetAnomaly] %s failed", function);
		}
	}
}

// ---------------------------------------------------------------------------
// client
// ---------------------------------------------------------------------------
static xr_string s_client_login;
static xr_string s_client_key;
static bool s_client_register = false;
static bool s_client_loaded = false;
static u8 s_client_role = role_none;

static void client_credentials_path(string_path& path)
{
	FS.update_path(path, "$app_data_root$", "netcoop_login.txt");
}

static void client_load_credentials()
{
	if (s_client_loaded)
		return;
	s_client_loaded = true;

	string_path path;
	client_credentials_path(path);
	FILE* f = fopen(path, "rb");
	if (!f)
		return;
	char line[256] = {};
	if (fgets(line, sizeof(line) - 1, f))
	{
		char* sep = strchr(line, '|');
		if (sep)
		{
			*sep = 0;
			char* key = sep + 1;
			key[strcspn(key, "\r\n")] = 0;
			if (login_valid(line) && key_valid(key))
			{
				s_client_login = line;
				s_client_key = key;
			}
		}
	}
	fclose(f);
}

bool client_set_credentials(LPCSTR login, LPCSTR password, bool register_account)
{
	if (!login || !password || !login_valid(login))
	{
		Msg("! [NetAnomaly] login must be 3-20 characters: letters, digits, _ - .");
		return false;
	}
	const u32 password_length = xr_strlen(password);
	if (password_length < 4 || password_length > 64)
	{
		Msg("! [NetAnomaly] password must be 4-64 characters");
		return false;
	}

	xr_string lower = login;
	to_lower(lower);
	xr_string salt = "NetAnomaly/";
	salt += lower;

	u8 key[key_bytes];
	if (!pbkdf2(password, password_length, salt.c_str(), (u32)salt.size(), client_key_iterations, key, key_bytes))
	{
		Msg("! [NetAnomaly] cannot derive the account key");
		return false;
	}

	s_client_loaded = true;
	s_client_login = login;
	s_client_key = to_hex(key, key_bytes);
	s_client_register = register_account;
	SecureZeroMemory(key, sizeof(key));

	// Remember the derived key, not the password, for the next connection.
	string_path path;
	client_credentials_path(path);
	FILE* f = fopen(path, "wb");
	if (f)
	{
		fprintf(f, "%s|%s\n", s_client_login.c_str(), s_client_key.c_str());
		fclose(f);
	}
	return true;
}

bool client_has_credentials()
{
	client_load_credentials();
	return !s_client_login.empty() && !s_client_key.empty();
}

LPCSTR client_login()
{
	client_load_credentials();
	return s_client_login.c_str();
}

u8 client_role()
{
	return s_client_role;
}

void client_write_auth(NET_Packet& P)
{
	client_load_credentials();
	P.w_u8(s_client_register ? auth_register : auth_login);
	P.w_stringZ(s_client_login.c_str());
	P.w_stringZ(s_client_key.c_str());
	s_client_register = false;
	s_client_role = role_none;
}

void client_on_auth_result(NET_Packet& P)
{
	const u8 ok = P.r_u8();
	const u8 role = P.r_u8();
	string512 message;
	if (!read_string(P, message, sizeof(message)))
		xr_strcpy(message, "");

	s_client_role = ok ? role : u8(role_none);
	Msg("%s [NetAnomaly] %s", ok ? "*" : "!", message);
	call_lua("netcoop_client_compat.on_auth_result", !!ok, s_client_role, message);
}

static bool s_trade_refresh = false;

void client_on_trade_result(NET_Packet& P)
{
	const u8 ok = P.r_u8();
	string512 message;
	if (!read_string(P, message, sizeof(message)))
		xr_strcpy(message, "");
	Msg("%s [NetAnomaly] trade: %s", ok ? "*" : "!", message);
	s_trade_refresh = true;
	call_lua("netcoop_client_compat.on_trade_result", !!ok, s_client_role, message);
}

bool client_take_trade_refresh()
{
	const bool refresh = s_trade_refresh;
	s_trade_refresh = false;
	return refresh;
}

void client_on_server_text(LPCSTR text)
{
	::luabind::functor<void> f;
	if (ai().script_engine().functor("netcoop_client_compat.on_server_text", f))
	{
		try
		{
			f(text);
		}
		catch (...)
		{
		}
	}
}

void client_send_command(LPCSTR text)
{
	if (!text || !xr_strlen(text) || xr_strlen(text) > 4000 || !g_pGameLevel)
		return;
	NET_Packet P;
	P.w_begin(M_NETANOMALY_CMD);
	P.w_stringZ(text);
	Level().Send(P, net_flags(TRUE, TRUE));
}

// Lua entry points.
bool script_login(LPCSTR login, LPCSTR password, bool register_account)
{
	return client_set_credentials(login, password, register_account);
}

int script_role() { return client_role(); }
LPCSTR script_account() { return client_login(); }
void script_command(LPCSTR text) { client_send_command(text); }
bool script_pure_client() { return pure_client(); }

// ---------------------------------------------------------------------------
// server: account storage
// ---------------------------------------------------------------------------
struct Account
{
	xr_string login; // as registered
	u8 role;
	xr_string salt;
	xr_string hash;
	bool has_money;
	u32 money;
	u32 failures;
	u32 locked_until;
};

typedef xr_map<xr_string, Account> Accounts;
static Accounts s_accounts;
static bool s_accounts_loaded = false;
static bool s_accounts_dirty = false;

static void accounts_path(string_path& path)
{
	FS.update_path(path, "$app_data_root$", "netcoop_accounts.txt");
}

static void accounts_load()
{
	if (s_accounts_loaded)
		return;
	s_accounts_loaded = true;

	string_path path;
	accounts_path(path);
	FILE* f = fopen(path, "rb");
	if (!f)
		return;

	char line[512];
	while (fgets(line, sizeof(line), f))
	{
		line[strcspn(line, "\r\n")] = 0;
		if (!line[0] || line[0] == '#')
			continue;

		// login|role|salt|hash|money
		char* fields[5] = {};
		u32 count = 0;
		char* cursor = line;
		while (count < 5)
		{
			fields[count++] = cursor;
			char* sep = strchr(cursor, '|');
			if (!sep)
				break;
			*sep = 0;
			cursor = sep + 1;
		}
		if (count < 4 || !login_valid(fields[0]))
			continue;

		Account a;
		a.login = fields[0];
		a.role = !xr_strcmp(fields[1], "admin") ? u8(role_admin) : u8(role_player);
		a.salt = fields[2];
		a.hash = fields[3];
		a.has_money = count >= 5 && fields[4][0] && fields[4][0] != '-';
		a.money = a.has_money ? (u32)strtoul(fields[4], NULL, 10) : 0;
		a.failures = 0;
		a.locked_until = 0;

		xr_string key = a.login;
		to_lower(key);
		s_accounts[key] = a;
	}
	fclose(f);
	Msg("[NetAnomaly] loaded %u account(s) from %s", (u32)s_accounts.size(), path);
}

static void accounts_save()
{
	if (!s_accounts_dirty)
		return;

	string_path path, temp;
	accounts_path(path);
	xr_sprintf(temp, "%s.tmp", path);
	FILE* f = fopen(temp, "wb");
	if (!f)
	{
		Msg("! [NetAnomaly] cannot write %s", temp);
		return;
	}
	fprintf(f, "# NetAnomaly accounts: login|role|salt|pbkdf2-sha256|money\n");
	for (Accounts::const_iterator it = s_accounts.begin(); it != s_accounts.end(); ++it)
	{
		const Account& a = it->second;
		if (a.has_money)
			fprintf(f, "%s|%s|%s|%s|%u\n", a.login.c_str(), role_name(a.role), a.salt.c_str(), a.hash.c_str(), a.money);
		else
			fprintf(f, "%s|%s|%s|%s|-\n", a.login.c_str(), role_name(a.role), a.salt.c_str(), a.hash.c_str());
	}
	fclose(f);
	if (!MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
	{
		Msg("! [NetAnomaly] cannot replace %s", path);
		return;
	}
	s_accounts_dirty = false;
}

static Account* account_find(LPCSTR login)
{
	accounts_load();
	xr_string key = login;
	to_lower(key);
	Accounts::iterator it = s_accounts.find(key);
	return it == s_accounts.end() ? NULL : &it->second;
}

static bool server_hash(LPCSTR client_key, const xr_string& salt_hex, xr_string& out)
{
	u8 hash[key_bytes];
	if (!pbkdf2(client_key, xr_strlen(client_key), salt_hex.c_str(), (u32)salt_hex.size(), server_hash_iterations,
	            hash, key_bytes))
		return false;
	out = to_hex(hash, key_bytes);
	return true;
}

bool server_account_money(LPCSTR login, u32& money)
{
	Account* a = login && login[0] ? account_find(login) : NULL;
	if (!a || !a->has_money)
		return false;
	money = a->money;
	return true;
}

bool server_set_role(LPCSTR login, u8 role, xr_string& message)
{
	Account* a = login ? account_find(login) : NULL;
	if (!a)
	{
		message = "account not found";
		return false;
	}
	a->role = role;
	s_accounts_dirty = true;
	accounts_save();
	message = a->login;
	message += " is now ";
	message += role_name(role);
	return true;
}

void server_list_accounts(xr_string& out)
{
	accounts_load();
	string256 line;
	xr_sprintf(line, "%u account(s):", (u32)s_accounts.size());
	out = line;
	for (Accounts::const_iterator it = s_accounts.begin(); it != s_accounts.end(); ++it)
	{
		const Account& a = it->second;
		if (a.has_money)
			xr_sprintf(line, "\n  %-20s %-7s %u RU", a.login.c_str(), role_name(a.role), a.money);
		else
			xr_sprintf(line, "\n  %-20s %-7s -", a.login.c_str(), role_name(a.role));
		out += line;
	}
}

// ---------------------------------------------------------------------------
// server: authentication
// ---------------------------------------------------------------------------
struct LoginInUse
{
	xr_string login;
	xrClientData* self;
	bool operator()(IClient* client) const
	{
		xrClientData* other = static_cast<xrClientData*>(client);
		if (other == self || !other->netcoop_login.size())
			return false;
		xr_string name = other->netcoop_login.c_str();
		to_lower(name);
		return name == login;
	}
};

static void send_auth_result(xrServer* server, xrClientData* CL, bool ok, u8 role, LPCSTR message)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_AUTH_RESULT);
	P.w_u8(ok ? 1 : 0);
	P.w_u8(role);
	P.w_stringZ(message);
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
}

static void reject(xrServer* server, xrClientData* CL, LPCSTR message)
{
	Msg("! [NetAnomaly] login rejected for 0x%08x: %s", CL->ID.value(), message);
	send_auth_result(server, CL, false, role_none, message);
	string512 reason;
	xr_sprintf(reason, "@%s", message);
	server->DisconnectClient(CL, reason);
}

void server_on_auth(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || CL->flags.bLocal || CL == server->GetServerClient())
		return;
	if (CL->netcoop_role != role_none)
		return; // already authenticated on this connection

	if (P.r_elapsed() < 1)
	{
		reject(server, CL, "Malformed login request");
		return;
	}
	const u8 mode = P.r_u8();
	char login[64];
	char key[96];
	if (!read_string(P, login, sizeof(login)) || !read_string(P, key, sizeof(key)) || !login_valid(login) ||
		!key_valid(key))
	{
		reject(server, CL, "Invalid login or password");
		return;
	}

	LoginInUse in_use;
	in_use.login = login;
	to_lower(in_use.login);
	in_use.self = CL;
	if (server->FindClient(in_use))
	{
		reject(server, CL, "This account is already online");
		return;
	}

	Account* a = account_find(login);
	if (mode == auth_register)
	{
		if (a)
		{
			reject(server, CL, "Account already exists, use Login");
			return;
		}
		Account created;
		created.login = login;
		created.role = role_player; // only the server console grants admin
		u8 salt[salt_bytes];
		if (!random_bytes(salt, salt_bytes))
		{
			reject(server, CL, "Server error: no random source");
			return;
		}
		created.salt = to_hex(salt, salt_bytes);
		if (!server_hash(key, created.salt, created.hash))
		{
			reject(server, CL, "Server error: cannot hash password");
			return;
		}
		created.has_money = false;
		created.money = 0;
		created.failures = 0;
		created.locked_until = 0;
		s_accounts[in_use.login] = created;
		s_accounts_dirty = true;
		accounts_save();
		a = &s_accounts[in_use.login];
		Msg("[NetAnomaly] account '%s' registered", login);
	}
	else
	{
		if (!a)
		{
			reject(server, CL, "Unknown account, use Register");
			return;
		}
		const u32 now = GetTickCount();
		if (a->locked_until && now < a->locked_until)
		{
			reject(server, CL, "Too many failed logins, try again in a minute");
			return;
		}
		xr_string hash;
		if (!server_hash(key, a->salt, hash) || !constant_time_equal(hash, a->hash))
		{
			if (++a->failures >= 5)
			{
				a->failures = 0;
				a->locked_until = now + 60000;
			}
			reject(server, CL, "Wrong password");
			return;
		}
		a->failures = 0;
		a->locked_until = 0;
	}

	CL->netcoop_login = a->login.c_str();
	CL->netcoop_role = a->role;
	CL->name = a->login.c_str();

	string256 message;
	xr_sprintf(message, "Logged in as %s (%s)", a->login.c_str(), role_name(a->role));
	Msg("[NetAnomaly] client 0x%08x %s", CL->ID.value(), message);
	send_auth_result(server, CL, true, a->role, message);
}

bool server_requires_login(xrServer* server, xrClientData* CL)
{
	return enabled() && CL && !CL->flags.bLocal && CL != server->GetServerClient() && CL->netcoop_role == role_none;
}

static xrCriticalSection s_pending_lock;
static xr_vector<u16> s_pending_actor_destroy;
static void server_release_task_manager(u16 actor_id);

static void store_money(xrClientData* CL)
{
	if (!CL || !CL->netcoop_login.size() || !CL->owner)
		return;
	CSE_ALifeTraderAbstract* trader = smart_cast<CSE_ALifeTraderAbstract*>(CL->owner);
	if (!trader)
		return;
	Account* a = account_find(CL->netcoop_login.c_str());
	if (!a)
		return;
	if (!a->has_money || a->money != trader->m_dwMoney)
	{
		a->has_money = true;
		a->money = trader->m_dwMoney;
		s_accounts_dirty = true;
	}
}

void server_on_client_disconnect(xrClientData* CL)
{
	if (!enabled() || !CL)
		return;
	store_money(CL);
	accounts_save();

	// Remove the player's Actor instead of migrating it to the server, so a
	// reconnect does not leave an abandoned body in the world. This runs on
	// the transport thread; the game object is destroyed from server_update.
	if (!CL->flags.bLocal && CL->owner && smart_cast<CSE_ALifeCreatureActor*>(CL->owner))
	{
		s_pending_lock.Enter();
		s_pending_actor_destroy.push_back(CL->owner->ID);
		s_pending_lock.Leave();
	}
}

// The disconnected client no longer exists, so the server takes over the
// Actor and everything it carries before destroying it.
static void give_to_server(xrServer* server, CSE_Abstract* entity, u32 depth)
{
	if (!entity || depth > 8)
		return;
	entity->owner = static_cast<xrClientData*>(server->GetServerClient());
	for (u32 i = 0; i < entity->children.size(); ++i)
		give_to_server(server, server->game->get_entity_from_eid(entity->children[i]), depth + 1);
}

static void destroy_pending_actors(xrServer* server)
{
	xr_vector<u16> ids;
	s_pending_lock.Enter();
	ids.swap(s_pending_actor_destroy);
	s_pending_lock.Leave();

	for (u32 i = 0; i < ids.size() && g_pGameLevel; ++i)
	{
		CGameObject* actor_object = smart_cast<CGameObject*>(Level().Objects.net_Find(ids[i]));
		if (actor_object && smart_cast<CActor*>(actor_object) && server->GetServerClient())
		{
			give_to_server(server, server->game->get_entity_from_eid(ids[i]), 0);
			Msg("[NetAnomaly] removing Actor %u of a disconnected player", ids[i]);
			// An NPC still talking to this Actor would keep a dangling partner.
			CActor* leaving = smart_cast<CActor*>(actor_object);
			if (leaving && leaving->IsTalking())
			{
				if (CInventoryOwner* partner = leaving->GetTalkPartner())
					partner->StopTalk();
				leaving->StopTalk();
			}
			server_release_task_manager(ids[i]);
			actor_object->DestroyObject();
		}
	}
}

struct StoreMoney
{
	void operator()(IClient* client) const { store_money(static_cast<xrClientData*>(client)); }
};

void server_talk_prune(xrServer* server);

void server_update(xrServer* server)
{
	if (!enabled())
		return;
	destroy_pending_actors(server);
	server_talk_prune(server);
	if (!s_accounts_loaded)
		return;
	StoreMoney store;
	server->ForEachClientDo(store);
	accounts_save();
}

// ---------------------------------------------------------------------------
// server: event validation
// ---------------------------------------------------------------------------
static bool living_npc(CSE_Abstract* entity)
{
	if (!entity || smart_cast<CSE_ALifeCreatureActor*>(entity))
		return false;
	CSE_ALifeCreatureAbstract* creature = smart_cast<CSE_ALifeCreatureAbstract*>(entity);
	return creature && creature->g_Alive();
}

bool server_remote_event_allowed(xrServer* server, xrClientData* CL, NET_Packet& P, u16 type, u16 destination)
{
	if (!enabled() || !CL || CL->flags.bLocal)
		return true;

	switch (type)
	{
	case GE_MONEY:
		return false; // money changes only on the server

	case GEG_PLAYER_ITEM_EAT:
	case GEG_PLAYER_ITEM2SLOT:
	case GEG_PLAYER_ITEM2BELT:
	case GEG_PLAYER_ITEM2RUCK:
	case GEG_PLAYER_ACTIVATEARTEFACT:
	case GEG_PLAYER_ACTIVATE_SLOT:
		{
			// Players use and arrange items only in their own inventory.
			CSE_Abstract* dest = server->game->get_entity_from_eid(destination);
			return dest && dest == CL->owner;
		}

	case GE_TRADE_BUY:
	case GE_TRADE_SELL:
	case GE_OWNERSHIP_TAKE:
	case GE_OWNERSHIP_REJECT:
		{
			CSE_Abstract* dest = server->game->get_entity_from_eid(destination);
			if (!dest)
				return true; // the normal handler reports it

			if (smart_cast<CSE_ALifeCreatureActor*>(dest) && dest != CL->owner)
				return false; // another player's inventory
			if (living_npc(dest))
				return false; // living NPC inventories change through server trade

			if (P.r_elapsed() >= sizeof(u16))
			{
				const u32 pos = P.r_pos;
				const u16 item_id = P.r_u16();
				P.r_pos = pos;
				CSE_Abstract* item = server->game->get_entity_from_eid(item_id);
				CSE_Abstract* holder = item && item->ID_Parent != 0xffff
					? server->game->get_entity_from_eid(item->ID_Parent)
					: NULL;
				if (holder && holder != dest)
				{
					if (smart_cast<CSE_ALifeCreatureActor*>(holder) && holder != CL->owner)
						return false;
					if (living_npc(holder))
						return false;
				}
			}
			return true;
		}
	default:
		return true;
	}
}

// ---------------------------------------------------------------------------
// server: trade
// ---------------------------------------------------------------------------
static void send_trade_result(xrServer* server, xrClientData* CL, bool ok, LPCSTR message)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_TRADE_RESULT);
	P.w_u8(ok ? 1 : 0);
	P.w_stringZ(message);
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
	if (!ok)
		Msg("! [NetAnomaly] trade rejected for '%s': %s", CL->netcoop_login.c_str(), message);
}

void server_on_trade(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || !CL->owner || !g_pGameLevel)
		return;
	if (P.r_elapsed() < 2 + 1 + 2)
		return;

	const u16 partner_id = P.r_u16();
	const u8 direction = P.r_u8();
	const u16 count = P.r_u16();
	if (count == 0 || count > 256 || P.r_elapsed() != u32(count) * sizeof(u16) || direction > trade_actor_sells)
	{
		send_trade_result(server, CL, false, "Malformed trade request");
		return;
	}

	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	CObject* partner_object = Level().Objects.net_Find(partner_id);
	CInventoryOwner* partner = smart_cast<CInventoryOwner*>(partner_object);
	CEntityAlive* partner_alive = smart_cast<CEntityAlive*>(partner_object);
	if (!actor || !actor->g_Alive() || !partner || !partner_alive || !partner_alive->g_Alive() ||
		smart_cast<CActor*>(partner_object))
	{
		send_trade_result(server, CL, false, "Trader is not available");
		return;
	}
	if (!partner->IsTradeEnabled())
	{
		send_trade_result(server, CL, false, "This character does not trade");
		return;
	}
	if (actor->Position().distance_to(partner_object->Position()) > trade_max_distance)
	{
		send_trade_result(server, CL, false, "Trader is too far away");
		return;
	}

	// The partner's CTrade: bBuying == true means the partner buys (actor sells).
	const bool partner_buys = direction == trade_actor_sells;
	CObject* seller = partner_buys ? static_cast<CObject*>(actor) : partner_object;

	xr_vector<PIItem> items;
	items.reserve(count);
	for (u16 i = 0; i < count; ++i)
	{
		const u16 id = P.r_u16();
		PIItem item = smart_cast<PIItem>(Level().Objects.net_Find(id));
		if (!item || item->object().H_Parent() != seller || item->object().getDestroy())
		{
			send_trade_result(server, CL, false, "Item is no longer available");
			return;
		}
		if (std::find(items.begin(), items.end(), item) != items.end())
			continue;
		items.push_back(item);
	}

	CTrade* trade = partner->GetTrade();
	if (!trade)
	{
		send_trade_result(server, CL, false, "Trader is not available");
		return;
	}
	trade->StartTradeEx(actor);

	u32 total = 0;
	for (u32 i = 0; i < items.size(); ++i)
	{
		const u32 price = trade->GetItemPrice(items[i], partner_buys);
		if (price == 0)
		{
			trade->StopTrade();
			send_trade_result(server, CL, false, partner_buys ? "Trader does not buy this item"
			                                                  : "Trader does not sell this item");
			return;
		}
		total += price;
	}

	if (partner_buys)
	{
		if (!partner->InfinitiveMoney() && partner->get_money() < total)
		{
			trade->StopTrade();
			send_trade_result(server, CL, false, "Trader does not have enough money");
			return;
		}
	}
	else if (actor->get_money() < total)
	{
		trade->StopTrade();
		send_trade_result(server, CL, false, "Not enough money");
		return;
	}

	if (partner_buys)
		trade->OnPerformTrade(0, total);
	else
		trade->OnPerformTrade(total, 0);

	for (u32 i = 0; i < items.size(); ++i)
		trade->TransferItem(items[i], partner_buys);

	// TransferItem changes money locally; publish the server result to everyone.
	actor->set_money(actor->get_money(), true);
	partner->set_money(partner->get_money(), true);
	trade->StopTrade();

	string256 message;
	xr_sprintf(message, "%s %u item(s) for %u RU", partner_buys ? "sold" : "bought", (u32)items.size(), total);
	Msg("[NetAnomaly] '%s' %s", CL->netcoop_login.c_str(), message);
	send_trade_result(server, CL, true, message);
}
} // namespace netcoop

// ---------------------------------------------------------------------------
// dialogue
// ---------------------------------------------------------------------------
namespace netcoop
{
enum ETalkOp : u8
{
	talk_start = 0,
	talk_choose = 1,
	talk_stop = 2,
};

enum ETalkFlags : u8
{
	talk_flag_open = 1,
	talk_flag_trade = 2,
};

static const u32 talk_max_text = 1024;
static const u32 talk_max_entries = 64;
static const float talk_max_distance = 5.f;
static xr_deque<TalkState> s_talk_states;

void client_talk_start(u16 npc_id)
{
	s_talk_states.clear();
	Msg("[NetAnomaly] talk request to NPC %u", npc_id);
	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK);
	P.w_u8(talk_start);
	P.w_u16(npc_id);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_talk_choose(LPCSTR id)
{
	if (!id || !id[0] || xr_strlen(id) >= 256)
		return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK);
	P.w_u8(talk_choose);
	P.w_stringZ(id);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_talk_stop()
{
	if (!g_pGameLevel)
		return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK);
	P.w_u8(talk_stop);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_on_talk_state(NET_Packet& P)
{
	if (P.r_elapsed() < 2 + 1 + 2)
		return;
	TalkState state;
	state.npc = P.r_u16();
	const u8 flags = P.r_u8();
	state.open = !!(flags & talk_flag_open);
	state.trade = !!(flags & talk_flag_trade);
	Msg("[NetAnomaly] talk state from server: NPC %u open=%d trade=%d", state.npc, state.open ? 1 : 0, state.trade ? 1 : 0);

	string1024 text;
	string256 id;
	const u16 lines = P.r_u16();
	for (u16 i = 0; i < lines && i < talk_max_entries; ++i)
	{
		if (P.r_elapsed() < 1)
			return;
		TalkLine line;
		line.npc = !!P.r_u8();
		if (!read_string(P, text, sizeof(text)))
			return;
		line.text = text;
		state.lines.push_back(line);
	}
	if (P.r_elapsed() < 2)
		return;
	const u16 choices = P.r_u16();
	for (u16 i = 0; i < choices && i < talk_max_entries; ++i)
	{
		TalkChoice choice;
		if (!read_string(P, id, sizeof(id)) || !read_string(P, text, sizeof(text)) || P.r_elapsed() < 1)
			return;
		choice.id = id;
		choice.text = text;
		choice.finalizer = !!P.r_u8();
		state.choices.push_back(choice);
	}
	s_talk_states.push_back(state);
}

bool client_take_talk_state(TalkState& out)
{
	if (s_talk_states.empty())
		return false;
	out = s_talk_states.front();
	s_talk_states.pop_front();
	return true;
}

struct TalkSession
{
	u16 npc;
	DIALOG_SHARED_PTR current;
};

typedef xr_map<u32, TalkSession> TalkSessions;
static TalkSessions s_talk_sessions;
static TalkState* s_talk_capture = NULL;

static void capture_line(bool npc, LPCSTR text)
{
	if (!s_talk_capture || !text || !text[0] || s_talk_capture->lines.size() >= talk_max_entries)
		return;
	TalkLine line;
	line.npc = npc;
	line.text = text;
	s_talk_capture->lines.push_back(line);
}

bool talk_capture_answer(LPCSTR text)
{
	if (!s_talk_capture)
		return false;
	capture_line(true, text);
	return true;
}

// ---------------------------------------------------------------------------
// server: per-player tasks
// ---------------------------------------------------------------------------
// The engine keeps one task list per level. A netcoop server keeps one per
// player Actor (stored in the ALife registry under that Actor's id) and makes
// it the level's list while that player is served.
typedef xr_map<u16, CGameTaskManager*> TaskManagers;
static TaskManagers s_task_managers;

static CGameTaskManager* server_task_manager(u16 actor_id)
{
	TaskManagers::iterator it = s_task_managers.find(actor_id);
	if (it != s_task_managers.end())
		return it->second;
	CGameTaskManager* manager = xr_new<CGameTaskManager>(actor_id);
	s_task_managers.insert(std::make_pair(actor_id, manager));
	return manager;
}

static void clear_tasks(CGameTaskManager* manager)
{
	vGameTasks& tasks = manager->GetGameTasks();
	for (u32 i = 0; i < tasks.size(); ++i)
	{
		if (tasks[i].game_task)
			tasks[i].game_task->RemoveMapLocations(false);
		tasks[i].destroy();
	}
	tasks.clear();
	manager->MarkChanged();
}

static void server_release_task_manager(u16 actor_id)
{
	TaskManagers::iterator it = s_task_managers.find(actor_id);
	if (it == s_task_managers.end())
		return;
	CGameTaskManager* manager = it->second;
	s_task_managers.erase(it);
	if (g_pGameLevel && Level().GameTaskManagerPtr() == manager)
		Level().SetGameTaskManager(NULL);
	clear_tasks(manager);
	xr_delete(manager);
}

// True when a player other than actor_id has this task in progress.
bool server_task_taken_by_other(u16 actor_id, LPCSTR task_id)
{
	if (!task_id || !task_id[0])
		return false;
	const shared_str id = task_id;
	for (TaskManagers::iterator it = s_task_managers.begin(); it != s_task_managers.end(); ++it)
		if (it->first != actor_id && it->second->HasGameTask(id, true))
			return true;
	return false;
}

// Server scripts use db.actor and the engine uses Actor() and the level task
// list; while one player is served all three refer to that player.
static bool s_actor_bound = false;
static CActor* s_bound_previous_actor = NULL;
static CGameTaskManager* s_bound_previous_tasks = NULL;

static void bind_engine_actor(CActor* actor)
{
	if (!g_pGameLevel || !Level().Server)
		return;
	if (actor)
	{
		if (!s_actor_bound)
		{
			s_actor_bound = true;
			s_bound_previous_actor = g_actor;
			s_bound_previous_tasks = Level().GameTaskManagerPtr();
		}
		g_actor = actor;
		Level().SetGameTaskManager(server_task_manager(actor->ID()));
	}
	else if (s_actor_bound)
	{
		s_actor_bound = false;
		g_actor = s_bound_previous_actor;
		Level().SetGameTaskManager(s_bound_previous_tasks);
		s_bound_previous_actor = NULL;
		s_bound_previous_tasks = NULL;
	}
}

// GAMMA dialogue scripts use db.actor; point it at the player being served.
static void bind_script_actor(CActor* actor)
{
	bind_engine_actor(actor);
	// Called for every server-side object script update; resolve the Lua function once.
	static ::luabind::functor<void> f;
	static bool resolved = false;
	if (!resolved)
		resolved = ai().script_engine().functor("netcoop_server_compat.bind_actor", f);
	if (!resolved)
		return;
	try
	{
		if (actor)
			f(actor->lua_game_object());
		else
			f();
	}
	catch (...)
	{
		Msg("! [NetAnomaly] netcoop_server_compat.bind_actor failed");
	}
}

static void talk_say(TalkSession& session, CPhraseDialogManager* our, const shared_str& phrase_id)
{
	capture_line(false, session.current->GetPhraseText(phrase_id));
	our->SayPhrase(session.current, phrase_id);
	if (session.current && session.current->IsFinished())
		session.current = DIALOG_SHARED_PTR((CPhraseDialog*)NULL);
}

// Mirrors CUITalkWnd::UpdateQuestions for a server-side dialogue run.
static void talk_build_choices(TalkSession& session, CPhraseDialogManager* our, CPhraseDialogManager* other,
                               TalkState& state)
{
	for (u32 guard = 0; guard < 16; ++guard)
	{
		state.choices.clear();
		if (!session.current)
		{
			our->UpdateAvailableDialogs(other);
			const CPhraseDialogManager::DIALOG_VECTOR& dialogs = our->AvailableDialogs();
			for (u32 i = 0; i < dialogs.size() && state.choices.size() < talk_max_entries; ++i)
			{
				TalkChoice choice;
				choice.id = dialogs[i]->GetDialogID();
				choice.text = dialogs[i]->DialogCaption();
				choice.finalizer = dialogs[i]->GetPhrase("0")->IsFinalizer();
				state.choices.push_back(choice);
			}
			return;
		}

		if (!session.current->IsWeSpeaking(our))
			return;

		const PHRASE_VECTOR& phrases = session.current->PhraseList();
		if (!phrases.empty() && session.current->allIsDummy())
		{
			// Only placeholder phrases: say one and continue, as the UI does.
			CPhrase* phrase = phrases[Random.randI(phrases.size())];
			talk_say(session, our, phrase->GetID());
			continue;
		}

		for (u32 i = 0; i < phrases.size() && state.choices.size() < talk_max_entries; ++i)
		{
			TalkChoice choice;
			choice.id = phrases[i]->GetID();
			choice.text = session.current->GetPhraseText(choice.id);
			choice.finalizer = phrases[i]->IsFinalizer();
			state.choices.push_back(choice);
		}
		return;
	}
}

static void send_talk_state(xrServer* server, xrClientData* CL, const TalkState& state)
{
	// Keep the packet well inside the transport size limit.
	u32 budget = 12000;
	xr_vector<const TalkLine*> lines;
	for (u32 i = 0; i < state.lines.size(); ++i)
	{
		const u32 size = state.lines[i].text.size() + 8;
		if (state.lines[i].text.size() < talk_max_text && budget > size)
		{
			budget -= size;
			lines.push_back(&state.lines[i]);
		}
	}
	xr_vector<const TalkChoice*> choices;
	for (u32 i = 0; i < state.choices.size(); ++i)
	{
		const TalkChoice& c = state.choices[i];
		const u32 size = c.id.size() + c.text.size() + 8;
		if (c.id.size() < 256 && c.text.size() < talk_max_text && budget > size)
		{
			budget -= size;
			choices.push_back(&c);
		}
	}

	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK_STATE);
	P.w_u16(state.npc);
	P.w_u8(u8((state.open ? talk_flag_open : 0) | (state.trade ? talk_flag_trade : 0)));
	P.w_u16((u16)lines.size());
	for (u32 i = 0; i < lines.size(); ++i)
	{
		P.w_u8(lines[i]->npc ? 1 : 0);
		P.w_stringZ(lines[i]->text.c_str());
	}
	P.w_u16((u16)choices.size());
	for (u32 i = 0; i < choices.size(); ++i)
	{
		P.w_stringZ(choices[i]->id.c_str());
		P.w_stringZ(choices[i]->text.c_str());
		P.w_u8(choices[i]->finalizer ? 1 : 0);
	}
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
}

static void talk_close(xrClientData* CL, CActor* actor, CInventoryOwner* npc)
{
	s_talk_sessions.erase(CL->ID.value());
	if (actor && actor->IsTalking())
		actor->StopTalk();
	if (npc && npc->IsTalking())
		npc->StopTalk();
}

void server_on_talk(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || !CL->owner || !g_pGameLevel || P.r_elapsed() < 1)
		return;

	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	if (!actor)
		return;

	const u8 op = P.r_u8();
	TalkSessions::iterator found = s_talk_sessions.find(CL->ID.value());

	u16 npc_id = found != s_talk_sessions.end() ? found->second.npc : u16(0xffff);
	if (op == talk_start)
	{
		if (P.r_elapsed() < 2)
			return;
		npc_id = P.r_u16();
	}

	CObject* npc_object = npc_id != 0xffff ? Level().Objects.net_Find(npc_id) : NULL;
	CInventoryOwner* npc = smart_cast<CInventoryOwner*>(npc_object);
	CEntityAlive* npc_alive = smart_cast<CEntityAlive*>(npc_object);
	CPhraseDialogManager* our = smart_cast<CPhraseDialogManager*>(actor);
	CPhraseDialogManager* other = smart_cast<CPhraseDialogManager*>(npc_object);

	if (op == talk_stop)
	{
		talk_close(CL, actor, npc);
		return;
	}

	TalkState state;
	state.npc = npc_id;
	state.open = false;
	state.trade = false;

	const bool valid = npc && npc_alive && npc_alive->g_Alive() && actor->g_Alive() && our && other &&
		!smart_cast<CActor*>(npc_object) &&
		actor->Position().distance_to(npc_object->Position()) <= talk_max_distance;
	if (!valid || (op == talk_choose && found == s_talk_sessions.end()) || op > talk_stop)
	{
		Msg("! [NetAnomaly] talk op %u with %u from '%s' rejected: npc=%d alive=%d distance=%.1f session=%d",
			op, npc_id, CL->netcoop_login.c_str(), npc ? 1 : 0, npc_alive && npc_alive->g_Alive() ? 1 : 0,
			npc_object ? actor->Position().distance_to(npc_object->Position()) : -1.f,
			found != s_talk_sessions.end() ? 1 : 0);
		talk_close(CL, actor, npc);
		send_talk_state(server, CL, state);
		return;
	}

	s_talk_capture = &state;
	bind_script_actor(actor);

	if (op == talk_start)
	{
		if (actor->IsTalking())
			actor->StopTalk();
		s_talk_sessions.erase(CL->ID.value());

		const bool offered = npc->OfferTalk(actor);
		Msg("[NetAnomaly] talk '%s' -> %s: offer=%d talk_enabled=%d", CL->netcoop_login.c_str(),
			npc_object->cName().c_str(), offered ? 1 : 0, npc->IsTalkEnabled() ? 1 : 0);
		if (offered)
		{
			actor->StartTalk(npc);

			TalkSession& session = s_talk_sessions[CL->ID.value()];
			session.npc = npc_id;
			session.current = DIALOG_SHARED_PTR((CPhraseDialog*)NULL);

			// Mirrors CUITalkWnd::InitOthersStartDialog.
			other->UpdateAvailableDialogs(our);
			if (!other->AvailableDialogs().empty())
			{
				session.current = other->AvailableDialogs().front();
				other->InitDialog(our, session.current);
				capture_line(true, session.current->GetPhraseText("0"));
				other->SayPhrase(session.current, "0");
				if (!session.current || session.current->IsFinished())
					session.current = DIALOG_SHARED_PTR((CPhraseDialog*)NULL);
			}
			talk_build_choices(session, our, other, state);
		}
	}
	else
	{
		char id[256];
		TalkSession& session = found->second;
		bool accepted = false;
		if (read_string(P, id, sizeof(id)))
		{
			if (!session.current)
			{
				if (our->HaveAvailableDialog(id))
				{
					session.current = our->GetDialogByID(id);
					our->InitDialog(other, session.current);
					talk_say(session, our, "0");
					accepted = true;
				}
			}
			else if (session.current->IsWeSpeaking(our))
			{
				const shared_str wanted = id;
				const PHRASE_VECTOR& phrases = session.current->PhraseList();
				for (u32 i = 0; i < phrases.size(); ++i)
				{
					if (phrases[i]->GetID() == wanted)
					{
						const shared_str phrase_id = phrases[i]->GetID();
						talk_say(session, our, phrase_id);
						accepted = true;
						break;
					}
				}
			}
		}
		if (!accepted)
			Msg("! [NetAnomaly] rejected dialogue choice from '%s'", CL->netcoop_login.c_str());
		talk_build_choices(session, our, other, state);
	}

	bind_script_actor(NULL);
	s_talk_capture = NULL;

	// A dialogue script may have ended the conversation (break_dialog).
	state.open = actor->IsTalking() && npc->IsTalking();
	state.trade = actor->IsTradeEnabled() && npc->IsTradeEnabled();
	if (!state.open)
		talk_close(CL, actor, npc);
	send_talk_state(server, CL, state);
}

// Drops sessions of connections that no longer exist (main thread).
void server_talk_prune(xrServer* server)
{
	for (TalkSessions::iterator it = s_talk_sessions.begin(); it != s_talk_sessions.end();)
	{
		ClientID id;
		id.set(it->first);
		if (!server->ID_to_client(id))
			it = s_talk_sessions.erase(it);
		else
			++it;
	}
}
} // namespace netcoop

namespace netcoop
{
bool client_owns_hud_item(const CObject* item)
{
	if (!item || !pure_client())
		return false;
	const CObject* parent = item->H_Parent();
	return parent && parent == Level().CurrentControlEntity();
}
} // namespace netcoop

namespace netcoop
{
static int s_nearest_bind_depth = 0;

bool server_bind_nearest_actor(CObject* npc)
{
	if (s_nearest_bind_depth > 0)
	{
		++s_nearest_bind_depth;
		return true;
	}
	if (!npc || !g_pGameLevel)
		return false;
	const u16 id = netcoop_nearest_player_actor(npc->Position());
	CActor* actor = id != 0xffff ? smart_cast<CActor*>(Level().Objects.net_Find(id)) : NULL;
	if (!actor || actor->getDestroy())
		return false;
	bind_script_actor(actor);
	s_nearest_bind_depth = 1;
	return true;
}

void server_unbind_actor()
{
	if (s_nearest_bind_depth <= 0)
		return;
	if (--s_nearest_bind_depth == 0)
		bind_script_actor(NULL);
}

ServerActorScope::ServerActorScope(CObject* object) : bound(false)
{
	if (enabled() && g_pGameLevel && Level().Server && object && !smart_cast<CActor*>(object))
		bound = server_bind_nearest_actor(object);
}

ServerActorScope::~ServerActorScope()
{
	if (bound)
		server_unbind_actor();
}
// ---------------------------------------------------------------------------
// task list replication
// ---------------------------------------------------------------------------
static const u32 tasks_update_interval = 500; // ms
static const u32 tasks_packet_budget = 12000;
static xr_map<u32, u32> s_sent_tasks_crc; // client id -> crc of the last list sent

struct TaskPlayer
{
	ClientID client;
	u16 actor;
};

struct CollectTaskPlayers
{
	xr_vector<TaskPlayer>* players;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (!CL || CL->flags.bLocal || CL->netcoop_role == role_none || !CL->owner)
			return;
		if (!smart_cast<CSE_ALifeCreatureActor*>(CL->owner))
			return;
		TaskPlayer p;
		p.client = CL->ID;
		p.actor = CL->owner->ID;
		players->push_back(p);
	}
};

static void write_tasks(CGameTaskManager* manager, NET_Packet& P)
{
	P.w_begin(M_NETCOOP_TASKS);
	const u32 count_pos = P.w_tell();
	P.w_u16(0);
	u16 count = 0;
	vGameTasks& tasks = manager->GetGameTasks();
	// Tasks in progress first, then finished ones while they fit.
	for (int pass = 0; pass < 2; ++pass)
	{
		for (u32 i = 0; i < tasks.size(); ++i)
		{
			CGameTask* t = tasks[i].game_task;
			if (!t || (t->GetTaskState() == eTaskStateInProgress) != (pass == 0))
				continue;
			CMemoryWriter w;
			t->save_task(w);
			const u32 size = tasks[i].task_id.size() + 1 + 2 + w.size();
			if (w.size() > 0xffff || P.w_tell() + size > tasks_packet_budget)
				continue;
			P.w_stringZ(tasks[i].task_id.c_str());
			P.w_u16(u16(w.size()));
			P.w(w.pointer(), w.size());
			++count;
		}
	}
	P.w_seek(count_pos, &count, sizeof(count));
}

void server_tasks_update(xrServer* server)
{
	if (!enabled() || !g_pGameLevel || !Level().Server)
		return;
	static u32 next_update = 0;
	const u32 now = Device.dwTimeGlobal;
	if (now < next_update)
		return;
	next_update = now + tasks_update_interval;

	// Managers of Actors that no longer exist (death, disconnect).
	xr_vector<u16> gone;
	for (TaskManagers::iterator it = s_task_managers.begin(); it != s_task_managers.end(); ++it)
		if (!smart_cast<CActor*>(Level().Objects.net_Find(it->first)))
			gone.push_back(it->first);
	for (u32 i = 0; i < gone.size(); ++i)
		server_release_task_manager(gone[i]);

	xr_vector<TaskPlayer> players;
	CollectTaskPlayers collect;
	collect.players = &players;
	server->ForEachClientDo(collect);

	static ::luabind::functor<void> lua_update;
	static bool lua_resolved = false;
	if (!lua_resolved)
		lua_resolved = ai().script_engine().functor("netcoop_server_compat.update_player_tasks", lua_update);

	for (u32 i = 0; i < players.size(); ++i)
	{
		CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(players[i].actor));
		if (!actor || actor->getDestroy())
			continue;

		bind_script_actor(actor);
		CGameTaskManager* manager = Level().GameTaskManagerPtr();
		if (manager)
		{
			manager->UpdateTasks();
			if (lua_resolved)
			{
				try
				{
					lua_update();
				}
				catch (...)
				{
					Msg("! [NetAnomaly] task update script failed for Actor %u", players[i].actor);
				}
			}
		}
		manager = Level().GameTaskManagerPtr();
		NET_Packet P;
		if (manager)
			write_tasks(manager, P);
		bind_script_actor(NULL);
		if (!manager)
			continue;

		const u32 crc = crc32(P.B.data, P.B.count);
		u32& sent = s_sent_tasks_crc[players[i].client.value()];
		if (sent == crc)
			continue;
		sent = crc;
		server->SendTo(players[i].client, P, net_flags(TRUE, TRUE));
	}
}

// ---------------------------------------------------------------------------
// client: task list from the server
// ---------------------------------------------------------------------------
static void notify_task(LPCSTR id, LPCSTR kind)
{
	::luabind::functor<void> f;
	if (!ai().script_engine().functor("netcoop_client_compat.on_task", f))
		return;
	try
	{
		f(id, kind);
	}
	catch (...)
	{
	}
}

void client_on_tasks(NET_Packet& P)
{
	if (!pure_client() || !Level().GameTaskManagerPtr())
		return;
	CGameTaskManager& manager = Level().GameTaskManager();

	xr_map<shared_str, ETaskState> previous;
	{
		vGameTasks& tasks = manager.GetGameTasks();
		for (u32 i = 0; i < tasks.size(); ++i)
			if (tasks[i].game_task)
				previous[tasks[i].task_id] = tasks[i].game_task->GetTaskState();
	}
	clear_tasks(&manager);

	if (P.r_elapsed() < sizeof(u16))
		return;
	const u16 count = P.r_u16();
	xr_vector<std::pair<shared_str, LPCSTR>> news;
	for (u16 i = 0; i < count; ++i)
	{
		string256 id;
		if (!read_string(P, id, sizeof(id)) || P.r_elapsed() < sizeof(u16))
			break;
		const u16 size = P.r_u16();
		if (P.r_elapsed() < size)
			break;
		IReader reader(P.B.data + P.r_tell(), size);
		P.r_advance(size);

		CGameTask* t = xr_new<CGameTask>();
		t->m_ID = id;
		t->load_task_remote(reader);
		vGameTasks& tasks = manager.GetGameTasks();
		tasks.push_back(SGameTaskKey(t->m_ID));
		tasks.back().game_task = t;

		xr_map<shared_str, ETaskState>::iterator old = previous.find(t->m_ID);
		const ETaskState state = t->GetTaskState();
		const bool was_active = old != previous.end() && old->second == eTaskStateInProgress;
		if (state == eTaskStateInProgress && !was_active)
			news.push_back(std::make_pair(t->m_ID, "new"));
		else if (was_active && state == eTaskStateCompleted)
			news.push_back(std::make_pair(t->m_ID, "complete"));
		else if (was_active && state == eTaskStateFail)
			news.push_back(std::make_pair(t->m_ID, "fail"));
	}

	if (!manager.ActiveTask())
	{
		CGameTask* first = manager.IterateGet(NULL, eTaskStateInProgress, true);
		if (first)
			manager.SetActiveTask(first);
	}
	manager.MarkChanged();
	if (CurrentGameUI())
		CurrentGameUI()->UpdatePda();

	for (u32 i = 0; i < news.size(); ++i)
		notify_task(news[i].first.c_str(), news[i].second);
}
// ---------------------------------------------------------------------------
// PDA news
// ---------------------------------------------------------------------------
struct FindActorOwner
{
	u16 actor_id;
	bool operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		return CL && !CL->flags.bLocal && CL->owner && CL->owner->ID == actor_id;
	}
};

void server_forward_news(u16 actor_id, const GAME_NEWS_DATA& news)
{
	if (!enabled() || !g_pGameLevel || !Level().Server)
		return;
	FindActorOwner find;
	find.actor_id = actor_id;
	xrClientData* CL = static_cast<xrClientData*>(Level().Server->FindClient(find));
	if (!CL)
		return;
	const u32 limit = 4000;
	if (news.news_caption.size() > limit || news.news_text.size() > limit || news.texture_name.size() > 256)
		return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_NEWS);
	P.w_u8(u8(news.m_type));
	P.w_stringZ(news.news_caption.size() ? news.news_caption.c_str() : "");
	P.w_stringZ(news.news_text.size() ? news.news_text.c_str() : "");
	P.w_stringZ(news.texture_name.size() ? news.texture_name.c_str() : "");
	P.w_s32(news.show_time);
	Level().Server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
}

void client_on_news(NET_Packet& P)
{
	if (!pure_client() || P.r_elapsed() < 1)
		return;
	CActor* actor = smart_cast<CActor*>(Level().CurrentControlEntity());
	if (!actor)
		return;
	GAME_NEWS_DATA news;
	news.m_type = P.r_u8() == GAME_NEWS_DATA::eTalk ? GAME_NEWS_DATA::eTalk : GAME_NEWS_DATA::eNews;
	string4096 caption, text;
	string256 texture;
	if (!read_string(P, caption, sizeof(caption)) || !read_string(P, text, sizeof(text)) ||
		!read_string(P, texture, sizeof(texture)) || P.r_elapsed() < sizeof(s32))
		return;
	news.news_caption = caption;
	news.news_text = text;
	news.texture_name = texture;
	news.show_time = P.r_s32();
	clamp(news.show_time, 0, 60000);
	actor->AddGameNews(news);
}

// ---------------------------------------------------------------------------
// server Lua -> client Lua messages
// ---------------------------------------------------------------------------
struct CollectLoggedIn
{
	xr_vector<ClientID>* ids;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (CL && !CL->flags.bLocal && CL->netcoop_role != role_none)
			ids->push_back(CL->ID);
	}
};

void script_broadcast(LPCSTR channel, LPCSTR data)
{
	if (!enabled() || !g_pGameLevel || !Level().Server || !channel || !channel[0])
		return;
	if (!data)
		data = "";
	if (xr_strlen(channel) >= 64 || xr_strlen(data) >= 8000)
	{
		Msg("! [NetAnomaly] script message '%s' is too large", channel);
		return;
	}
	xr_vector<ClientID> ids;
	CollectLoggedIn collect;
	collect.ids = &ids;
	Level().Server->ForEachClientDo(collect);
	for (u32 i = 0; i < ids.size(); ++i)
	{
		NET_Packet P;
		P.w_begin(M_NETCOOP_SCRIPT);
		P.w_stringZ(channel);
		P.w_stringZ(data);
		Level().Server->SendTo(ids[i], P, net_flags(TRUE, TRUE));
	}
}

void client_on_script(NET_Packet& P)
{
	if (!pure_client())
		return;
	string64 channel;
	static char data[8192];
	if (!read_string(P, channel, sizeof(channel)) || !read_string(P, data, sizeof(data)))
		return;
	::luabind::functor<void> f;
	if (!ai().script_engine().functor("netcoop_client_compat.on_script_message", f))
		return;
	try
	{
		f((LPCSTR)channel, (LPCSTR)data);
	}
	catch (...)
	{
	}
}

bool script_send_to_actor(u16 actor_id, LPCSTR channel, LPCSTR data)
{
	if (!enabled() || !g_pGameLevel || !Level().Server || !channel || !channel[0])
		return false;
	if (!data)
		data = "";
	if (xr_strlen(channel) >= 64 || xr_strlen(data) >= 8000)
		return false;
	FindActorOwner find;
	find.actor_id = actor_id;
	xrClientData* CL = static_cast<xrClientData*>(Level().Server->FindClient(find));
	if (!CL)
		return false;
	NET_Packet P;
	P.w_begin(M_NETCOOP_SCRIPT);
	P.w_stringZ(channel);
	P.w_stringZ(data);
	Level().Server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
	return true;
}

bool server_open_ui(u16 actor_id, LPCSTR kind, u16 partner_id)
{
	string128 data;
	xr_sprintf(data, "%s %u", kind, partner_id);
	const bool sent = script_send_to_actor(actor_id, "open_ui", data);
	if (enabled() && g_pGameLevel && Level().Server)
		Msg("[NetAnomaly] open %s with %u for Actor %u: %s", kind, partner_id, actor_id, sent ? "sent" : "no remote owner");
	return sent;
}

// Script hang watchdog. A mod script that never returns freezes the whole
// process (window, input, network). A watcher thread notices a frame that
// takes over 20 s and arms a Lua count hook: the hook logs the Lua stack of
// the running script and, after 60 s, aborts that script call with an error.
// No hook is installed while frames advance, so normal play costs nothing.
namespace
{
volatile LONG wd_armed = 0;
volatile u32 wd_frame = 0;
volatile u32 wd_since = 0;
volatile bool wd_logged = false;

void wd_disarm(lua_State* L)
{
	lua_sethook(L, 0, 0, 0);
	InterlockedExchange(&wd_armed, 0);
}

void wd_hook(lua_State* L, lua_Debug*)
{
	if (Device.dwFrame != wd_frame)
	{
		wd_disarm(L);
		return;
	}
	const u32 stuck = GetTickCount() - wd_since;
	if (!wd_logged)
	{
		wd_logged = true;
		Msg("! [NetAnomaly] script hang: frame %u has run for %u s, Lua stack:", wd_frame, stuck / 1000);
		lua_Debug ar;
		for (int level = 0; level < 24 && lua_getstack(L, level, &ar); ++level)
		{
			if (!lua_getinfo(L, "nSl", &ar))
				break;
			Msg("! [NetAnomaly]   %2d: %s:%d %s", level, ar.short_src, ar.currentline, ar.name ? ar.name : "?");
		}
		FlushLog();
	}
	if (stuck > 60000)
	{
		wd_disarm(L);
		wd_frame = 0; // re-arm if the script catches the error and goes on
		Msg("! [NetAnomaly] script hang: aborting the script call");
		FlushLog();
		luaL_error(L, "netcoop: script hung for %u s", stuck / 1000);
	}
}

// Hitch sampling: a frame over 100 ms gets the main thread's native stack
// logged (at most once a second), so stutter can be attributed to a system
// or a script callback. The thread is suspended only while its stack is
// unwound, without allocations or locks.
HANDLE wd_main_thread = 0;

u32 sample_main_stack(DWORD64* pcs, u32 max_pcs)
{
	if (!wd_main_thread || SuspendThread(wd_main_thread) == DWORD(-1))
		return 0;
	u32 count = 0;
	CONTEXT ctx;
	ZeroMemory(&ctx, sizeof(ctx));
	ctx.ContextFlags = CONTEXT_FULL;
	if (GetThreadContext(wd_main_thread, &ctx))
	{
		while (count < max_pcs && ctx.Rip)
		{
			pcs[count++] = ctx.Rip;
			DWORD64 image_base = 0;
			PRUNTIME_FUNCTION fn = RtlLookupFunctionEntry(ctx.Rip, &image_base, 0);
			if (!fn)
				break; // generated code (LuaJIT traces) has no unwind data
			void* handler_data = 0;
			DWORD64 establisher = 0;
			RtlVirtualUnwind(UNW_FLAG_NHANDLER, image_base, ctx.Rip, fn, &ctx, &handler_data, &establisher, 0);
		}
	}
	ResumeThread(wd_main_thread);
	return count;
}

void log_hitch(u32 frame, u32 ms, const DWORD64* pcs, u32 count)
{
	static bool sym_ready = false;
	if (!sym_ready)
	{
		sym_ready = true;
		SymSetOptions(SymGetOptions() | SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
		SymInitialize(GetCurrentProcess(), 0, TRUE);
	}
	string4096 line;
	xr_sprintf(line, "[NetAnomaly][hitch] frame %u at %u ms:", frame, ms);
	for (u32 i = 0; i < count; ++i)
	{
		char buffer[sizeof(SYMBOL_INFO) + 256];
		SYMBOL_INFO* sym = (SYMBOL_INFO*)buffer;
		ZeroMemory(buffer, sizeof(buffer));
		sym->SizeOfStruct = sizeof(SYMBOL_INFO);
		sym->MaxNameLen = 255;
		DWORD64 displacement = 0;
		string512 part;
		if (SymFromAddr(GetCurrentProcess(), pcs[i], &displacement, sym))
			xr_sprintf(part, " < %s", sym->Name);
		else
			xr_sprintf(part, " < %llx", pcs[i]);
		xr_strcat(line, part);
	}
	Msg("%s", line);
}

DWORD WINAPI wd_thread(void*)
{
	u32 last_frame = Device.dwFrame;
	u32 since = GetTickCount();
	u32 sampled_frame = 0;
	u32 next_sample = 0;
	for (;;)
	{
		Sleep(10);
		const u32 frame = Device.dwFrame;
		const u32 now = GetTickCount();
		if (frame != last_frame)
		{
			last_frame = frame;
			since = now;
			continue;
		}
		if (g_netcoop_metrics && g_pGameLevel && now - since >= 100 && sampled_frame != frame && now >= next_sample)
		{
			sampled_frame = frame;
			next_sample = now + 1000;
			DWORD64 pcs[24];
			const u32 count = sample_main_stack(pcs, 24);
			if (count && Device.dwFrame == frame)
				log_hitch(frame, now - since, pcs, count);
		}
		if (now - since < 20000 || wd_armed || !g_pGameLevel || wd_frame == frame)
			continue;
		wd_frame = frame;
		wd_since = since;
		wd_logged = false;
		InterlockedExchange(&wd_armed, 1);
		Msg("! [NetAnomaly] frame %u stuck for %u s, watching scripts", frame, (now - since) / 1000);
		lua_sethook(ai().script_engine().lua(), wd_hook, LUA_MASKCOUNT, 10000);
	}
}
} // namespace

void script_watchdog_start()
{
	static bool started = false;
	if (started || !enabled())
		return;
	started = true;
	DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &wd_main_thread,
	                THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, 0);
	HANDLE h = CreateThread(0, 0, wd_thread, 0, 0, 0);
	if (h)
		CloseHandle(h);
}

} // namespace netcoop

// ---------------------------------------------------------------------------
// Network smoothness and metrics (doc 38, stages 0 and 1)
// ---------------------------------------------------------------------------
#include "Weapon.h"
#include "ai/stalker/ai_stalker.h"
#include "memory_manager.h"
#include "enemy_manager.h"
#include "visual_memory_manager.h"

int g_netcoop_smooth = 1;
int g_netcoop_interp_ms = 100;
int g_netcoop_metrics = 1;

namespace netcoop
{
bool smooth()
{
	return enabled() && g_netcoop_smooth != 0;
}

u32 remote_interp_delay()
{
	return (pure_client() && g_netcoop_smooth) ? u32(g_netcoop_interp_ms) : NET_Latency;
}

namespace
{
struct Metrics
{
	u32 frames, frame_ms_sum, frame_ms_max, frames_over_33, frames_over_100;
	u32 snaps, snap_ms_sum, snap_ms_max, snaps_over_100, dups;
	u32 puppet_frames, extrap_frames, jumps;
	float jump_max;
	u32 acks, fixes;
	float err_sum, err_max;
	u32 owner_rejects;
	float owner_reject_max;
	u32 shots;
};
Metrics m;
u32 next_print = 0;

struct PuppetTrack
{
	Fvector pos;
	u32 time;
};
xr_map<u16, PuppetTrack> puppets;
xr_map<u16, u32> shot_log_time;
} // namespace

void metric_snapshot(u32 interval_ms)
{
	++m.snaps;
	m.snap_ms_sum += interval_ms;
	m.snap_ms_max = _max(m.snap_ms_max, interval_ms);
	if (interval_ms > 100)
		++m.snaps_over_100;
}

void metric_snapshot_duplicate()
{
	++m.dups;
}

// A jump is a frame step longer than a running NPC can cover (10 m/s) plus
// 0.25 m: the object was teleported, not moved.
void metric_puppet_frame(u16 id, const Fvector& pos, bool extrapolating)
{
	++m.puppet_frames;
	if (extrapolating)
		++m.extrap_frames;
	PuppetTrack& t = puppets[id];
	const u32 now = Device.dwTimeGlobal;
	if (t.time && now - t.time < 500)
	{
		const float step = t.pos.distance_to(pos);
		const float allowed = 0.25f + 10.f * float(now - t.time) / 1000.f;
		if (step > allowed)
		{
			++m.jumps;
			m.jump_max = _max(m.jump_max, step);
		}
	}
	t.pos = pos;
	t.time = now;
}

void metric_actor_error(float error, bool applied)
{
	++m.acks;
	m.err_sum += error;
	m.err_max = _max(m.err_max, error);
	if (applied)
		++m.fixes;
}

void metric_owner_step_rejected(float step)
{
	++m.owner_rejects;
	m.owner_reject_max = _max(m.owner_reject_max, step);
}

// Server: who an NPC shoots at and whether it sees the target. Client: a
// puppet's weapon must never start firing on its own.
void metric_weapon_fire(CWeapon* weapon)
{
	if (!enabled() || !g_pGameLevel || !weapon || !weapon->H_Parent())
		return;
	CAI_Stalker* stalker = smart_cast<CAI_Stalker*>(weapon->H_Parent());
	if (!stalker)
		return;
	++m.shots;
	const u32 now = Device.dwTimeGlobal;
	u32& last = shot_log_time[stalker->ID()];
	if (last && now - last < 3000)
		return;
	last = now;
	if (pure_client())
	{
		Msg("[NetAnomaly][shot] client puppet %s (%u) started firing %s", stalker->cName().c_str(), stalker->ID(),
		    weapon->cNameSect().c_str());
		return;
	}
	const CEntityAlive* enemy = stalker->g_Alive() ? stalker->memory().enemy().selected() : 0;
	Msg("[NetAnomaly][shot] %s (%u) fires %s at %s (%u) dist %.1f visible %d", stalker->cName().c_str(), stalker->ID(),
	    weapon->cNameSect().c_str(), enemy ? enemy->cName().c_str() : "no enemy", enemy ? enemy->ID() : 0,
	    enemy ? enemy->Position().distance_to(stalker->Position()) : 0.f,
	    enemy ? int(stalker->memory().visual().visible_now(enemy)) : 0);
}

void metrics_update()
{
	if (!enabled())
		return;
	const u32 dt = Device.dwTimeDelta;
	++m.frames;
	m.frame_ms_sum += dt;
	m.frame_ms_max = _max(m.frame_ms_max, dt);
	if (dt > 33)
		++m.frames_over_33;
	if (dt > 100)
		++m.frames_over_100;

	const u32 now = GetTickCount();
	if (!next_print)
		next_print = now + 10000;
	if (now < next_print)
		return;
	next_print = now + 10000;
	if (g_netcoop_metrics)
	{
		Msg("[NetAnomaly][metrics] %s smooth=%d delay=%u | frame avg %.1f max %u >33ms %u >100ms %u"
		    " | snaps %u avg %.0f max %u >100ms %u dup %u | puppets %u extrap %.1f%% jumps %u max %.2f"
		    " | actor acks %u fixes %u err avg %.2f max %.2f | owner rejects %u max %.1f | shots %u",
		    pure_client() ? "client" : "server", g_netcoop_smooth, remote_interp_delay(),
		    m.frames ? float(m.frame_ms_sum) / m.frames : 0.f, m.frame_ms_max, m.frames_over_33, m.frames_over_100,
		    m.snaps, m.snaps ? float(m.snap_ms_sum) / m.snaps : 0.f, m.snap_ms_max, m.snaps_over_100, m.dups,
		    m.puppet_frames, m.puppet_frames ? 100.f * m.extrap_frames / m.puppet_frames : 0.f, m.jumps, m.jump_max,
		    m.acks, m.fixes, m.acks ? m.err_sum / m.acks : 0.f, m.err_max, m.owner_rejects, m.owner_reject_max,
		    m.shots);
	}
	ZeroMemory(&m, sizeof(m));
	if (puppets.size() > 4096)
		puppets.clear();
	if (shot_log_time.size() > 4096)
		shot_log_time.clear();
}
} // namespace netcoop
