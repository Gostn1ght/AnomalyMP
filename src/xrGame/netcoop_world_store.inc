// W1 (doc 41): the world survives server restarts.
//
// Before: the server always started a new game ("server(all/.../alife/new)"),
// so every restart or crash rebuilt the world from the spawn: dead NPCs came
// back, corpses, dropped items, furniture, stashes and campfires were gone,
// containers were refilled and the world clock started over. Characters
// survived only because they live in their own files.
//
// Now, with -netcoop_world=<name>, the server saves the whole ALife world
// (the engine's own save: time, every entity online and offline, registries,
// GAMMA's script state) every 5 minutes and when the last player leaves, and
// starts from the newest complete save instead of a new game.
// - Two slots, <name>_a and <name>_b, are written in turn; a pointer file
//   <name>.current names the newest complete one and is replaced atomically
//   after the save. A crash while saving leaves the previous world intact.
// - Players are not part of the world: their characters come from their
//   own files. Living player Actors found in a loaded world (they were
//   online when it was saved) are released with everything they carried,
//   before anyone can see them; dead players' bodies stay as corpses.
// - The world clock continues from the saved time (owner's choice pending:
//   whether offline real time should pass; doc 41 section 21).

static const u32 world_save_period_ms = 300000;
static bool s_world_loaded = false;
static bool s_world_cleanup_pending = false;
static u32 s_world_last_save = 0;

static bool world_store_name(string64& out)
{
	out[0] = 0;
	LPCSTR option = strstr(Core.Params, "-netcoop_world=");
	if (!option || !enabled() || pure_client()) return false;
	option += xr_strlen("-netcoop_world=");
	u32 length = 0;
	while (option[length] && option[length] != ' ')
	{
		// Reserve "_a" / "_b" and a terminator. Never silently truncate
		// names: two different worlds must not alias the same save slots.
		if (length + 3 >= sizeof(out)) return false;
		const char c = option[length];
		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_')) return false;
		out[length] = c;
		++length;
	}
	out[length] = 0;
	return length > 0;
}

static void world_store_pointer_path(LPCSTR world, string_path& path)
{
	string128 file;
	xr_sprintf(file, "%s.current", world);
	FS.update_path(path, "$game_saves$", file);
}

static bool world_store_read_pointer(LPCSTR world, string64& save)
{
	save[0] = 0;
	string_path path;
	world_store_pointer_path(world, path);
	FILE* f = fopen(path, "rb");
	if (!f) return false;
	const size_t read = fread(save, 1, sizeof(save) - 1, f);
	fclose(f);
	save[read] = 0;
	for (size_t i = 0; i < read; ++i)
		if (save[i] == '\r' || save[i] == '\n') { save[i] = 0; break; }
	// Only this world's two slots are valid: a damaged pointer must never
	// select another world or an arbitrary save path.
	string64 slot_a, slot_b;
	xr_sprintf(slot_a, "%s_a", world);
	xr_sprintf(slot_b, "%s_b", world);
	return xr_strcmp(save, slot_a) == 0 || xr_strcmp(save, slot_b) == 0;
}

static bool world_store_write_pointer(LPCSTR world, LPCSTR save)
{
	string_path path, temp;
	world_store_pointer_path(world, path);
	xr_sprintf(temp, "%s.tmp", path);
	FILE* f = fopen(temp, "wb");
	if (!f) return false;
	const bool written = fwrite(save, 1, xr_strlen(save), f) == xr_strlen(save) && fflush(f) == 0 && _commit(_fileno(f)) == 0;
	const bool closed = fclose(f) == 0;
	return written && closed && MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
}

// CALifeSimulator constructor: load the newest saved world instead of a new game.
bool world_store_choose_start(LPSTR game_or_spawn, u32 game_size, LPSTR new_or_load, u32 mode_size)
{
	string64 world, save;
	if (!world_store_name(world)) return false;
	if (!world_store_read_pointer(world, save))
	{
		Msg("[NetAnomaly][world] '%s': no saved world yet, starting a new one", world);
		return false;
	}
	string128 file;
	xr_sprintf(file, "%s%s", save, SAVE_EXTENSION);
	if (!FS.exist("$game_saves$", file))
	{
		Msg("! [NetAnomaly][world] '%s': saved world %s is missing, starting a new one", world, file);
		return false;
	}
	xr_strcpy(game_or_spawn, game_size, save);
	xr_strcpy(new_or_load, mode_size, "load");
	s_world_loaded = true;
	s_world_cleanup_pending = true;
	Msg("[NetAnomaly][world] '%s': loading saved world %s", world, save);
	return true;
}

// Living player Actors saved with the world (they were online then) are
// released with their inventories: the players come back from their files.
static void world_store_cleanup_loaded()
{
	if (!s_world_cleanup_pending || !ai().get_alife()) return;
	s_world_cleanup_pending = false;
	CALifeSimulator* sim = const_cast<CALifeSimulator*>(ai().get_alife());
	CSE_ALifeCreatureActor* story = sim->graph().actor();
	xr_vector<CSE_ALifeDynamicObject*> players;
	// The mutable objects() overload is protected; the public const registry
	// is sufficient while collecting ids, before any release mutates it.
	for (const auto& entry : static_cast<const CALifeSimulator*>(sim)->objects().objects())
	{
		CSE_ALifeCreatureActor* actor = smart_cast<CSE_ALifeCreatureActor*>(entry.second);
		if (actor && actor != story && actor->get_health() > 0.f) players.push_back(entry.second);
	}
	for (CSE_ALifeDynamicObject* actor : players)
	{
		Msg("[NetAnomaly][world] released player Actor %u from the saved world (%u items)", actor->ID, u32(actor->children.size()));
		sim->release(actor, true);
	}
}

bool world_store_save_now(LPCSTR reason)
{
	string64 world;
	if (!world_store_name(world) || !ai().get_alife() || !g_pGameLevel) return false;
	string64 save, previous, slot_a;
	xr_sprintf(slot_a, "%s_a", world);
	// Derive the next slot from the committed pointer, not a process-local
	// counter reset by restart. Never overwrite the last committed snapshot,
	// including after a failed save or a failed pointer replacement.
	const bool current_a = world_store_read_pointer(world, previous) && xr_strcmp(previous, slot_a) == 0;
	xr_sprintf(save, "%s_%c", world, current_a ? 'b' : 'a');
	CTimer timer;
	timer.Start();
	try
	{
		Level().ClientSend();
		Level().ClientSave();
		const_cast<CALifeSimulator*>(ai().get_alife())->save(save, false);
	}
	catch (...)
	{
		Msg("! [NetAnomaly][world] saving %s failed (%s)", save, reason);
		return false;
	}
	s_world_last_save = real_time_ms();
	if (!world_store_write_pointer(world, save))
	{
		Msg("! [NetAnomaly][world] saved %s but could not point %s.current to it", save, world);
		return false;
	}
	Msg("[NetAnomaly][world] saved %s (%s) in %u ms", save, reason, timer.GetElapsed_ms());
	return true;
}

// Every server_update: periodic save, and one when the last player leaves.
static void world_store_update(xrServer* server)
{
	string64 world;
	if (!world_store_name(world) || !ai().get_alife()) return;
	struct CountPlayers
	{
		xrServer* server; u32 count;
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (CL != server->GetServerClient() && CL->owner) ++count;
		}
	} counter = {server, 0};
	server->ForEachClientDo(counter);
	static u32 previous_players = 0;
	const u32 now = real_time_ms();
	if (!s_world_last_save) s_world_last_save = now;
	if (counter.count == 0 && previous_players > 0) world_store_save_now("last player left");
	else if (now - s_world_last_save >= world_save_period_ms) world_store_save_now("periodic");
	previous_players = counter.count;
}
