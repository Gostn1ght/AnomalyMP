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
		const u32 now = timeGetTime();
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

static void destroy_pending_actors()
{
	xr_vector<u16> ids;
	s_pending_lock.Enter();
	ids.swap(s_pending_actor_destroy);
	s_pending_lock.Leave();

	for (u32 i = 0; i < ids.size() && g_pGameLevel; ++i)
	{
		CGameObject* actor_object = smart_cast<CGameObject*>(Level().Objects.net_Find(ids[i]));
		if (actor_object && smart_cast<CActor*>(actor_object))
		{
			Msg("[NetAnomaly] removing Actor %u of a disconnected player", ids[i]);
			actor_object->DestroyObject();
		}
	}
}

struct StoreMoney
{
	void operator()(IClient* client) const { store_money(static_cast<xrClientData*>(client)); }
};

void server_update(xrServer* server)
{
	if (!enabled())
		return;
	destroy_pending_actors();
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
