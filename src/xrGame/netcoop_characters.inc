// Included inside namespace netcoop in netcoop.cpp. Accounts authenticate a
// connection; character slots own gameplay state. No client-supplied saves.
struct Character
{
	xr_string account, name, faction, loadout;
	u8 slot = 1, economy = 1;
	bool initialized = false, respawn = false;
	u32 last_save = 0;
	NET_Packet actor;
	struct Item { xr_string section; u16 parent; NET_Packet spawn; };
	xr_vector<Item> items;
};
static xr_map<xr_string, Character> s_characters;
static xr_map<u16, xr_string> s_actor_character;


static xr_string character_key(LPCSTR account, u8 slot)
{
	xr_string key = account;
	to_lower(key);
	key += ":";
	key += char('0' + slot);
	return key;
}

static void character_path(LPCSTR account, u8 slot, string_path& path)
{
	xr_string login = account;
	to_lower(login);
	string128 file;
	xr_sprintf(file, "netcoop_character_%s_%u.bin", login.c_str(), slot);
	FS.update_path(path, "$app_data_root$", file);
}

static bool character_name_valid(LPCSTR name)
{
	if (!name || !name[0] || xr_strlen(name) > 63) return false;
	for (const unsigned char* c = (const unsigned char*)name; *c; ++c)
		if (*c < 32 || *c == '|') return false;
	return true;
}

bool script_character(int slot, LPCSTR name, LPCSTR faction, int economy, LPCSTR loadout)
{
	if (slot < 1 || slot > 5 || !name || !faction || !loadout || xr_strlen(loadout) > 4096) return false;
	s_client_character_slot = u8(slot);
	s_client_character_name = name;
	s_client_character_faction = faction;
	s_client_character_economy = u8(economy);
	s_client_character_loadout = loadout;
	return true;
}

static bool character_read_string(FILE* f, xr_string& value, u32 max_size)
{
	value.clear();
	for (u32 n = 0; n <= max_size; ++n)
	{
		const int c = fgetc(f);
		if (c == EOF) return false;
		if (!c) return true;
		value += char(c);
	}
	return false;
}

static bool character_read_packet(FILE* f, NET_Packet& packet)
{
	u32 size, crc;
	if (fread(&size, 4, 1, f) != 1 || fread(&crc, 4, 1, f) != 1 || size > sizeof(packet.B.data)) return false;
	packet.B.count = size;
	packet.r_pos = 0;
	return (!size || fread(packet.B.data, 1, size, f) == size) && crc32(packet.B.data, size) == crc;
}

static void character_write_packet(FILE* f, const NET_Packet& packet)
{
	const u32 size = packet.B.count, crc = crc32(packet.B.data, size);
	fwrite(&size, 4, 1, f); fwrite(&crc, 4, 1, f);
	if (size) fwrite(packet.B.data, 1, size, f);
}

static bool character_save(Character& character)
{
	string_path path, temp;
	character_path(character.account.c_str(), character.slot, path);
	xr_sprintf(temp, "%s.tmp", path);
	FILE* f = fopen(temp, "wb");
	if (!f) return false;
	const u32 magic = 0x3348434e; // NCH3
	fwrite(&magic, 4, 1, f);
	fwrite(character.name.c_str(), 1, character.name.size() + 1, f);
	fwrite(character.faction.c_str(), 1, character.faction.size() + 1, f);
	fwrite(character.loadout.c_str(), 1, character.loadout.size() + 1, f);
	fputc(character.economy, f); fputc(character.initialized ? 1 : 0, f); fputc(character.respawn ? 1 : 0, f);
	character_write_packet(f, character.actor);
	const u32 count = u32(character.items.size());
	fwrite(&count, 4, 1, f);
	for (const Character::Item& item : character.items)
	{
		fwrite(item.section.c_str(), 1, item.section.size() + 1, f);
		fwrite(&item.parent, 2, 1, f);
		character_write_packet(f, item.spawn);
	}
	const bool ok = !ferror(f);
	const bool closed = fclose(f) == 0;
	if (!ok || !closed || !MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) return false;
	character.last_save = real_time_ms();
	return true;
}

static Character* character_load(LPCSTR account, u8 slot)
{
	const xr_string key = character_key(account, slot);
	auto cached = s_characters.find(key);
	if (cached != s_characters.end()) return &cached->second;
	string_path path;
	character_path(account, slot, path);
	FILE* f = fopen(path, "rb");
	if (!f) return nullptr;
	Character character;
	character.account = account; character.slot = slot;
	u32 magic = 0, count = 0;
	bool ok = fread(&magic, 4, 1, f) == 1 && magic == 0x3348434e &&
		character_read_string(f, character.name, 63) && character_read_string(f, character.faction, 32) &&
		character_read_string(f, character.loadout, 4096);
	if (ok)
	{
		character.economy = u8(fgetc(f));
		const int initialized = fgetc(f), respawn = fgetc(f);
		character.initialized = initialized == 1; character.respawn = respawn == 1;
		if (initialized < 0 || initialized > 1 || respawn < 0 || respawn > 1) { fclose(f); return nullptr; }
		ok = character_read_packet(f, character.actor) && fread(&count, 4, 1, f) == 1 && count <= 512;
	}
	for (u32 i = 0; ok && i < count; ++i)
	{
		Character::Item item;
		ok = character_read_string(f, item.section, 128) && fread(&item.parent, 2, 1, f) == 1 &&
			item.parent <= i && character_read_packet(f, item.spawn) && pSettings->section_exist(item.section.c_str());
		if (ok) character.items.push_back(std::move(item));
	}
	fclose(f);
	if (!ok || !character_name_valid(character.name.c_str()))
	{
		Msg("! [NetAnomaly] cannot read character slot %u for %s", slot, account);
		return nullptr;
	}
	s_characters[key] = std::move(character);
	return &s_characters[key];
}

static bool character_validate_loadout(LPCSTR faction, u8 economy, LPCSTR loadout)
{
	if (economy < 1 || economy > 3 || xr_strlen(faction) > 20 || xr_strlen(loadout) > 4096) return false;
	string_path path;
	if (!FS.exist(path, "$game_config$", "items\\settings\\new_game_loadouts.ltx")) return false;
	CInifile ini(path, TRUE, TRUE, FALSE);
	xr_string section = faction; section += "_loadout";
	if (!ini.section_exist(section.c_str())) return false;
	string64 budget_key;
	xr_sprintf(budget_key, "total_points_eco_%u", economy);
	const float budget = ini.r_float("points", budget_key);
	float used = 0.f;
	xr_map<xr_string, u32> selected;
	const u32 count = _GetItemCount(loadout);
	if (count > 256) return false;
	for (u32 i = 0; loadout[0] && i < count; ++i)
	{
		string128 item, field;
		_GetItem(loadout, i, item);
		_Trim(item);
		if (!pSettings->section_exist(item) || !ini.line_exist(section.c_str(), item)) return false;
		LPCSTR values = ini.r_string(section.c_str(), item);
		_GetItem(values, 1, field); const u32 available = u32(atoi(field));
		_GetItem(values, 2, field); const float price = float(atof(field));
		if (++selected[item] > available || !_valid(price) || price < 0.f) return false;
		if (_GetItemCount(values) >= 4)
		{
			_GetItem(values, 3, field);
			if (economy > atoi(field)) return false;
		}
		used += price;
		if (used > budget) return false;
	}
	return true;
}

static bool character_select(xrClientData* CL, u8 slot, LPCSTR name, LPCSTR faction, u8 economy, LPCSTR loadout)
{
	if (slot < 1 || slot > 5) return false;
	Character* character = character_load(CL->netcoop_login.c_str(), slot);
	if (!character)
	{
		// A damaged save must never be silently replaced by a fresh character.
		string_path path; character_path(CL->netcoop_login.c_str(), slot, path);
		if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) return false;
		if (!character_name_valid(name) || !character_validate_loadout(faction, economy, loadout)) return false;
		Character created;
		created.account = CL->netcoop_login.c_str(); created.slot = slot;
		created.name = name; created.faction = faction; created.economy = economy; created.loadout = loadout;
		created.actor.B.count = 0;
		if (!character_save(created)) return false;
		const xr_string key = character_key(created.account.c_str(), slot);
		s_characters[key] = std::move(created);
		character = &s_characters[key];
	}
	CL->netcoop_character_slot = slot;
	CL->netcoop_character_name = character->name.c_str();
	return true;
}

bool server_character_load_actor(xrClientData* CL, CSE_Abstract* actor)
{
	if (!CL || !CL->netcoop_login.size()) return false;
	Character* character = character_load(CL->netcoop_login.c_str(), CL->netcoop_character_slot);
	if (!character) return false;
	if (character->initialized && character->actor.B.count)
	{
		NET_Packet packet = character->actor;
		if (!actor->Spawn_Read(packet)) return false;
		actor->ID = actor->ID_Parent = actor->ID_Phantom = 0xffff;
		actor->m_bALifeControl = false;
		if (CSE_PHSkeleton* skeleton = smart_cast<CSE_PHSkeleton*>(actor)) skeleton->_flags.zero();
		if (CSE_ALifeCreatureActor* creature = smart_cast<CSE_ALifeCreatureActor*>(actor))
		{ creature->m_holderID = 0xffff; creature->m_bOnline = true; }
	}
	CSE_ALifeTraderAbstract* trader = smart_cast<CSE_ALifeTraderAbstract*>(actor);
	if (trader)
	{
		trader->m_character_name = character->name;
		trader->m_character_name_str = character->name;
		if (!character->initialized) trader->set_character_profile(shared_str((xr_string("actor_") + character->faction).c_str()));
	}
	CSE_ALifeCreatureActor* creature = smart_cast<CSE_ALifeCreatureActor*>(actor);
	// Saves from another server map retain inventory and progress, but use
	// that map's arrival point rather than coordinates in a different world.
	const bool same_level = creature && ai().valid_game_vertex(creature->m_tGraphID) &&
		ai().valid_game_vertex(ai().game_graph().current_level_vertex()) &&
		ai().game_graph().vertex(creature->m_tGraphID)->level_id() ==
		ai().game_graph().vertex(ai().game_graph().current_level_vertex())->level_id();
	return character->initialized && !character->respawn && same_level &&
		ai().get_level_graph() && ai().level_graph().valid_vertex_id(creature->m_tNodeID) && _valid(creature->o_Position);
}

void server_character_spawn_items(xrClientData* CL)
{
	if (!CL || !CL->owner || !CL->netcoop_login.size()) return;
	Character* character = character_load(CL->netcoop_login.c_str(), CL->netcoop_character_slot);
	if (!character) return;
	s_actor_character[CL->owner->ID] = character_key(character->account.c_str(), character->slot);
	xrServer* server = Level().Server;
	xr_vector<u16> parents; parents.push_back(CL->owner->ID);
	if (character->initialized)
	{
		for (const Character::Item& saved : character->items)
		{
			CSE_Abstract* item = server->game->spawn_begin(saved.section.c_str());
			NET_Packet packet = saved.spawn;
			if (!item->Spawn_Read(packet)) { F_entity_Destroy(item); return; }
			item->ID = item->ID_Phantom = 0xffff;
			item->ID_Parent = parents[saved.parent];
			item->s_flags.assign(M_SPAWN_OBJECT_LOCAL);
			CSE_Abstract* spawned = server->game->spawn_end(item, CL->ID);
			if (!spawned) return;
			parents.push_back(spawned->ID);
		}
	}
	else
	{
		const u32 count = _GetItemCount(character->loadout.c_str());
		for (u32 i = 0; character->loadout.size() && i < count; ++i)
		{
			string128 section; _GetItem(character->loadout.c_str(), i, section); _Trim(section);
			CSE_Abstract* item = server->game->spawn_begin(section);
			item->ID_Parent = CL->owner->ID;
			item->s_flags.assign(M_SPAWN_OBJECT_LOCAL);
			server->game->spawn_end(item, CL->ID);
		}
		// Match freeplay's ammunition allowance for each selected firearm.
        string_path path;
        if (FS.exist(path, "$game_config$", "items\\settings\\new_game_loadouts.ltx"))
        {
            CInifile ini(path, TRUE, TRUE, FALSE);
            for (u32 i = 0; character->loadout.size() && i < count; ++i)
            {
                string128 weapon, ammo; _GetItem(character->loadout.c_str(), i, weapon); _Trim(weapon);
                if (!pSettings->line_exist(weapon, "ammo_class") || !pSettings->line_exist(weapon, "slot")) continue;
                const u32 slot = pSettings->r_u32(weapon, "slot");
                if (slot != 1 && slot != 2 && !(slot == 0 && pSettings->line_exist(weapon, "animation_slot") && pSettings->r_u32(weapon, "animation_slot") == 1)) continue;
                _GetItem(pSettings->r_string(weapon, "ammo_class"), 0, ammo); _Trim(ammo);
                if (ini.line_exist("ammo_type_per_wpn", weapon)) xr_strcpy(ammo, ini.r_string("ammo_type_per_wpn", weapon));
                if (!pSettings->section_exist(ammo)) continue;
                const u32 box = pSettings->line_exist(ammo, "box_size") ? pSettings->r_u32(ammo, "box_size") : 50;
                u32 remaining = ini.line_exist("ammo_count", ammo) ? ini.r_u32("ammo_count", ammo) : (box < 30 ? box * 2 : box);
                while (remaining && box)
                {
                    CSE_Abstract* item = server->game->spawn_begin(ammo);
                    CSE_ALifeItemAmmo* bullets = smart_cast<CSE_ALifeItemAmmo*>(item);
                    if (!bullets) { F_entity_Destroy(item); break; }
                    bullets->a_elapsed = u16(_min(remaining, box)); remaining -= bullets->a_elapsed;
                    item->ID_Parent = CL->owner->ID; item->s_flags.assign(M_SPAWN_OBJECT_LOCAL);
                    server->game->spawn_end(item, CL->ID);
                }
            }
        }
        character->initialized = true;
	}
	Msg("[NetAnomaly] character '%s' slot %u loaded for %s", character->name.c_str(), character->slot, character->account.c_str());
}

static void character_capture_items(xrServer* server, Character& character, CSE_Abstract* parent, u16 parent_index, u32 depth)
{
	if (depth > 8) return;
	for (u16 id : parent->children)
	{
		CSE_Abstract* item = server->game->get_entity_from_eid(id);
		if (!item || character.items.size() >= 512) continue;
		if (CInventoryItem* runtime = smart_cast<CInventoryItem*>(Level().Objects.net_Find(id)))
		{
			if (CSE_ALifeInventoryItem* saved = smart_cast<CSE_ALifeInventoryItem*>(item))
			{ saved->m_fCondition = runtime->GetCondition(); saved->m_upgrades = runtime->get_upgrades(); }
			if (CWeapon* weapon = smart_cast<CWeapon*>(Level().Objects.net_Find(id)))
				if (CSE_ALifeItemWeapon* saved = smart_cast<CSE_ALifeItemWeapon*>(item))
				{ saved->a_elapsed = u16(weapon->GetAmmoElapsed()); saved->ammo_type = weapon->GetAmmoType(); saved->m_addon_flags.flags = weapon->GetAddonsState(); }
		}
		Character::Item record;
		record.parent = parent_index; record.section = item->s_name.c_str();
		item->Spawn_Write(record.spawn, TRUE);
		character.items.push_back(std::move(record));
		const u16 index = u16(character.items.size());
		character_capture_items(server, character, item, index, depth + 1);
	}
}

void server_character_save_actor(u16 actor_id)
{
	auto key = s_actor_character.find(actor_id);
	if (key == s_actor_character.end() || !g_pGameLevel || !Level().Server) return;
	Character& character = s_characters[key->second];
	xrServer* server = Level().Server;
	CSE_Abstract* actor = server->game->get_entity_from_eid(actor_id);
	CActor* runtime = smart_cast<CActor*>(Level().Objects.net_Find(actor_id));
	CSE_ALifeCreatureActor* entity = smart_cast<CSE_ALifeCreatureActor*>(actor);
	if (!entity || !runtime) return;
	entity->m_dwMoney = runtime->get_money();
	entity->m_rank = runtime->Rank(); entity->m_reputation = runtime->Reputation();
	entity->o_Position = runtime->Position();
	if (ai().valid_game_vertex(runtime->ai_location().game_vertex_id()))
		entity->m_tGraphID = runtime->ai_location().game_vertex_id();
	if (ai().get_level_graph())
		entity->m_tNodeID = ai().level_graph().vertex_id(runtime->Position());
	character.respawn = !runtime->g_Alive();
	character.items.clear();
	if (runtime->g_Alive()) character_capture_items(server, character, actor, 0, 0);
	// A dead character resumes alive; its former inventory stays in the world.
	const float health = entity->get_health();
	entity->set_health(runtime->g_Alive() ? runtime->GetfHealth() : 1.f);
	actor->Spawn_Write(character.actor, TRUE);
	entity->set_health(health);
	character.initialized = true;
	if (!character_save(character)) Msg("! [NetAnomaly] character save failed for %s slot %u", character.account.c_str(), character.slot);
}

static void characters_update(xrServer* server)
{
	struct Save
	{
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (!CL->owner || !CL->netcoop_login.size()) return;
			Character* character = character_load(CL->netcoop_login.c_str(), CL->netcoop_character_slot);
			if (character && real_time_ms() - character->last_save >= 20000) server_character_save_actor(CL->owner->ID);
		}
	} save;
	server->ForEachClientDo(save);
}
