// Included in netcoop.cpp (namespace netcoop) - server: the account store and what lives beside it.
// Split out of netcoop.cpp in the same order (doc 151); see the file list there.

// ---------------------------------------------------------------------------
// server: account storage
// ---------------------------------------------------------------------------
struct Account
{
    xr_string firebase_uid;
	// 0: pending, 1: approved, 2: rejected. Old account files default to approved.
	u8 approval = 1;
	xr_string device;
	xr_string login; // as registered
	u8 role;
	xr_string salt;
	xr_string hash;
	bool has_money;
	u32 money;
	u32 failures;
	u32 locked_until;
	// Changed here and not yet written. Location servers share the file:
	// everything else is re-read from it (accounts_refresh).
	bool touched = false;
};

typedef xr_map<xr_string, Account> Accounts;
static Accounts s_accounts;
static bool s_accounts_loaded = false;
static bool s_accounts_dirty = false;

static void accounts_path(string_path& path)
{
	FS.update_path(path, "$app_data_root$", "netcoop_accounts.txt");
}

static FILETIME s_accounts_stamp = {};

static bool accounts_file_stamp(FILETIME& stamp)
{
	string_path path;
	accounts_path(path);
	WIN32_FILE_ATTRIBUTE_DATA data;
	if (!GetFileAttributesExA(path, GetFileExInfoStandard, &data)) return false;
	stamp = data.ftLastWriteTime;
	return true;
}

// A lock every server of the location cluster honours, also on other
// machines that share $app_data_root$ over the network: an exclusively
// opened lock file that disappears when closed (and when the process dies).
// A named mutex spans one machine only.
struct ClusterFileLock
{
	HANDLE file = INVALID_HANDLE_VALUE;
	bool held = false;
	explicit ClusterFileLock(LPCSTR name, u32 timeout_ms = 5000)
	{
		string_path dir, path;
		FS.update_path(dir, "$app_data_root$", "netcoop_locks\\");
		CreateDirectoryA(dir, nullptr);
		xr_sprintf(path, "%s%s.lock", dir, name);
		const u32 started = GetTickCount();
		for (;;)
		{
			file = CreateFileA(path, GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS,
				FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, nullptr);
			if (file != INVALID_HANDLE_VALUE) { held = true; return; }
			if (GetTickCount() - started >= timeout_ms) return;
			Sleep(5);
		}
	}
	~ClusterFileLock() { if (file != INVALID_HANDLE_VALUE) CloseHandle(file); }
	ClusterFileLock(const ClusterFileLock&) = delete;
	ClusterFileLock& operator=(const ClusterFileLock&) = delete;
};

// One writer at a time across the location server processes.
struct AccountsFileLock
{
	ClusterFileLock lock;
	bool held;
	AccountsFileLock() : lock("accounts"), held(lock.held) {}
};

static void accounts_read(Accounts& out)
{
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
		char* fields[8] = {};
		u32 count = 0;
		char* cursor = line;
		while (count < 8)
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
        a.firebase_uid = count >= 8 ? fields[7] : "";
		a.approval = count >= 7 ? (!xr_strcmp(fields[6], "pending") ? 0 : !xr_strcmp(fields[6], "rejected") ? 2 : 1) : 1;
		a.login = fields[0];
		a.device = count >= 6 && key_valid(fields[5]) ? fields[5] : "";
		a.role = !xr_strcmp(fields[1], "admin") ? u8(role_admin) : u8(role_player);
		a.salt = fields[2];
		a.hash = fields[3];
		a.has_money = count >= 5 && fields[4][0] && fields[4][0] != '-';
		a.money = a.has_money ? (u32)strtoul(fields[4], NULL, 10) : 0;
		a.failures = 0;
		a.locked_until = 0;

		xr_string key = a.login;
		to_lower(key);
		out[key] = a;
	}
	fclose(f);
}

// Another location server may have written the file (registration, money of
// a player who is there now): adopt its records except our unsaved changes.
static void accounts_refresh()
{
	FILETIME stamp;
	if (!accounts_file_stamp(stamp) || !CompareFileTime(&stamp, &s_accounts_stamp)) return;
	Accounts file;
	accounts_read(file);
	s_accounts_stamp = stamp;
	for (auto& entry : file)
	{
		auto it = s_accounts.find(entry.first);
		if (it == s_accounts.end()) { s_accounts[entry.first] = entry.second; continue; }
		if (it->second.touched) continue;
		const u32 failures = it->second.failures, locked = it->second.locked_until;
		it->second = entry.second;
		it->second.failures = failures; it->second.locked_until = locked;
	}
}

static void accounts_load()
{
	if (s_accounts_loaded)
	{
		accounts_refresh();
		return;
	}
	s_accounts_loaded = true;
	accounts_read(s_accounts);
	accounts_file_stamp(s_accounts_stamp);
	Msg("[Lost Zone] loaded %u account(s)", (u32)s_accounts.size());
}

static bool accounts_save()
{
	if (!s_accounts_dirty)
		return true;

	AccountsFileLock lock;
	if (!lock.held)
	{
		Msg("! [Lost Zone] account save held: file mutex unavailable");
		return false;
	}
	accounts_refresh();
	string_path path, temp;
	accounts_path(path);
	xr_sprintf(temp, "%s.%u.tmp", path, GetCurrentProcessId());
	FILE* f = fopen(temp, "wb");
	if (!f)
	{
		Msg("! [Lost Zone] cannot write %s", temp);
		return false;
	}
	fprintf(f, "# NetAnomaly accounts: login|role|salt|pbkdf2-sha256|money|device-digest|approval\n");
	for (Accounts::const_iterator it = s_accounts.begin(); it != s_accounts.end(); ++it)
	{
		const Account& a = it->second;
		if (a.has_money)
			fprintf(f, "%s|%s|%s|%s|%u|%s|%s|%s\n", a.login.c_str(), role_name(a.role), a.salt.c_str(), a.hash.c_str(), a.money, a.device.c_str(), a.approval == 0 ? "pending" : a.approval == 2 ? "rejected" : "approved", a.firebase_uid.c_str());
		else
			fprintf(f, "%s|%s|%s|%s|-|%s|%s|%s\n", a.login.c_str(), role_name(a.role), a.salt.c_str(), a.hash.c_str(), a.device.c_str(), a.approval == 0 ? "pending" : a.approval == 2 ? "rejected" : "approved", a.firebase_uid.c_str());
	}
	const bool flushed = !ferror(f) && fflush(f) == 0 && _commit(_fileno(f)) == 0;
	const bool closed = fclose(f) == 0;
	if (!flushed || !closed)
	{
		DeleteFileA(temp);
		Msg("! [Lost Zone] incomplete account save; keeping %s", path);
		return false;
	}
	if (!MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
	{
		Msg("! [Lost Zone] cannot replace %s", path);
		return false;
	}
	s_accounts_dirty = false;
	for (auto& entry : s_accounts) entry.second.touched = false;
	accounts_file_stamp(s_accounts_stamp);
	return true;
}

static Account* account_find(LPCSTR login)
{
	accounts_load();
	xr_string key = login;
	to_lower(key);
	Accounts::iterator it = s_accounts.find(key);
	return it == s_accounts.end() ? NULL : &it->second;
}

bool server_reset_device(LPCSTR login)
{
    Account* account = account_find(login);
    if (!account) return false;
    account->device.clear(); account->touched = true; s_accounts_dirty = true; accounts_save();
    return true;
}

bool script_registration_decide(LPCSTR login, bool accept)
{
    // Compatibility export for older scripts. Registration is open; bans
    // have their own authenticated server-console path.
    (void)login;
    (void)accept;
    return false;
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
	if (role == role_admin) a->approval = 1; // console bootstrap of the first administrator
	a->touched = true;
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

static u32 storage_capacity(bool safe);
static u32 storage_section_cost(LPCSTR section);
static bool item_state_ready_for_save(u16 id);
static bool storage_launcher_charge(CSE_Abstract* child, u16 parent); // netcoop_storage.inc
static void item_state_for_save(u16 id, xr_vector<u8>& out);
static void item_state_restore(u16 id, const xr_vector<u8>& saved);
// netcoop_world_store.inc: a character that took items from the world is
// written only after the world commit that no longer has them (doc 43 G08).
static bool world_store_takes_committed(u16 actor_id);
static void world_store_request_save();
bool world_store_save_now(LPCSTR reason);
static void world_store_note_taken(u16 actor_id);
static u32 storage_live_capacity(CActor* actor);
#include "netcoop_characters.inc"
#include "netcoop_storage.inc"
#include "netcoop_pda.inc"
#include "netcoop_marks.inc"
#include "netcoop_map.inc"
#include "netcoop_items.inc"
// Called synchronously on the authority's world-checkpoint path. Offline
// props already have their server state; capture only live physical props.
static bool world_store_capture_physics_props()
{
	if (!Level().Server || !Level().Server->game) return false;
	::luabind::functor<bool> door_binder_ready;
	const bool classify_doors = ai().script_engine().functor(
		"zz_netcoop_world_rules.physics_door_binder_ready", door_binder_ready);
	for (u32 n = 0; n < Level().Objects.o_count(); ++n)
	{
		auto* object = Level().Objects.o_get_by_iterator(n);
		if (CBreakableObject* breakable = smart_cast<CBreakableObject*>(object))
		{
			if (breakable->getDestroy() || breakable->H_Parent()) continue;
			CSE_Abstract* entity = Level().Server->game->get_entity_from_eid(breakable->ID());
			if (!breakable->netcoop_capture_saved_health(entity))
			{
				Msg("! [NetAnomaly][world] cannot capture breakable object %u", breakable->ID());
				return false;
			}
			continue;
		}
		if (CPhysicsSkeletonObject* fragment = smart_cast<CPhysicsSkeletonObject*>(object))
		{
			if (fragment->getDestroy() || fragment->H_Parent() ||
				!fragment->PPhysicsShell() || !fragment->PHGetSyncItemsNumber()) continue;
			CSE_Abstract* entity = Level().Server->game->get_entity_from_eid(fragment->ID());
			CSE_PHSkeleton* skeleton = smart_cast<CSE_PHSkeleton*>(entity);
			if (skeleton && !skeleton->need_save()) continue;
			if (!fragment->netcoop_capture_saved_physics(entity))
			{
				Msg("! [NetAnomaly][world] cannot capture physics fragment %u", fragment->ID());
				return false;
			}
			continue;
		}
		CPhysicObject* prop = smart_cast<CPhysicObject*>(object);
		if (!prop || prop->getDestroy() || prop->H_Parent() ||
			!prop->PPhysicsShell() || !prop->PHGetSyncItemsNumber()) continue;
		CSE_Abstract* entity = Level().Server->game->get_entity_from_eid(prop->ID());
		CSE_PHSkeleton* skeleton = smart_cast<CSE_PHSkeleton*>(entity);
		if (skeleton && !skeleton->need_save()) continue;
		const bool capture_door_binder = classify_doors && door_binder_ready(prop->ID());
		if (!prop->netcoop_capture_saved_physics(entity, capture_door_binder))
		{
			Msg("! [NetAnomaly][world] cannot capture physics prop %u", prop->ID());
			return false;
		}
		if (CDestroyablePhysicsObject* destroyable = smart_cast<CDestroyablePhysicsObject*>(prop))
		{
			if (!destroyable->netcoop_capture_saved_health(entity))
			{
				Msg("! [NetAnomaly][world] cannot capture destroyable health %u", prop->ID());
				return false;
			}
		}
	}
	return true;
}
#include "netcoop_world_store.inc"
#include "netcoop_campfire.inc"
#include "netcoop_voice_record.inc"
#include "netcoop_photo.inc"
#include "netcoop_voice.inc"
