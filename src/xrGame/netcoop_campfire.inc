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
}

// A player asks to light (with matches) or put out a campfire.
void server_on_campfire(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!CL || !CL->owner || P.r_elapsed() != 3) return;
	const u16 id = P.r_u16();
	const bool on = P.r_u8() != 0;
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
	if (on) campfire->turn_on_script();
	else campfire->turn_off_script();
	Msg("[NetAnomaly][campfire] player=%s %s campfire %u", CL->netcoop_login.c_str(), on ? "lit" : "put out", id);
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
