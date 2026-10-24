// Campfires (owner's requirement 2026-10-05): none burns at server start;
// NPCs light them through GAMMA's camp logic on the server, players with
// matches by asking the server; every client shows the server's state at once.
//
// Before: GAMMA lit a campfire in Lua wherever it ran. NPC camps lit theirs
// on the server only, a player's matches lit one on that player's client
// only, and nothing was sent anywhere: each client saw its own fires.
//
// M_NETCOOP_CAMPFIRE server -> client: u16 n, n x (u16 id, u8 on)
//                    client -> server: u16 id, u8 on (a player's request)

static const float campfire_reach = 3.5f;
static xr_map<u16, bool> s_campfires; // server: id -> burning
static xr_map<u32, bool> s_campfire_synced; // server: ClientID -> got the full list
static xr_map<u16, bool> s_campfire_pending; // client: state for a campfire not spawned yet
// Fuel (doc 43 L28): a fire a player lit burns this long in game time, then
// goes out by itself; only these fires are looked at (no distant fire tick).
// A fire an NPC lit burns 2-3 game hours too (owner 2026-10-13: no fire burns
// for ever); NPCs light camp fires only in the evening and at night, and not
// again right after one burned out (netcoop_campfires.script on the server).
static const u64 campfire_fuel_ms = 3ull * 60 * 60 * 1000; // 3 game hours
static const u64 campfire_npc_fuel_ms = 2ull * 60 * 60 * 1000; // plus up to 1 game hour
static xr_map<u16, u64> s_campfire_fuel_end; // server: id -> game time it goes out
static u32 s_campfire_fuel_next = 0;

void campfires_reset()
{
	s_campfires.clear();
	s_campfire_synced.clear();
	s_campfire_pending.clear();
	s_campfire_fuel_end.clear();
	s_campfire_fuel_next = 0;
}

static void campfire_send(xrServer* server, xrClientData* only, const xr_vector<std::pair<u16, bool>>& states)
{
	if (states.empty()) return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_CAMPFIRE);
	P.w_u16(u16(states.size()));
	for (const auto& state : states) { P.w_u16(state.first); P.w_u8(state.second ? 1 : 0); }
	struct Send
	{
		xrServer* server; NET_Packet* packet; xrClientData* only;
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (CL == server->GetServerClient() || !CL->flags.bConnected || !CL->gamma_snapshot_ready || !CL->owner) return;
			if (only && CL != only) return;
			server->SendTo(CL->ID, *packet, net_flags(TRUE, TRUE));
		}
	} send = {server, &P, only};
	server->ForEachClientDo(send);
}

void server_campfire_changed(u16 id, bool on)
{
	if (pure_client() || !g_pGameLevel || !Level().Server) return;
	// GAMMA may extinguish a player-lit fire and light its own later.
	// That new NPC fire must not inherit the former player's deadline.
	if (!on) s_campfire_fuel_end.erase(id);
	// Lit by an NPC (a player's request sets its own fuel right after this).
	else if (s_campfire_fuel_end.find(id) == s_campfire_fuel_end.end())
		s_campfire_fuel_end[id] = Level().GetGameTime() + campfire_npc_fuel_ms + u64(::Random.randI(0, 60)) * 60 * 1000;
	auto known = s_campfires.find(id);
	if (known != s_campfires.end() && known->second == on) return;
	s_campfires[id] = on;
	xr_vector<std::pair<u16, bool>> one;
	one.push_back(std::make_pair(id, on));
	campfire_send(Level().Server, nullptr, one);
}

// Every server frame: clients that finished loading get every burning campfire.
static void server_campfires_update(xrServer* server)
{
	struct Sync
	{
		xrServer* server;
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (CL == server->GetServerClient() || !CL->flags.bConnected || !CL->gamma_snapshot_ready || !CL->owner) return;
			bool& synced = s_campfire_synced[CL->ID.value()];
			if (synced) return;
			synced = true;
			xr_vector<std::pair<u16, bool>> burning;
			for (const auto& state : s_campfires)
				if (state.second) burning.push_back(state);
			campfire_send(server, CL, burning);
		}
	} sync = {server};
	server->ForEachClientDo(sync);

	if (s_campfire_fuel_end.empty() || Device.dwTimeGlobal < s_campfire_fuel_next) return;
	s_campfire_fuel_next = Device.dwTimeGlobal + 2000;
	const u64 now = Level().GetGameTime();
	for (auto it = s_campfire_fuel_end.begin(); it != s_campfire_fuel_end.end();)
	{
		CZoneCampfire* campfire = smart_cast<CZoneCampfire*>(Level().Objects.net_Find(it->first));
		if (!campfire || !campfire->is_on()) { it = s_campfire_fuel_end.erase(it); continue; }
		if (now < it->second) { ++it; continue; }
		Msg("[NetAnomaly][campfire] campfire %u burned out", it->first);
		it = s_campfire_fuel_end.erase(it);
		campfire->turn_off_script();
	}
}

// A player asks to light (with matches) or put out a campfire.
void server_on_campfire(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!CL || !CL->owner || P.r_elapsed() != 3) return;
	const u16 id = P.r_u16();
	const u8 requested = P.r_u8();
	if (requested > 1) return;
	const bool on = requested != 0;
	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	CZoneCampfire* campfire = smart_cast<CZoneCampfire*>(Level().Objects.net_Find(id));
	LPCSTR failure = nullptr;
	PIItem matches = nullptr;
	if (!actor || !actor->g_Alive()) failure = "player is dead";
	else if (!campfire) failure = "no campfire";
	else if (actor->Position().distance_to(campfire->Position()) > campfire_reach) failure = "too far";
	else if (on && campfire->is_on()) failure = "already burning";
	else if (!on && !campfire->is_on()) failure = "already out";
	else if (on)
	{
		for (PIItem item : actor->inventory().m_all)
			if (item && (!xr_strcmp(item->object().cNameSect(), "matches") || !xr_strcmp(item->object().cNameSect(), "box_matches")))
			{
				if (item->object().getDestroy()) continue;
				CEatableItem* box = smart_cast<CEatableItem*>(item);
				if (box && box->GetRemainingUses() == 0) continue;
				matches = item;
				break;
			}
		if (!matches) failure = "no matches";
	}
	if (failure)
	{
		Msg("! [NetAnomaly][campfire] player=%s %s campfire %u refused: %s", CL->netcoop_login.c_str(), on ? "light" : "put out", id, failure);
		return;
	}
	if (matches)
	{
		CEatableItem* box = smart_cast<CEatableItem*>(matches);
		if (box && box->GetRemainingUses() > 1)
		{
			box->SetRemainingUses(u8(box->GetRemainingUses() - 1));
			server_item_touch(matches->object().ID());
		}
		else matches->object().DestroyObject();
	}
	if (on)
	{
		campfire->turn_on_script();
		s_campfire_fuel_end[id] = Level().GetGameTime() + campfire_fuel_ms;
	}
	else
	{
		campfire->turn_off_script();
		s_campfire_fuel_end.erase(id);
	}
	Msg("[NetAnomaly][campfire] player=%s %s campfire %u", CL->netcoop_login.c_str(), on ? "lit" : "put out", id);
	// the other players see the hands at the fire (mod_system_lz_nw_gestures.ltx)
	script_broadcast("netcoop_consumption", make_string("%u|255|%s|anim_campfire_ignition", actor->ID(), actor->cName().c_str()).c_str());
}

// ---- client ------------------------------------------------------------------
void client_campfire_request(u16 id, bool on)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_CAMPFIRE);
	P.w_u16(id); P.w_u8(on ? 1 : 0);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_on_campfire(NET_Packet& P)
{
	if (P.r_elapsed() < 2) return;
	const u16 count = P.r_u16();
	if (P.r_elapsed() != u32(count) * 3) return;
	for (u16 i = 0; i < count; ++i)
	{
		const u16 id = P.r_u16();
		const bool on = P.r_u8() != 0;
		if (CZoneCampfire* campfire = smart_cast<CZoneCampfire*>(Level().Objects.net_Find(id))) campfire->netcoop_apply(on);
		else if (s_campfire_pending.size() < 4096) s_campfire_pending[id] = on;
	}
}

void client_campfire_spawned(CZoneCampfire* campfire)
{
	auto pending = s_campfire_pending.find(campfire->ID());
	if (pending == s_campfire_pending.end()) return;
	const bool on = pending->second;
	s_campfire_pending.erase(pending);
	campfire->netcoop_apply(on);
}
