// Included in netcoop.cpp (namespace netcoop) - server: trade.
// Split out of netcoop.cpp in the same order (doc 151); see the file list there.

// ---------------------------------------------------------------------------
// server: trade
// ---------------------------------------------------------------------------
// Trade windows the server's own dialogue opened: player Actor -> partner,
// and when (owner 2026-10-18: "Buy" did nothing at the Marsh technician -
// GAMMA's meet condlist keeps native trade off for technicians, single
// player opened the window from the dialogue anyway).
struct DialogTrade { u16 partner; u32 since; };
static xr_map<u16, DialogTrade> s_dialog_trade;

static xr_string prepare_trade(u16 partner_id, bool dialog_trade = false)
{
	if (!enabled() || !g_pGameLevel || !Level().Server) return "Trade state is not ready";
	::luabind::functor<LPCSTR> prepare;
	if (ai().script_engine().functor("netcoop_server_compat.prepare_trade", prepare))
	{
		try
		{
			LPCSTR refusal = prepare(partner_id, dialog_trade);
			return refusal ? refusal : "Trader policy did not return a result";
		}
		catch (...) { Msg("! [Lost Zone] trader %u profile preparation failed", partner_id); }
	}
	return "Trader policy is unavailable";
}

static bool server_trade_item_allowed(u16 partner_id, PIItem item, bool partner_buys)
{
	if (!item || !item->CanTrade()) return false;
	::luabind::functor<bool> allowed;
	if (!ai().script_engine().functor("netcoop_server_compat.trade_item_allowed", allowed)) return false;
	try { return allowed(partner_id, item->object().lua_game_object(), partner_buys); }
	catch (...) { Msg("! [Lost Zone] trader %u item policy failed", partner_id); return false; }
}

static void send_trade_result(xrServer* server, xrClientData* CL, bool ok, LPCSTR message)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_TRADE_RESULT);
	P.w_u8(ok ? 1 : 0);
	P.w_stringZ(message);
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
	if (!ok)
		Msg("! [Lost Zone] trade rejected for '%s': %s", CL->netcoop_login.c_str(), message);
}

struct TradeAnswer { u32 txid; bool ok; xr_string message; };
static xr_map<u32, xr_deque<TradeAnswer>> s_trade_answers; // ClientID -> recent answers
static xr_map<u16, u32> s_trade_locks; // item -> real time until which it is in a deal

void server_on_trade(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || !CL->owner || !g_pGameLevel)
		return;
	if (P.r_elapsed() < 4 + 2 + 1 + 2)
		return;

	// u32 TransactionID first: a repeated request (resend, double click) gets
	// the stored answer and is never executed twice.
	const u32 txid = P.r_u32();
	const u16 partner_id = P.r_u16();
	const u8 direction = P.r_u8();
	const u16 count = P.r_u16();
	xr_deque<TradeAnswer>& answers = s_trade_answers[CL->ID.value()];
	for (const TradeAnswer& answer : answers)
		if (answer.txid == txid)
		{
			Msg("[NetAnomaly][trade] tx=%08x player=%s duplicate request, answered again", txid, CL->netcoop_login.c_str());
			send_trade_result(server, CL, answer.ok, answer.message.c_str());
			return;
		}
	xr_vector<u16> requested;
	u32 total = 0;
	auto finish = [&](bool ok, LPCSTR message)
	{
		TradeAnswer answer; answer.txid = txid; answer.ok = ok; answer.message = message;
		answers.push_back(answer);
		while (answers.size() > 64) answers.pop_front();
		xr_string ids;
		for (u16 id : requested) { string16 one; xr_sprintf(one, ids.empty() ? "%u" : ",%u", id); ids += one; }
		Msg("%s[NetAnomaly][trade] tx=%08x player=%s trader=%u %s items=[%s] price=%u %s%s", ok ? "" : "! ", txid,
			CL->netcoop_login.c_str(), partner_id, direction == trade_actor_sells ? "sell" : "buy", ids.c_str(), total,
			ok ? "ok: " : "failed: ", message);
		send_trade_result(server, CL, ok, message);
	};
	if (count == 0 || count > 256 || P.r_elapsed() != u32(count) * sizeof(u16) || direction > trade_actor_sells)
	{
		finish(false, "Malformed trade request");
		return;
	}

	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	CObject* partner_object = Level().Objects.net_Find(partner_id);
	CInventoryOwner* partner = smart_cast<CInventoryOwner*>(partner_object);
	CEntityAlive* partner_alive = smart_cast<CEntityAlive*>(partner_object);
	if (!actor || !actor->g_Alive() || !partner || !partner_alive || !partner_alive->g_Alive() ||
		smart_cast<CActor*>(partner_object))
	{
		finish(false, "Trader is not available");
		return;
	}
	if (actor->Position().distance_to(partner_object->Position()) > trade_max_distance)
	{
		finish(false, "Trader is too far away");
		return;
	}

	// The partner's CTrade: bBuying == true means the partner buys (actor sells).
	ServerVictimScope trade_actor_scope(actor);
	auto opened = s_dialog_trade.find(actor->ID());
	const bool dialog_trade = opened != s_dialog_trade.end() && opened->second.partner == partner_id &&
		Device.dwTimeGlobal - opened->second.since < 30 * 60 * 1000;
	partner->DisableTrade(); // failed/missing Lua policy cannot reuse a stale grant
	const xr_string trade_refusal = prepare_trade(partner_id, dialog_trade);
	if (!partner->IsTradeEnabled())
	{
		finish(false, trade_refusal.empty() ? "This character does not trade" : trade_refusal.c_str());
		return;
	}
	const bool partner_buys = direction == trade_actor_sells;
	CObject* seller = partner_buys ? static_cast<CObject*>(actor) : partner_object;

	xr_vector<PIItem> items;
	items.reserve(count);
	for (u16 i = 0; i < count; ++i)
	{
		const u16 id = P.r_u16();
		requested.push_back(id);
		PIItem item = smart_cast<PIItem>(Level().Objects.net_Find(id));
		// The lock: an item from a deal still being carried out by its events
		// is not sold again (the runtime parent changes a frame later).
		auto lock = s_trade_locks.find(id);
		if (lock != s_trade_locks.end() && real_time_ms() < lock->second)
		{
			finish(false, "Item is already being traded");
			return;
		}
		CSE_Abstract* entity = server->game->get_entity_from_eid(id);
		if (!item || item->object().H_Parent() != seller || item->object().getDestroy() || !entity || entity->ID_Parent != seller->ID())
		{
			finish(false, "Item is no longer available");
			return;
		}
		if (std::find(items.begin(), items.end(), item) != items.end())
			continue;
		items.push_back(item);
	}

	CTrade* trade = partner->GetTrade();
	if (!trade)
	{
		finish(false, "Trader is not available");
		return;
	}
	trade->StartTradeEx(actor);
	if (!partner_buys)
	{
		// Weight only (no cell limit); the save format holds 512 items.
		xr_vector<u16> incoming;
		for (auto item:items) incoming.push_back(item->object().ID());
		if (!storage_inventory_room(server,CL->owner,incoming))
		{
			trade->StopTrade(); finish(false,"Inventory save limit reached (512 items)"); return;
		}
	}

	for (u32 i = 0; i < items.size(); ++i)
	{
		if (!server_trade_item_allowed(partner_id, items[i], partner_buys))
		{
			trade->StopTrade();
			finish(false, "Item does not meet this trader's conditions");
			return;
		}
		const u32 price = trade->GetItemPrice(items[i], partner_buys);
		if (price == 0)
		{
			trade->StopTrade();
			finish(false, partner_buys ? "Trader does not buy this item"
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
			finish(false, "Trader does not have enough money");
			return;
		}
	}
	else if (actor->get_money() < total)
	{
		trade->StopTrade();
		finish(false, "Not enough money");
		return;
	}

	if (partner_buys)
		trade->OnPerformTrade(0, total);
	else
		trade->OnPerformTrade(total, 0);

	const u32 lock_until = real_time_ms() + 3000;
	if (s_trade_locks.size() > 4096)
		for (auto it = s_trade_locks.begin(); it != s_trade_locks.end();)
			it = real_time_ms() >= it->second ? s_trade_locks.erase(it) : std::next(it);
	for (u32 i = 0; i < items.size(); ++i)
	{
		s_trade_locks[items[i]->object().ID()] = lock_until;
		trade->TransferItem(items[i], partner_buys);
	}

	// TransferItem changes money locally; publish the server result to everyone.
	actor->set_money(actor->get_money(), true);
	partner->set_money(partner->get_money(), true);
	trade->StopTrade();
	for (PIItem item : items) server_item_touch(item->object().ID());

	// Commit at once: money and items live in one character file replaced
	// atomically (it was written every 20 s, so a crash undid recent deals).
	server_character_save_actor(CL->owner->ID);

	string256 message;
	xr_sprintf(message, "%s %u item(s) for %u RU", partner_buys ? "sold" : "bought", (u32)items.size(), total);
	Msg("[Lost Zone] '%s' %s", CL->netcoop_login.c_str(), message);
	finish(true, message);
}
} // namespace netcoop
