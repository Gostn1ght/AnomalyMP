// Anomalies switched off on the server (owner 2026-10-24, spec 5.2:
// "anomalies sometimes stop doing damage").
//
// GAMMA switches anomalies off and on on the server (dynamic anomalies after
// an emission, field layers, one-shot blowouts). Each switch went to the
// clients connected at that moment (GE_ZONE_STATE_CHANGE); a player who came
// later saw every anomaly switched on: one the server had switched off still
// showed and hurt nobody. Now a client that finished loading gets the list of
// anomalies off on the server, and an anomaly it spawns later takes the state
// the list gave it.
//
// script message "netcoop_zones" server -> one client: "id,id,..." (off)

static xr_map<u32, bool> s_zones_synced; // server: ClientID -> got the list
static xr_set<u16> s_zones_pending; // client: off, not spawned yet

void zones_reset()
{
	s_zones_synced.clear();
	s_zones_pending.clear();
}

static void zones_send(xrServer* server, ClientID id, const xr_string& list)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_SCRIPT);
	P.w_stringZ("netcoop_zones");
	P.w_stringZ(list.c_str());
	server->SendTo(id, P, net_flags(TRUE, TRUE));
}

// Every server frame: a client that finished loading gets the anomalies off.
static void server_zones_update(xrServer* server)
{
	struct Sync
	{
		xrServer* server;
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (CL == server->GetServerClient() || !CL->flags.bConnected || !CL->gamma_snapshot_ready || !CL->owner) return;
			bool& synced = s_zones_synced[CL->ID.value()];
			if (synced) return;
			synced = true;
			xr_string list;
			u32 count = 0;
			for (u32 n = 0; n < Level().Objects.o_count(); ++n)
			{
				CCustomZone* zone = smart_cast<CCustomZone*>(Level().Objects.o_get_by_iterator(n));
				// a campfire's state goes with the campfires (netcoop_campfire.inc)
				if (!zone || zone->getDestroy() || zone->IsEnabled() || smart_cast<CZoneCampfire*>(zone)) continue;
				if (list.size() > 7800)
				{
					zones_send(server, CL->ID, list);
					list.clear();
				}
				if (!list.empty()) list += ",";
				list += make_string("%u", u32(zone->ID())).c_str();
				++count;
			}
			if (!list.empty()) zones_send(server, CL->ID, list);
			if (count) Msg("[Lost Zone][zones] %s: %u anomalies are off here", CL->netcoop_login.c_str(), count);
		}
	} sync = {server};
	server->ForEachClientDo(sync);
}

static void client_on_zones(LPCSTR data)
{
	if (!pure_client() || !data) return;
	for (LPCSTR at = data; *at;)
	{
		char* end = nullptr;
		const unsigned long id = std::strtoul(at, &end, 10);
		if (end == at || id >= 0xffff) return;
		if (CCustomZone* zone = smart_cast<CCustomZone*>(Level().Objects.net_Find(u16(id))))
			zone->netcoop_switch_off();
		else if (s_zones_pending.size() < 8192)
			s_zones_pending.insert(u16(id));
		at = *end == ',' ? end + 1 : end;
	}
}

void client_zone_spawned(CCustomZone* zone)
{
	if (s_zones_pending.erase(zone->ID())) zone->netcoop_switch_off();
}
