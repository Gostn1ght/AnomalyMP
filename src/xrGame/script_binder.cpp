////////////////////////////////////////////////////////////////////////////
//	Module 		: script_binder.cpp
//	Created 	: 26.03.2004
//  Modified 	: 26.03.2004
//	Author		: Dmitriy Iassenev
//	Description : Script objects binder
////////////////////////////////////////////////////////////////////////////

#include "pch_script.h"
#include "Actor.h"
#include "netcoop.h"
#include "ai_space.h"
#include "script_engine.h"
#include "script_binder.h"
#include "xrServer_Objects_ALife.h"
#include "script_binder_object.h"
#include "script_game_object.h"
#include "gameobject.h"
#include "level.h"

// comment next string when commiting
//#define DBG_DISABLE_SCRIPTS

// Netcoop server: object scripts outside the per-update binding (spawn,
// reinit, reload, destroy) also see the nearest player as db.actor.
namespace
{
struct netcoop_actor_scope
{
	bool bound;
	bool server_object;

	explicit netcoop_actor_scope(CScriptBinder* binder) : bound(false), server_object(false)
	{
		CGameObject* object = smart_cast<CGameObject*>(binder);
		server_object = netcoop::enabled() && g_pGameLevel && Level().Server && object && !object->cast_actor();
		if (server_object)
			bound = netcoop::server_bind_nearest_actor(object);
	}

	~netcoop_actor_scope()
	{
		if (bound)
			netcoop::server_unbind_actor();
	}
};
}

CScriptBinder::CScriptBinder()
{
	init();
}

CScriptBinder::~CScriptBinder()
{
	VERIFY(!m_object);
}

void CScriptBinder::init()
{
	m_object = 0;
}

void CScriptBinder::clear()
{
	try
	{
		xr_delete(m_object);
	}
	catch (...)
	{
		m_object = 0;
	}
	init();
}

void CScriptBinder::reinit()
{
#ifdef DEBUG_MEMORY_MANAGER
	size_t									start = 0;
	if (g_bMEMO)
		start							= Memory.mem_usage();
#endif // DEBUG_MEMORY_MANAGER
	if (m_object)
	{
		netcoop_actor_scope netcoop_scope(this);
		try
		{
			m_object->reinit();
		}
		catch (...)
		{
			if (!netcoop_scope.server_object)
				clear();
		}
	}
#ifdef DEBUG_MEMORY_MANAGER
	if (g_bMEMO) {
//		lua_gc				(ai().script_engine().lua(),LUA_GCCOLLECT,0);
//		lua_gc				(ai().script_engine().lua(),LUA_GCCOLLECT,0);
		Msg					("CScriptBinder::reinit() : %lld",Memory.mem_usage() - start);
	}
#endif // DEBUG_MEMORY_MANAGER
}

void CScriptBinder::Load(LPCSTR section)
{
}

void CScriptBinder::reload(LPCSTR section)
{
#ifdef DEBUG_MEMORY_MANAGER
	size_t									start = 0;
	if (g_bMEMO)
		start							= Memory.mem_usage();
#endif // DEBUG_MEMORY_MANAGER
#ifndef DBG_DISABLE_SCRIPTS
	VERIFY(!m_object);
	if (!pSettings->line_exist(section, "script_binding"))
		return;

	::luabind::functor<void> lua_function;
	if (!ai().script_engine().functor(pSettings->r_string(section, "script_binding"), lua_function))
	{
		ai().script_engine().script_log(ScriptStorage::eLuaMessageTypeError, "function %s is not loaded!",
		                                pSettings->r_string(section, "script_binding"));
		return;
	}

	CGameObject* game_object = smart_cast<CGameObject*>(this);

	try
	{
		lua_function(game_object ? game_object->lua_game_object() : 0);
	}
	catch (...)
	{
		clear();
		return;
	}

	if (m_object)
	{
		netcoop_actor_scope netcoop_scope(this);
		try
		{
			m_object->reload(section);
		}
		catch (...)
		{
			if (!netcoop_scope.server_object)
				clear();
		}
	}
#endif
#ifdef DEBUG_MEMORY_MANAGER
	if (g_bMEMO) {
//		lua_gc				(ai().script_engine().lua(),LUA_GCCOLLECT,0);
//		lua_gc				(ai().script_engine().lua(),LUA_GCCOLLECT,0);
		Msg					("CScriptBinder::reload() : %lld",Memory.mem_usage() - start);
	}
#endif // DEBUG_MEMORY_MANAGER
}

BOOL CScriptBinder::net_Spawn(CSE_Abstract* DC)
{
#ifdef DEBUG_MEMORY_MANAGER
	size_t									start = 0;
	if (g_bMEMO)
		start							= Memory.mem_usage();
#endif // DEBUG_MEMORY_MANAGER
	CSE_Abstract* abstract = (CSE_Abstract*)DC;
	CSE_ALifeObject* object = smart_cast<CSE_ALifeObject*>(abstract);
	if (object && m_object)
	{
		netcoop_actor_scope netcoop_scope(this);
		try
		{
			return ((BOOL)m_object->net_Spawn(object));
		}
		catch (...)
		{
			// A GAMMA script error here would leave a server NPC without any
			// logic for good; keep its binder, the error is in the log.
			if (!netcoop_scope.server_object)
				clear();
		}
	}

#ifdef DEBUG_MEMORY_MANAGER
	if (g_bMEMO) {
//		lua_gc				(ai().script_engine().lua(),LUA_GCCOLLECT,0);
//		lua_gc				(ai().script_engine().lua(),LUA_GCCOLLECT,0);
		Msg					("CScriptBinder::net_Spawn() : %lld",Memory.mem_usage() - start);
	}
#endif // DEBUG_MEMORY_MANAGER

	return (TRUE);
}

void CScriptBinder::net_Destroy()
{
	if (m_object)
	{
#ifdef _DEBUG
		Msg						("* Core object %s is UNbinded from the script object",smart_cast<CGameObject*>(this) ? *smart_cast<CGameObject*>(this)->cName() : "");
#endif // _DEBUG
		netcoop_actor_scope netcoop_scope(this);
		try
		{
			m_object->net_Destroy();
		}
		catch (...)
		{
			clear();
		}
	}
	xr_delete(m_object);
}

void CScriptBinder::set_object(CScriptBinderObject* object)
{
	//netcoop: a pure client has no alife simulator, so NPC and remote-player binders stay
	// disabled (the server runs their logic). The locally controlled Actor keeps its
	// GAMMA binder: actor_on_update, time events, item-use and HUD animations run there.
	CActor* netcoop_actor = smart_cast<CActor*>(this);
	const bool netcoop_own_actor = netcoop_actor && netcoop_actor->Local();
	if (strstr(Core.Params, "-netcoop") && !strstr(Core.Params, "server(") && !netcoop_own_actor)
	{
		static bool s_netcoop_bind_logged = false;
		if (!s_netcoop_bind_logged)
		{
			s_netcoop_bind_logged = true;
			Msg("[NetAnomaly] script binders disabled on netcoop client");
		}
		xr_delete(object);
		return;
	}

	if (IsGameTypeSingle())
	{
		VERIFY2(!m_object, "Cannot bind to the object twice!");
#ifdef _DEBUG
		Msg					("* Core object %s is binded with the script object",smart_cast<CGameObject*>(this) ? *smart_cast<CGameObject*>(this)->cName() : "");
#endif // _DEBUG
		m_object = object;
	}
	else
	{
		xr_delete(object);
	}
}

void CScriptBinder::shedule_Update(u32 time_delta)
{
	if (!m_object)
		return;

	// Netcoop server: GAMMA NPC and monster logic assumes a single db.actor. Bind
	// it to the nearest player for this update; without players the NPC idles.
	CGameObject* netcoop_object = smart_cast<CGameObject*>(this);
	const bool netcoop_npc = netcoop::enabled() && g_pGameLevel && Level().Server &&
		netcoop_object && !smart_cast<CActor*>(netcoop_object);
	if (netcoop_npc && !netcoop::server_bind_nearest_actor(netcoop_object))
		return;

	try
	{
		m_object->shedule_Update(time_delta);
	}
	catch (...)
	{
		// A single script error used to drop the binder for good, leaving the NPC
		// without any logic. Keep it on netcoop servers; the error is logged.
		if (!netcoop_npc)
			clear();
	}

	if (netcoop_npc)
		netcoop::server_unbind_actor();
}

void CScriptBinder::save(NET_Packet& output_packet)
{
	if (m_object)
	{
		try
		{
			m_object->save(&output_packet);
		}
		catch (...)
		{
			clear();
		}
	}
}

void CScriptBinder::load(IReader& input_packet)
{
	if (m_object)
	{
		try
		{
			m_object->load(&input_packet);
		}
		catch (...)
		{
			clear();
		}
	}
}

BOOL CScriptBinder::net_SaveRelevant()
{
	if (m_object)
	{
		try
		{
			return (m_object->net_SaveRelevant());
		}
		catch (...)
		{
			clear();
		}
	}
	return (FALSE);
}

void CScriptBinder::net_Relcase(CObject* object)
{
	CGameObject* game_object = smart_cast<CGameObject*>(object);
	if (m_object && game_object)
	{
		try
		{
			m_object->net_Relcase(game_object->lua_game_object());
		}
		catch (...)
		{
			clear();
		}
	}
}
