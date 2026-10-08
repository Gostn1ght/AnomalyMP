#include "pch_script.h"
#include "PHCollisionDamageReceiver.h"
#include "PhysicObject.h"
#include "hit.h"
#include "PHDestroyable.h"
#include "hit_immunity.h"
#include "damage_manager.h"
#include "DestroyablePhysicsObject.h"
#include "netcoop.h"
#include "netcoop_destroyable_state.h"
#include "../Include/xrRender/KinematicsAnimated.h"
#include "../Include/xrRender/Kinematics.h"
#include "xrServer_Objects_ALife.h"
#include "game_object_space.h"
#include "script_callback_ex.h"
#include "script_game_object.h"
#include "../xrphysics/PhysicsShell.h"
#ifdef DEBUG
#include "../xrphysics/IPHWorld.h"
//#include "PHWorld.h"
//extern CPHWorld			*ph_world;
#endif
CDestroyablePhysicsObject::CDestroyablePhysicsObject()
{
	m_fHealth = 1.f;
}

CDestroyablePhysicsObject::~CDestroyablePhysicsObject()
{
}

void CDestroyablePhysicsObject::OnChangeVisual()
{
	if (m_pPhysicsShell)
	{
		m_pPhysicsShell->Deactivate();
		xr_delete(m_pPhysicsShell);
		VERIFY(0==Visual());
	}
	inherited::OnChangeVisual();
}

CPhysicsShellHolder* CDestroyablePhysicsObject::PPhysicsShellHolder()
{
	return cast_physics_shell_holder();
}

void CDestroyablePhysicsObject::net_Destroy()
{
	inherited::net_Destroy();
	CPHDestroyable::RespawnInit();
	CPHCollisionDamageReceiver::Clear();
}

BOOL CDestroyablePhysicsObject::net_Spawn(CSE_Abstract* DC)
{
	float saved_health = 1.f;
	if (netcoop::enabled())
	{
		auto* source = smart_cast<CSE_ALifeObjectPhysic*>(DC);
		if (!source || netcoop_destroyable_state::read(netcoop_destroyable_state::view(source->m_ini_string.c_str()), saved_health) ==
			netcoop_destroyable_state::Status::invalid) return FALSE;
	}
	BOOL res = inherited::net_Spawn(DC);
	if (!res) return FALSE;
	if (netcoop::enabled()) m_fHealth = saved_health;

	IKinematics* K = smart_cast<IKinematics*>(Visual());
	CInifile* ini = K->LL_UserData();
	//R_ASSERT2(ini->section_exist("destroyed"),"destroyable_object must have -destroyed- section in model user data");
	CPHDestroyable::Init();
	if (ini && ini->section_exist("destroyed"))
		CPHDestroyable::Load(ini, "destroyed");

	CDamageManager::reload("damage_section", ini);
	if (ini)
	{
		if (ini->section_exist("immunities")) CHitImmunity::LoadImmunities("immunities", ini);
		CPHCollisionDamageReceiver::Init();
		if (ini->section_exist("sound")) m_destroy_sound.create(ini->r_string("sound", "break_sound"), st_Effect,
		                                                        sg_SourceType);
		if (ini->section_exist("particles")) m_destroy_particles = ini->r_string("particles", "destroy_particles");
	}
	CParticlesPlayer::LoadParticles(K);
	RunStartupAnim(DC);
	return res;
}

bool CDestroyablePhysicsObject::netcoop_capture_saved_health(CSE_Abstract* entity)
{
	auto* target = smart_cast<CSE_ALifeObjectPhysic*>(entity);
	const u16 count = PHGetSyncItemsNumber();
	if (!target || target->ID != ID() || getDestroy() || H_Parent() ||
		!PPhysicsShell() || !count || !std::isfinite(m_fHealth)) return false;
	// Conservatively budget the complete stock Spawn_Write, not just the
	// INI field: all variable strings, client bytes and compressed bodies.
	// The fixed fields use <512 bytes; reserve one extra for strict <limit.
	std::size_t remaining = NET_PacketSizeLimit - 513;
	const std::size_t sizes[] = {target->client_data.size(), 8u * count,
		netcoop_destroyable_state::view(target->s_name.c_str()).size(), netcoop_destroyable_state::view(target->name_replace()).size(),
		netcoop_destroyable_state::view(target->get_visual()).size(), netcoop_destroyable_state::view(target->startup_animation.c_str()).size(),
		netcoop_destroyable_state::view(target->fixed_bones.c_str()).size()};
	for (const auto size : sizes)
	{
		if (size > remaining) return false;
		remaining -= size;
	}
	std::string saved;
	if (!netcoop_destroyable_state::write(netcoop_destroyable_state::view(target->m_ini_string.c_str()), m_fHealth, remaining, saved))
		return false;
	// Do not serialize an uninitialized Lua binder or invalidate borrowed
	// CSE INI pointers. The original sections stay byte-for-byte identical.
	target->m_ini_string = saved.c_str();
	return true;
}

//void CDestroyablePhysicsObject::Hit							(float P,Fvector &dir,CObject *who,s16 element,Fvector p_in_object_space, float impulse,  ALife::EHitType hit_type)
void CDestroyablePhysicsObject::Hit(SHit* pHDS)
{
	SHit HDS = *pHDS;
	callback(GameObject::eHit)(
		lua_game_object(),
		HDS.power,
		HDS.dir,
		HDS.who ? smart_cast<const CGameObject*>(HDS.who)->lua_game_object() : 0,
		HDS.bone()
	);
	HDS.power = CHitImmunity::AffectHit(HDS.power, HDS.hit_type);
	float hit_scale = 1.f, wound_scale = 1.f;
	CDamageManager::HitScale(HDS.bone(), hit_scale, wound_scale);
	HDS.power *= hit_scale;
	//	inherited::Hit(P,dir,who,element,p_in_object_space,impulse,hit_type);
	inherited::Hit(&HDS);
	m_fHealth -= HDS.power;
	if (m_fHealth <= 0.f)
	{
		//		CPHDestroyable::SetFatalHit(SHit(P,dir,who,element,p_in_object_space,impulse,hit_type));
		CPHDestroyable::SetFatalHit(HDS);
		if (CPHDestroyable::CanDestroy())Destroy();
	}
}

void CDestroyablePhysicsObject::Destroy()
{
	setVisible(false);				   
#ifdef DEBUG
	VERIFY(!physics_world()->Processing());
#endif
	const CGameObject* who_object = smart_cast<const CGameObject*>(FatalHit().initiator());
	callback(GameObject::eDeath)(lua_game_object(), who_object ? who_object->lua_game_object() : 0);
	CPHDestroyable::Destroy(ID(), "physic_destroyable_object");
	if (m_destroy_sound._handle())
	{
		m_destroy_sound.play_at_pos(this, Position());
	}
	if (*m_destroy_particles)
	{
		//Fvector dir;dir.set(0,1,0);
		Fmatrix m;
		m.identity();
		/////////////////////////////////////////////////
		m.j.set(0, 1.f, 0);
		///////////////////////////////////////////////

		Fvector hdir;
		hdir.set(CPHDestroyable::FatalHit().direction());

		if (fsimilar(_abs(m.j.dotproduct(hdir)), 1.f, EPS_L))
		{
			do
			{
				hdir.random_dir();
			}
			while (fsimilar(_abs(m.j.dotproduct(hdir)), 1.f, EPS_L));
		}
		m.i.crossproduct(m.j, hdir);
		m.i.normalize();
		m.k.crossproduct(m.i, m.j);
		StartParticles(m_destroy_particles, m, ID());
	}
	SheduleRegister();
}

void CDestroyablePhysicsObject::InitServerObject(CSE_Abstract* D)
{
	CSE_PHSkeleton* ps = smart_cast<CSE_PHSkeleton*>(D);
	R_ASSERT(ps);
	if (ps->_flags.test(CSE_PHSkeleton::flSpawnCopy))
		inherited::InitServerObject(D);
	else
		CPHDestroyable::InitServerObject(D);

	CSE_ALifeObjectPhysic* PO = smart_cast<CSE_ALifeObjectPhysic*>(D);
	if (PO)PO->type = epotSkeleton;
}

void CDestroyablePhysicsObject::shedule_Update(u32 dt)
{
	inherited::shedule_Update(dt);
	CPHDestroyable::SheduleUpdate(dt);
}

bool CDestroyablePhysicsObject::CanRemoveObject()
{
	return !CParticlesPlayer::IsPlaying() && !m_destroy_sound._feedback(); //&& sound!
}

DLL_Pure* CDestroyablePhysicsObject::_construct()
{
	CDamageManager::_construct();
	return inherited::_construct();
}
