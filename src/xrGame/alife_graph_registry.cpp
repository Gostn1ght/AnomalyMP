////////////////////////////////////////////////////////////////////////////
//	Module 		: alife_graph_registry.cpp
//	Created 	: 15.01.2003
//  Modified 	: 12.05.2004
//	Author		: Dmitriy Iassenev
//	Description : ALife graph registry
////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#include "alife_graph_registry.h"
#include "../xrEngine/x_ray.h"
#include "../xrEngine/IGame_Persistent.h"

#include <cmath>

extern ENGINE_API bool g_dedicated_server;

using namespace ALife;

CALifeGraphRegistry::CALifeGraphRegistry()
{
	m_level = 0;
	m_process_time = 0;
	m_actor = 0;
}

CALifeGraphRegistry::~CALifeGraphRegistry()
{
	xr_delete(m_level);
}

void CALifeGraphRegistry::on_load()
{
	for (int i = 0; i < GameGraph::LOCATION_TYPE_COUNT; ++i)
	{
		{
			for (int j = 0; j < GameGraph::LOCATION_COUNT; ++j)
				m_terrain[i][j].clear();
		}
		for (GameGraph::_GRAPH_ID j = 0; j < (GameGraph::_GRAPH_ID)ai().game_graph().header().vertex_count(); ++j)
			m_terrain[i][ai().game_graph().vertex(j)->vertex_type()[i]].push_back(j);
	}

	m_objects.resize(ai().game_graph().header().vertex_count());

	{
		GRAPH_REGISTRY::iterator I = m_objects.begin();
		GRAPH_REGISTRY::iterator E = m_objects.end();
		for (; I != E; ++I)
			(*I).objects().clear();
	}
}

void CALifeGraphRegistry::update(CSE_ALifeDynamicObject* object)
{
	if (!object->m_bDirectControl)
		return;

	// NetAnomaly co-op: player Actors carry M_SPAWN_OBJECT_ASPLAYER too, but
	// the ALife actor stays the story Actor (id 0). A player Actor there left
	// a dangling alife():actor() after the player disconnected.
	const bool netcoop_player_actor = m_actor && m_actor != object && strstr(Core.Params, "-netcoop");
	if (object->s_flags.is(M_SPAWN_OBJECT_ASPLAYER) && !netcoop_player_actor)
	{
		const bool first_actor_registration = !m_actor && !m_level;
		m_actor = smart_cast<CSE_ALifeCreatureActor*>(object);
		R_ASSERT2(m_actor, "Invalid flag M_SPAWN_OBJECT_ASPLAYER for non-actor object!");
		// A dedicated netcoop new game has no main-menu Actor binder to move the
		// starter Actor out of fake_start. Select the GAMMA spawn point before
		// setup_current_level() chooses and loads the first level.
		if (first_actor_registration && g_dedicated_server && strstr(Core.Params, "-netcoop") &&
			!xr_strcmp(g_pGamePersistent->m_game_params.m_new_or_load, "new"))
		{
			LPCSTR option = strstr(Core.Params, "-netcoop_start_location=");
			if (option)
			{
				option += xr_strlen("-netcoop_start_location=");
				string64 section = {};
				u32 length = 0;
				while ((option[length] >= 'a' && option[length] <= 'z') ||
					(option[length] >= 'A' && option[length] <= 'Z') ||
					(option[length] >= '0' && option[length] <= '9') || option[length] == '_')
				{
					R_ASSERT2(length + 1 < sizeof(section), "Netcoop start location name is too long");
					section[length] = option[length];
					++length;
				}
				R_ASSERT2(length && (!option[length] || option[length] == ' '),
					"Invalid -netcoop_start_location value");
				string_path config_path;
				FS.update_path(config_path, "$game_config$", "plugins\\new_game_start_locations.ltx");
				R_ASSERT3(FS.exist(config_path), "Missing GAMMA start locations file", config_path);
				CInifile gamma_starts(config_path, TRUE);
				// Maps without a GAMMA start (labs, Limansk, Hospital...) start at a
				// level changer's arrival point: netcoop\start_levels.ltx, generated
				// from the Zone's level changers (tools/make-cluster-plan.py).
				string_path cluster_path;
				FS.update_path(cluster_path, "$game_config$", "netcoop\\start_levels.ltx");
				const bool gamma_has = gamma_starts.section_exist(section);
				CInifile* cluster_starts = !gamma_has && FS.exist(cluster_path) ? xr_new<CInifile>(cluster_path, TRUE) : nullptr;
				CInifile& starts = gamma_has || !cluster_starts ? gamma_starts : *cluster_starts;
				R_ASSERT3(starts.section_exist(section), "Unknown netcoop start location", section);
				const u32 graph_id = starts.r_u32(section, "gvid");
				R_ASSERT2(graph_id < ai().game_graph().header().vertex_count(), "Invalid start game graph vertex");
				const u32 level_id = starts.r_u32(section, "lvid");
				const Fvector position = {starts.r_float(section, "x"), starts.r_float(section, "y"),
					starts.r_float(section, "z")};
				R_ASSERT2(std::isfinite(position.x) && std::isfinite(position.y) &&
					std::isfinite(position.z), "Invalid start position");
				m_actor->m_tGraphID = static_cast<GameGraph::_GRAPH_ID>(graph_id);
				m_actor->m_tNodeID = level_id;
				m_actor->o_Position = position;
				Msg("[Lost Zone] Dedicated new game start: %s, graph=%u, level_vertex=%u, position=%.2f %.2f %.2f",
					section, graph_id, level_id, position.x, position.y, position.z);
				if (cluster_starts) xr_delete(cluster_starts);
			}
		}
	}

	if (m_actor && !m_level)
		setup_current_level();

	CSE_ALifeInventoryItem* item = smart_cast<CSE_ALifeInventoryItem*>(object);
	if (!item || !item->attached())
		add(object, object->m_tGraphID);
}

void CALifeGraphRegistry::setup_current_level()
{
	m_level = xr_new<CALifeLevelRegistry>(ai().game_graph().vertex(actor()->m_tGraphID)->level_id());
	level().set_process_time(m_process_time);
	for (int i = 0, n = ai().game_graph().header().vertex_count(); i < n; ++i)
		if (ai().game_graph().vertex(i)->level_id() == level().level_id())
		{
			D_OBJECT_P_MAP::const_iterator I = m_objects[i].objects().objects().begin();
			D_OBJECT_P_MAP::const_iterator E = m_objects[i].objects().objects().end();
			for (; I != E; ++I)
				level().add((*I).second);
		}

	{
		xr_vector<CSE_ALifeDynamicObject*>::const_iterator I = m_temp.begin();
		xr_vector<CSE_ALifeDynamicObject*>::const_iterator E = m_temp.end();
		for (; I != E; ++I)
			level().add(*I);

		m_temp.clear();
	}
	GameGraph::LEVEL_MAP::const_iterator I = ai().game_graph().header().levels().find(
		ai().game_graph().vertex(actor()->m_tGraphID)->level_id());
	R_ASSERT2(ai().game_graph().header().levels().end() != I, "Graph point level ID not found!");

	int id = pApp->Level_ID(*(*I).second.name(), "1.0", true);
	VERIFY3(id >= 0, "Level is corrupted or doesn't exist", *(*I).second.name());
	ai().load(*(*I).second.name());
}

void CALifeGraphRegistry::attach(CSE_Abstract& object, CSE_ALifeInventoryItem* item,
                                 GameGraph::_GRAPH_ID game_vertex_id, bool alife_query, bool add_children)
{
#ifdef DEBUG
	if (psAI_Flags.test(aiALife)) {
		Msg						("[LSS] Attaching item [%s][%d] to [%s][%d]",item->base()->name_replace(),item->base()->ID,object.name_replace(),object.ID);
	}
#endif
	if (alife_query)
		remove(smart_cast<CSE_ALifeDynamicObject*>(item), game_vertex_id);
	else
		level().remove(smart_cast<CSE_ALifeDynamicObject*>(item));

	CSE_ALifeDynamicObject* dynamic_object = smart_cast<CSE_ALifeDynamicObject*>(&object);
	R_ASSERT2(!alife_query || dynamic_object, "Cannot attach an item to a non-alife object object");

	dynamic_object->attach(item, alife_query, add_children);
}

void CALifeGraphRegistry::detach(CSE_Abstract& object, CSE_ALifeInventoryItem* item,
                                 GameGraph::_GRAPH_ID game_vertex_id, bool alife_query, bool remove_children)
{
#ifdef DEBUG
	if (psAI_Flags.test(aiALife)) {
		Msg						("[LSS] Detaching item [%s][%d] from [%s][%d]",item->base()->name_replace(),item->base()->ID,object.name_replace(),object.ID);
	}
#endif
	if (alife_query)
		add(smart_cast<CSE_ALifeDynamicObject*>(item), game_vertex_id);
	else
	{
		CSE_ALifeDynamicObject* object = smart_cast<CSE_ALifeDynamicObject*>(item);
		VERIFY(object);
		object->m_tGraphID = game_vertex_id;
		level().add(object);
	}

	CSE_ALifeDynamicObject* dynamic_object = smart_cast<CSE_ALifeDynamicObject*>(&object);
	R_ASSERT2(!alife_query || dynamic_object, "Cannot detach an item from non-alife object");

	VERIFY(
		alife_query || !smart_cast<CSE_ALifeDynamicObject*>(&object) || (ai().game_graph().vertex(smart_cast<
			CSE_ALifeDynamicObject*>(&object)->m_tGraphID)->level_id() == level().level_id()));

	if (dynamic_object)
		dynamic_object->detach(item, 0, alife_query, remove_children);
	else
	{
#ifdef DEBUG
		bool					value = std::find(object.children.begin(),object.children.end(),item->base()->ID) != object.children.end();
		if (!value) {
			Msg					("! ERROR: can't detach independant object. entity[%s:%d], parent[%s:%d], section[%s]",
				item->base()->name_replace(),item->base()->ID,object.name_replace(),object.ID, *item->base()->s_name);
		}
#endif // DEBUG
		//		R_ASSERT2				(value,"Can't detach an item which is not on my own");
	}
}

void CALifeGraphRegistry::add(CSE_ALifeDynamicObject* object, GameGraph::_GRAPH_ID game_vertex_id, bool update)
{
#ifdef DEBUG
	if (psAI_Flags.test(aiALife)) {
		Msg						("[LSS] adding object [%s][%d] to graph point %d",object->name_replace(),object->ID,game_vertex_id);
	}
#endif
	if (!object->m_bOnline && object->used_ai_locations() /**&& object->interactive()/**/)
	{
		VERIFY(ai().game_graph().valid_vertex_id(game_vertex_id));
		m_objects[game_vertex_id].objects().add(object->ID, object);
		object->m_tGraphID = game_vertex_id;
	}
	else if (!m_level && update)
	{
		m_temp.push_back(object);
		object->m_tGraphID = game_vertex_id;
	}

	if (update && m_level && ai().game_graph().valid_vertex_id(game_vertex_id))
		level().add(object);
}

void CALifeGraphRegistry::remove(CSE_ALifeDynamicObject* object, GameGraph::_GRAPH_ID game_vertex_id, bool update)
{
	if (object->used_ai_locations() /**&& object->interactive()/**/)
	{
#ifdef DEBUG
		if (psAI_Flags.test(aiALife)) {
			Msg					("[LSS] removing object [%s][%d] from graph point %d",object->name_replace(),object->ID,game_vertex_id);
		}
#endif
		m_objects[game_vertex_id].objects().remove(object->ID);
	}
	if (update && m_level)
		level().remove(object, ai().game_graph().vertex(game_vertex_id)->level_id() != level().level_id());
}
