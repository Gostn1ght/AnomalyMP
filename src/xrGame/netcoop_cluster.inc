// Included inside namespace netcoop in netcoop.cpp, after the account and
// character code. Location cluster (doc 43 H): one dedicated server process
// per map, all started from the same runtime folder, so accounts and
// character files are shared. A level changer moves a player to the server
// of the target map:
//   1. the source validates the request (player inside that changer, alive,
//      target map served by the cluster) and freezes the player;
//   2. it saves the character synchronously with the destination point of
//      the changer as its position, releases the player's session lease and
//      writes a signed single-use ticket;
//   3. the client reconnects to the target server with its own credentials;
//   4. the target accepts the login only when no other server holds a live
//      lease, consumes the ticket and loads the character fresh from disk.
// The character file stays the single copy of the inventory: the source
// never saves the player again after step 2, a frozen player cannot drop or
// hand over items, and a crashed source releases its lease by timeout.
//
// netcoop_cluster.ltx in $app_data_root$:
//   [locations]
//   l01_escape = 203.0.113.5:1267   ; address the clients use for that map
//   l02_garbage = 203.0.113.5:1270
// netcoop_cluster.secret (created by the first server that needs it) signs
// tickets. Leases and tickets live in $app_data_root$/netcoop_cluster/.

static void store_money(xrClientData* CL); // netcoop.cpp, account money of a slot-1 character

static u64 cluster_unix_ms();

static const u32 cluster_lease_ttl_s = 30, cluster_ticket_ttl_s = 180, cluster_leave_ms = 3000;

struct ClusterLeaving { u16 actor = 0; u32 since = 0; xr_string level; };
static xr_map<u32, ClusterLeaving> s_cluster_leaving; // ClientID value -> leaving player
static xr_map<u32, u32> s_cluster_redirected; // ClientID value -> time of a login redirect
static u32 s_cluster_heartbeat = 0;
static xr_string s_cluster_secret;

static u32 cluster_now() { return u32(_time64(nullptr)); }

static u32 cluster_port()
{
	static u32 port = 0xffffffff;
	if (port != 0xffffffff) return port;
	port = 0;
	if (LPCSTR option = strstr(Core.Params, "-netport "))
		port = u32(atoi(option + xr_strlen("-netport ")));
	return port;
}

static void cluster_dir(string_path& path)
{
	FS.update_path(path, "$app_data_root$", "netcoop_cluster\\");
	CreateDirectoryA(path, nullptr);
}

static void cluster_file(LPCSTR prefix, LPCSTR login, int slot, string_path& path)
{
	xr_string lower = login; to_lower(lower);
	string_path dir; cluster_dir(dir);
	if (slot < 0) xr_sprintf(path, "%s%s_%s.txt", dir, prefix, lower.c_str());
	else xr_sprintf(path, "%s%s_%s_%d.txt", dir, prefix, lower.c_str(), slot);
}

static bool cluster_read_line(LPCSTR path, xr_string& line)
{
	FILE* f = fopen(path, "rb");
	if (!f) return false;
	char buffer[512] = {};
	const size_t size = fread(buffer, 1, sizeof(buffer) - 1, f);
	fclose(f);
	buffer[size] = 0;
	buffer[strcspn(buffer, "\r\n")] = 0;
	line = buffer;
	return true;
}

static bool cluster_write_line(LPCSTR path, LPCSTR line)
{
	string_path temp;
	xr_sprintf(temp, "%s.%u.tmp", path, GetCurrentProcessId());
	FILE* f = fopen(temp, "wb");
	if (!f) return false;
	fputs(line, f);
	const bool ok = !ferror(f) && fflush(f) == 0 && _commit(_fileno(f)) == 0;
	if (fclose(f) != 0 || !ok) { DeleteFileA(temp); return false; }
	if (!MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) { DeleteFileA(temp); return false; }
	return true;
}

// Address the clients use for a map, from netcoop_cluster.ltx.
static bool cluster_location(LPCSTR level, xr_string& host, u32& port)
{
	string_path path;
	FS.update_path(path, "$app_data_root$", "netcoop_cluster.ltx");
	if (!level || !level[0] || GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) return false;
	CInifile ini(path, TRUE, TRUE, FALSE);
	if (!ini.line_exist("locations", level)) return false;
	xr_string value = ini.r_string("locations", level);
	const size_t colon = value.rfind(':');
	if (colon == xr_string::npos || colon == 0) return false;
	host = value.substr(0, colon);
	port = u32(atoi(value.c_str() + colon + 1));
	for (char c : host)
		if (!isalnum((unsigned char)c) && c != '.' && c != '-' && c != '_') return false;
	return port > 0 && port < 65536;
}

static bool cluster_config_present()
{
	string_path path;
	FS.update_path(path, "$app_data_root$", "netcoop_cluster.ltx");
	return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

// ---- server status (doc 43 H01): alive and not full -----------------------
// Every server writes "unix_s players capacity" to netcoop_cluster/status_<port>.txt
// each 10 s. A transfer or a login redirect to a map whose server is down or
// full would strand the character there, so neither happens then.
static const u32 cluster_status_ttl_s = 30;

static u32 cluster_capacity()
{
	static u32 capacity = 0xffffffff;
	if (capacity != 0xffffffff) return capacity;
	capacity = 0;
	if (LPCSTR option = strstr(Core.Params, "maxplayers=")) capacity = u32(atoi(option + xr_strlen("maxplayers=")));
	return capacity;
}

struct ClusterCountPlayers
{
	u32* count;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (CL && !CL->flags.bLocal) ++*count;
	}
};

static void cluster_status_write(xrServer* server)
{
	u32 players = 0;
	ClusterCountPlayers count = {&players};
	server->ForEachClientDo(count);
	string_path dir, file; cluster_dir(dir);
	xr_sprintf(file, "%sstatus_%u.txt", dir, cluster_port());
	string128 line; xr_sprintf(line, "%u %u %u", cluster_now(), players, cluster_capacity());
	cluster_write_line(file, line);
}

// "" when the server on that port can take one more player, else the reason.
static LPCSTR cluster_target_problem(u32 port)
{
	string_path dir, file; cluster_dir(dir);
	xr_sprintf(file, "%sstatus_%u.txt", dir, port);
	xr_string line; u32 stamp = 0, players = 0, capacity = 0;
	if (!cluster_read_line(file, line) || sscanf(line.c_str(), "%u %u %u", &stamp, &players, &capacity) != 3 ||
		cluster_now() > stamp + cluster_status_ttl_s)
		return "the server of that map is offline";
	// The server's own authority client counts against maxplayers.
	if (capacity && players + 1 >= capacity) return "the server of that map is full";
	return "";
}

static bool cluster_secret()
{
	if (!s_cluster_secret.empty()) return true;
	string_path path;
	FS.update_path(path, "$app_data_root$", "netcoop_cluster.secret");
	xr_string line;
	if (!cluster_read_line(path, line) || line.size() < 64)
	{
		// The first server creates it; CREATE_NEW lets exactly one win a race.
		u8 bytes[32];
		if (!random_bytes(bytes, sizeof(bytes))) return false;
		const xr_string fresh = to_hex(bytes, sizeof(bytes));
		HANDLE file = CreateFileA(path, GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
		if (file != INVALID_HANDLE_VALUE)
		{
			DWORD written = 0;
			WriteFile(file, fresh.c_str(), DWORD(fresh.size()), &written, nullptr);
			FlushFileBuffers(file);
			CloseHandle(file);
		}
		if (!cluster_read_line(path, line) || line.size() < 64) return false;
	}
	s_cluster_secret = line;
	return true;
}

static bool hmac_sha256_hex(const xr_string& key, const xr_string& data, xr_string& out)
{
	BCRYPT_ALG_HANDLE alg = nullptr;
	BCRYPT_HASH_HANDLE hash = nullptr;
	u8 digest[32];
	bool ok = BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, BCRYPT_ALG_HANDLE_HMAC_FLAG)) &&
		BCRYPT_SUCCESS(BCryptCreateHash(alg, &hash, nullptr, 0, (PUCHAR)key.data(), ULONG(key.size()), 0)) &&
		BCRYPT_SUCCESS(BCryptHashData(hash, (PUCHAR)data.data(), ULONG(data.size()), 0)) &&
		BCRYPT_SUCCESS(BCryptFinishHash(hash, digest, sizeof(digest), 0));
	if (hash) BCryptDestroyHash(hash);
	if (alg) BCryptCloseAlgorithmProvider(alg, 0);
	if (ok) out = to_hex(digest, sizeof(digest));
	return ok;
}

// ---- session lease: one server owns a logged-in account at a time --------

// A timestamp read followed by a rename is not an ownership claim: two
// processes can both see an absent/stale lease, and a paused old process can
// resume after its TTL and overwrite the new owner's snapshot. Keep an OS
// exclusive handle for the ENTIRE session, including background save commits.
// A crash releases the handle; a live stalled process cannot be stolen from.
// The empty ownership file is never deleted/replaced (avoids inode/name races).
// This is local Windows/shared-runtime authority, not cross-host fencing.
static xr_map<xr_string, HANDLE> s_cluster_ownership;

static xr_string cluster_login_key(LPCSTR login)
{
	xr_string key = login; to_lower(key); return key;
}

static bool cluster_lease_holder(LPCSTR login, u32& port, u32& stamp)
{
	string_path path; cluster_file("online", login, -1, path);
	xr_string line;
	return cluster_read_line(path, line) && sscanf(line.c_str(), "%u %u", &port, &stamp) == 2;
}

static bool cluster_lease_write(LPCSTR login)
{
	if (s_cluster_ownership.find(cluster_login_key(login)) == s_cluster_ownership.end()) return false;
	string_path path; cluster_file("online", login, -1, path);
	string64 line; xr_sprintf(line, "%u %u", cluster_port(), cluster_now());
	return cluster_write_line(path, line);
}

// Removes the lease only while it is still ours: the target server may have
// taken it over already.
static void cluster_lease_release(LPCSTR login)
{
	const auto owned = s_cluster_ownership.find(cluster_login_key(login));
	if (owned == s_cluster_ownership.end()) return; // Never remove another owner's lease.
	// Drain every queued old snapshot before another process can load this
	// account. In normal handoff/disconnect the preceding synchronous save has
	// already drained; this also covers front-end storage and auth rejection.
	character_commits_flush();
	u32 port = 0, stamp = 0;
	if (cluster_lease_holder(login, port, stamp) && port == cluster_port())
	{
		string_path path; cluster_file("online", login, -1, path);
		DeleteFileA(path);
	}
	CloseHandle(owned->second);
	s_cluster_ownership.erase(owned);
}

// Login on this server: refused while another live server still has the
// player; otherwise the lease becomes ours.
static bool cluster_claim_session(LPCSTR login, xr_string& error)
{
	const xr_string key = cluster_login_key(login);
	if (s_cluster_ownership.find(key) != s_cluster_ownership.end())
	{
		error = "This account is still owned by this location server";
		return false;
	}
	string_path ownership_path; cluster_file("ownership", login, -1, ownership_path);
	const HANDLE ownership = CreateFileA(ownership_path, GENERIC_READ | GENERIC_WRITE, 0, nullptr,
		OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (ownership == INVALID_HANDLE_VALUE)
	{
		error = "This account is still owned by another location server, or its ownership file is unavailable";
		return false;
	}
	u32 port = 0, stamp = 0;
	const u32 now = cluster_now();
	if (cluster_lease_holder(login, port, stamp) && port != cluster_port() && u64(now) < u64(stamp) + cluster_lease_ttl_s)
	{
		string256 text;
		xr_sprintf(text, "This character is still on another location server; try again after its lease expires");
		error = text;
		CloseHandle(ownership);
		return false;
	}
	s_cluster_ownership[key] = ownership;
	if (!cluster_lease_write(login))
	{
		CloseHandle(ownership);
		s_cluster_ownership.erase(key);
		error = "Cannot commit account ownership; try again after storage is available";
		return false;
	}
	return true;
}

// ---- transfer ticket -------------------------------------------------------

static bool cluster_ticket_write(LPCSTR login, u8 slot, LPCSTR level)
{
	if (!cluster_secret()) return false;
	u8 nonce[16];
	if (!random_bytes(nonce, sizeof(nonce))) return false;
	xr_string lower = login; to_lower(lower);
	string512 body;
	xr_sprintf(body, "v1|%s|%u|%s|%u|%u|%s", lower.c_str(), slot, level, cluster_port(), cluster_now() + cluster_ticket_ttl_s,
		to_hex(nonce, sizeof(nonce)).c_str());
	xr_string signature;
	if (!hmac_sha256_hex(s_cluster_secret, body, signature)) return false;
	string_path path; cluster_file("ticket", login, slot, path);
	return cluster_write_line(path, (xr_string(body) + "|" + signature).c_str());
}

// Consumes the ticket (single use). Returns true for a valid ticket to this
// map; a forged, expired or foreign ticket is deleted and ignored.
static bool cluster_ticket_take(LPCSTR login, u8 slot, LPCSTR level, u32& source_port)
{
	string_path path; cluster_file("ticket", login, slot, path);
	xr_string line;
	if (!cluster_read_line(path, line)) return false;
	DeleteFileA(path);
	const size_t bar = line.rfind('|');
	if (bar == xr_string::npos || !cluster_secret()) return false;
	const xr_string body = line.substr(0, bar), signature = line.substr(bar + 1);
	xr_string expected;
	if (!hmac_sha256_hex(s_cluster_secret, body, expected) || !constant_time_equal(expected, signature)) return false;
	char version[8] = {}, who[64] = {}, target[64] = {};
	u32 ticket_slot = 0, expires = 0;
	if (sscanf(body.c_str(), "%7[^|]|%63[^|]|%u|%63[^|]|%u|%u|", version, who, &ticket_slot, target, &source_port, &expires) != 6)
		return false;
	xr_string lower = login; to_lower(lower);
	return !xr_strcmp(version, "v1") && lower == who && ticket_slot == slot && !xr_strcmp(target, level) && cluster_now() <= expires;
}

static LPCSTR cluster_current_level()
{
	if (!ai().get_game_graph() || !ai().get_level_graph()) return "";
	return *ai().game_graph().header().level(ai().level_graph().level_id()).name();
}

bool server_task_here(const char* origin)
{
	return !enabled() || !origin || !origin[0] || !xr_strcmp(origin, cluster_current_level());
}

static xr_set<xr_string> s_cancelled_foreign_tasks;

void server_task_check_target(const char* task_id, unsigned short object_id)
{
	if (!enabled() || pure_client() || !task_id || object_id == u16(-1) || !ai().get_alife() || !ai().get_game_graph()) return;
	CSE_ALifeObject* target = smart_cast<CSE_ALifeObject*>(ai().alife().objects().object(object_id, true));
	if (!target || target->m_story_id != INVALID_STORY_ID || !ai().game_graph().valid_vertex_id(target->m_tGraphID)) return;
	const LPCSTR level = *ai().game_graph().header().level(ai().game_graph().vertex(target->m_tGraphID)->level_id()).name();
	if (!xr_strcmp(level, cluster_current_level())) return;
	if (!s_cancelled_foreign_tasks.insert(task_id).second) return;
	::luabind::functor<bool> cancel;
	bool done = false;
	if (ai().script_engine().functor("netcoop_server_compat.cancel_task_on_other_map", cancel))
		try { done = cancel(task_id, level); } catch (...) {}
	Msg("[Lost Zone][tasks] %s: target %u is on %s, task %s", task_id, object_id, level, done ? "cancelled" : "left as is");
	if (!done) return;
	s_cancelled_foreign_tasks.erase(task_id); // the same id may be given again later
}

// ---- NPC transit records (netcoop_transit.script) -------------------------

LPCSTR script_cluster_maps()
{
	static xr_string maps;
	maps.clear();
	string_path path;
	FS.update_path(path, "$app_data_root$", "netcoop_cluster.ltx");
	if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) return "";
	CInifile ini(path, TRUE, TRUE, FALSE);
	if (!ini.section_exist("locations")) return "";
	CInifile::Sect& section = ini.r_section("locations");
	for (const auto& item : section.Data)
	{
		xr_string host; u32 port = 0;
		if (!cluster_location(*item.first, host, port) || port == cluster_port()) continue;
		if (!maps.empty()) maps += " ";
		maps += *item.first;
	}
	return maps.c_str();
}

static bool cluster_name_valid(LPCSTR name)
{
	if (!name || !name[0] || xr_strlen(name) > 63) return false;
	for (const char* c = name; *c; ++c)
		if (!isalnum((unsigned char)*c) && *c != '_') return false;
	return true;
}

#include "netcoop_transit_queue.inc"

// ---- server: login and leaving ---------------------------------------------

// finish_auth, after the password: the cluster lease, the ticket and a fresh
// character from disk (another server may have changed the file).
static bool cluster_on_login(xrClientData* CL, LPCSTR login, u8 slot, xr_string& error)
{
	if (!cluster_claim_session(login, error)) return false;
	character_commits_flush();
	xr_string prefix = login; to_lower(prefix); prefix += ":";
	for (auto it = s_characters.begin(); it != s_characters.end();)
		if (it->first.compare(0, prefix.size(), prefix) == 0) it = s_characters.erase(it); else ++it;
	u32 source = 0;
	if (slot && cluster_ticket_take(login, slot, cluster_current_level(), source))
		Msg("[Lost Zone][cluster] %s slot %u arrived from the server on port %u", login, slot, source);
	return true;
}

// A character saved on another map of the cluster plays there: the entry
// server sends the client on instead of moving the character to its own map.
static bool cluster_route(xrServer* server, LPCSTR login, u8 slot, xr_string& redirect)
{
	Character* character = slot ? character_load(login, slot) : nullptr;
	if (!character || !character->initialized || character->respawn || !character->actor.B.count) return false;
	CSE_Abstract* entity = server->game->spawn_begin("actor");
	if (!entity) return false;
	NET_Packet packet = character->actor;
	u32 vertex = u32(-1);
	if (entity->Spawn_Read(packet))
		if (CSE_ALifeCreatureActor* actor = smart_cast<CSE_ALifeCreatureActor*>(entity)) vertex = actor->m_tGraphID;
	F_entity_Destroy(entity);
	if (!ai().get_game_graph() || !ai().game_graph().valid_vertex_id(vertex)) return false;
	const LPCSTR level = *ai().game_graph().header().level(ai().game_graph().vertex(vertex)->level_id()).name();
	if (!xr_strcmp(level, cluster_current_level())) return false;
	xr_string host; u32 port = 0;
	if (!cluster_location(level, host, port) || port == cluster_port()) return false;
	// Its map's server is down or full: play here (the arrival point of this map).
	if (cluster_target_problem(port)[0])
	{
		Msg("[Lost Zone][cluster] %s stays here: %s (%s)", login, cluster_target_problem(port), level);
		return false;
	}
	string256 text;
	xr_sprintf(text, "redirect|%s|%u|%s", host.c_str(), port, level);
	redirect = text;
	return true;
}

// The redirected client disconnects by itself when it starts the new
// connection; a kick right away would reach it as a "kicked" dialog.
static void cluster_send_redirect(xrServer* server, xrClientData* CL, LPCSTR redirect)
{
	Msg("[Lost Zone][cluster] %s is sent to %s", CL->netcoop_login.size() ? CL->netcoop_login.c_str() : "?", redirect);
	send_auth_result(server, CL, false, role_none, redirect);
	s_cluster_redirected[CL->ID.value()] = real_time_ms();
}

bool server_client_leaving(xrClientData* CL)
{
	if (!CL) return false;
	if (!s_cluster_redirected.empty() && s_cluster_redirected.find(CL->ID.value()) != s_cluster_redirected.end()) return true;
	return !s_cluster_leaving.empty() && s_cluster_leaving.find(CL->ID.value()) != s_cluster_leaving.end();
}

static bool cluster_actor_leaving(u16 actor_id)
{
	for (const auto& entry : s_cluster_leaving)
		if (entry.second.actor == actor_id) return true;
	return false;
}

static void cluster_refuse(xrServer* server, xrClientData* CL, LPCSTR text)
{
	Msg("[Lost Zone][cluster] %s: %s", CL->netcoop_login.c_str(), text);
	if (CL->owner) script_send_to_actor(CL->owner->ID, "netcoop_transfer_refused", text);
}

static bool cluster_move(xrServer* server, xrClientData* CL, CLevelChanger* changer);


// M_CHANGE_LEVEL from a remote player: the level changer dialog's "go".
void server_on_change_level(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!CL || !CL->owner || !CL->netcoop_login.size() || server_client_leaving(CL)) return;
	if (P.r_elapsed() < sizeof(GameGraph::_GRAPH_ID) + sizeof(u32)) return;
	GameGraph::_GRAPH_ID game_vertex;
	u32 level_vertex;
	P.r(&game_vertex, sizeof(game_vertex));
	P.r(&level_vertex, sizeof(level_vertex));
	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	if (!actor || !actor->g_Alive()) return;
	// The client names the changer; position and destination come from the
	// server's own copy of it.
	CLevelChanger* changer = nullptr;
	for (CLevelChanger* candidate : g_lchangers)
	{
		if (candidate->next_game_vertex() != game_vertex || candidate->next_level_vertex() != level_vertex) continue;
		Fvector center; candidate->Center(center);
		if (actor->Position().distance_to(center) <= candidate->Radius() + 10.f) { changer = candidate; break; }
	}
	if (!changer) return cluster_refuse(server, CL, "not inside this level changer");
	cluster_move(server, CL, changer);
}

// The player goes through the changer to the server of its target map.
static bool cluster_move(xrServer* server, xrClientData* CL, CLevelChanger* changer)
{
	if (!changer->IsLevelChangerEnabled()) return cluster_refuse(server, CL, "this passage is closed"), false;
	const GameGraph::_GRAPH_ID game_vertex = changer->next_game_vertex();
	const u32 level_vertex = changer->next_level_vertex();
	if (!ai().game_graph().valid_vertex_id(game_vertex)) return false;
	const GameGraph::CVertex* vertex = ai().game_graph().vertex(game_vertex);
	const LPCSTR level = *ai().game_graph().header().level(vertex->level_id()).name();
	if (!xr_strcmp(level, cluster_current_level())) return cluster_refuse(server, CL, "the passage leads to this map"), false;
	xr_string host; u32 port = 0;
	if (!cluster_location(level, host, port))
		return cluster_refuse(server, CL, "no server runs that map yet"), false;
	if (port == cluster_port()) return cluster_refuse(server, CL, "cluster config points the map at this server"), false;
	if (LPCSTR problem = cluster_target_problem(port))
		if (problem[0]) return cluster_refuse(server, CL, problem), false;
	const u16 actor_id = CL->owner->ID;
	if (s_character_restore.find(actor_id) != s_character_restore.end())
		return cluster_refuse(server, CL, "the character is still loading"), false;

	// Prepare the ticket before changing the authoritative character file.
	// A ticket write failure must leave the player and saved destination here.
	if (!cluster_ticket_write(CL->netcoop_login.c_str(), CL->netcoop_character_slot, level))
		return cluster_refuse(server, CL, "the transfer ticket could not be saved"), false;

	// Capture the wallet before freezing. Disconnect/periodic saves of a
	// frozen source must never overwrite money already spent at the target.
	store_money(CL);
	if (!accounts_save())
	{
		string_path ticket;
		cluster_file("ticket", CL->netcoop_login.c_str(), CL->netcoop_character_slot, ticket);
		DeleteFileA(ticket);
		return cluster_refuse(server, CL, "the account wallet could not be saved"), false;
	}
	// The frozen player sends nothing more that the server would apply.
	ClusterLeaving& leaving = s_cluster_leaving[CL->ID.value()];
	leaving.actor = actor_id; leaving.since = real_time_ms(); leaving.level = level;
	CharacterDestination destination;
	destination.game_vertex = game_vertex; destination.level_vertex = level_vertex;
	destination.position = changer->next_position(); destination.angles = changer->next_angles();
	if (!character_save_actor(actor_id, &destination))
	{
		string_path ticket;
		cluster_file("ticket", CL->netcoop_login.c_str(), CL->netcoop_character_slot, ticket);
		DeleteFileA(ticket); // prepared ticket has no committed destination
		s_cluster_leaving.erase(CL->ID.value());
		return cluster_refuse(server, CL, "the character could not be saved"), false;
	}
	// From here on this server never saves the character again.
	s_actor_character.erase(actor_id);
	cluster_lease_release(CL->netcoop_login.c_str());
	string256 data;
	xr_sprintf(data, "%s|%u|%s", host.c_str(), port, level);
	script_send_to_actor(actor_id, "netcoop_transfer", data);
	Msg("[Lost Zone][cluster] %s leaves for %s (%s:%u)", CL->netcoop_login.c_str(), level, host.c_str(), port);
	return true;
}

// -netcoop_cluster_selftest: headless bots (nbot_*) go through the first
// open changer to another cluster map 20 s after they appear, again and
// again: a soak test of the whole handoff with real servers and clients.
static bool cluster_selftest() { return strstr(Core.Params, "-netcoop_cluster_selftest") != nullptr; }
static xr_map<u16, u32> s_selftest_seen; // bot Actor -> first seen

struct ClusterSelftest
{
	xr_vector<std::pair<xrClientData*, CLevelChanger*>>* out;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (!CL || CL->flags.bLocal || !CL->owner || !CL->netcoop_login.size() || strncmp(CL->netcoop_login.c_str(), "nbot_", 5) ||
			server_client_leaving(CL)) return;
		const u32 now = real_time_ms();
		auto seen = s_selftest_seen.find(CL->owner->ID);
		if (seen == s_selftest_seen.end()) { s_selftest_seen[CL->owner->ID] = now; return; }
		if (now - seen->second < 20000) return;
		seen->second = now; // one attempt per 20 s
		for (CLevelChanger* changer : g_lchangers)
		{
			if (!changer->IsLevelChangerEnabled() || !ai().game_graph().valid_vertex_id(changer->next_game_vertex())) continue;
			const LPCSTR level = *ai().game_graph().header().level(ai().game_graph().vertex(changer->next_game_vertex())->level_id()).name();
			xr_string host; u32 port = 0;
			if (xr_strcmp(level, cluster_current_level()) && cluster_location(level, host, port) && port != cluster_port())
			{
				out->push_back(std::make_pair(CL, changer));
				return;
			}
		}
	}
};

struct ClusterDisconnectLeaving
{
	xr_vector<xrClientData*>* out;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		auto it = s_cluster_leaving.find(CL->ID.value());
		if (it != s_cluster_leaving.end() && real_time_ms() - it->second.since >= cluster_leave_ms)
		{
			it->second.since = real_time_ms(); // once more later if it is still here
			out->push_back(CL);
		}
		auto sent = s_cluster_redirected.find(CL->ID.value());
		if (sent != s_cluster_redirected.end() && real_time_ms() - sent->second >= cluster_leave_ms)
		{
			s_cluster_redirected.erase(sent);
			out->push_back(CL);
		}
	}
};

struct ClusterHeartbeat
{
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (CL && !CL->flags.bLocal && CL->owner && CL->netcoop_login.size() && !server_client_leaving(CL))
			cluster_lease_write(CL->netcoop_login.c_str());
	}
};

// ---- one calendar for the cluster ----------------------------------------
// Every server publishes its game time; each one follows the most advanced.
// A server that is behind (it was restarted, or its map was down) runs its
// clock faster until it has caught up: the world clock forbids jumps, and a
// faster clock keeps ALife, weather and events continuous. No server is ever
// slowed down, so the cluster time only moves forward.
static u32 s_cluster_clock_check = 0;
static float s_cluster_clock_factor = 0.f;

static u64 cluster_unix_ms()
{
	FILETIME ft; GetSystemTimeAsFileTime(&ft);
	const u64 ticks = (u64(ft.dwHighDateTime) << 32) | ft.dwLowDateTime;
	return ticks / 10000 - 11644473600000ull;
}

static void cluster_clock_update()
{
	if (!ai().get_alife()) return;
	string_path config;
	FS.update_path(config, "$app_data_root$", "netcoop_cluster.ltx");
	if (GetFileAttributesA(config) == INVALID_FILE_ATTRIBUTES) return; // single server
	CALifeTimeManager& time = const_cast<CALifeSimulator*>(ai().get_alife())->time_manager();
	const float normal = time.normal_time_factor();
	if (!(normal > 0.f)) return;
	const u64 now = cluster_unix_ms(), own = time.game_time();
	string_path dir, file; cluster_dir(dir);
	xr_sprintf(file, "%sclock_%u.txt", dir, cluster_port());
	string128 line; xr_sprintf(line, "%llu %llu %f", now, own, normal);
	cluster_write_line(file, line);
	// The most advanced fresh clock, projected to this moment.
	double target = double(own);
	string_path mask; xr_sprintf(mask, "%sclock_*.txt", dir);
	WIN32_FIND_DATAA found;
	HANDLE search = FindFirstFileA(mask, &found);
	if (search != INVALID_HANDLE_VALUE)
	{
		do
		{
			string_path path; xr_sprintf(path, "%s%s", dir, found.cFileName);
			xr_string text; unsigned long long stamp = 0, game = 0; float factor = 0.f;
			if (!cluster_read_line(path, text) || sscanf(text.c_str(), "%llu %llu %f", &stamp, &game, &factor) != 3) continue;
			if (stamp > now || now - stamp > 30000 || !(factor > 0.f) || factor > 1000.f) continue;
			target = _max(target, double(game) + double(now - stamp) * factor);
		} while (FindNextFileA(search, &found));
		FindClose(search);
	}
	// Behind by more than 2 game seconds: catch up within about a real
	// minute, at most four times the normal speed.
	const double behind = target - double(own);
	float factor = normal;
	if (behind > 2000.0) factor = normal + float(_min(behind / 60000.0, double(normal) * 3.0));
	if (_abs(factor - s_cluster_clock_factor) > normal * 0.01f)
	{
		if (factor != normal || s_cluster_clock_factor != 0.f)
			Msg("[Lost Zone][cluster] calendar %.0f s behind the cluster: time factor %.2f", behind / 1000.0, factor);
		time.set_time_factor(factor);
		s_cluster_clock_factor = factor;
	}
}

// server_frame_update: leases of everyone here every 10 s; players that got
// their redirect are disconnected after a short grace for the message.
static void cluster_update(xrServer* server)
{
	const u32 now = real_time_ms();
	if (now - s_cluster_clock_check >= 5000)
	{
		s_cluster_clock_check = now;
		cluster_clock_update();
	}
	if (now - s_cluster_heartbeat >= 10000)
	{
		s_cluster_heartbeat = now;
		if (cluster_config_present()) cluster_status_write(server);
		ClusterHeartbeat heartbeat;
		server->ForEachClientDo(heartbeat);
	}
	if (cluster_selftest())
	{
		xr_vector<std::pair<xrClientData*, CLevelChanger*>> moves;
		ClusterSelftest test = {&moves};
		server->ForEachClientDo(test);
		for (const auto& move : moves) cluster_move(server, move.first, move.second);
	}
	if (s_cluster_leaving.empty() && s_cluster_redirected.empty()) return;
	for (auto it = s_cluster_redirected.begin(); it != s_cluster_redirected.end();)
		if (now - it->second > 60000) it = s_cluster_redirected.erase(it); else ++it; // gone already
	xr_vector<xrClientData*> gone;
	ClusterDisconnectLeaving disconnect = {&gone};
	server->ForEachClientDo(disconnect); // the client list is not changed while it is walked
	for (xrClientData* CL : gone) server->DisconnectClient(CL, "@Moved to another location");
}

// ---- client ----------------------------------------------------------------

// "host|port|level" from the source server: reconnect with the same account
// and character. "start" disconnects the current level first.
static void client_cluster_transfer(LPCSTR data)
{
	char host[128] = {}, level[64] = {};
	u32 port = 0;
	if (sscanf(data, "%127[^|]|%u|%63s", host, &port, level) != 3 || !port || port > 65535) return;
	for (const char* c = host; *c; ++c)
		if (!isalnum((unsigned char)*c) && *c != '.' && *c != '-' && *c != '_') return;
	xr_string name = client_login();
	if (name.empty() || !login_valid(name.c_str())) name = "player";
	Msg("[Lost Zone][cluster] moving to %s at %s:%u", level, host, port);
	string512 command;
	xr_sprintf(command, "start client(%s/name=%s/port=%u)", host, name.c_str(), port);
	Console->Execute(command);
}
