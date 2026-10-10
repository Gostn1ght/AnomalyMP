//////////////////////////////////////////////////////////////////////
// ExplosiveItem.cpp:	класс для вещи которая взрывается под 
//						действием различных хитов (канистры,
//						балоны с газом и т.д.)
////////////////////////////////////////////////////////////////////////////
//	Modified by Axel DominatoR
//	Last updated: 13/08/2015
////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#include "../../script_game_object.h"
#include "ExplosiveItem.h"
#include "netcoop.h"
#include "netcoop_prop_mass.h"
#include "../xrPhysics/PhysicsShell.h"
#include "../Include/xrRender/Kinematics.h"


CExplosiveItem::CExplosiveItem(void)
{
}

CExplosiveItem::~CExplosiveItem(void)
{
}

void CExplosiveItem::Load(LPCSTR section)
{
	inherited::Load(section);
	CExplosive::Load(section);

	// Added by Axel, to enable optional condition use on any item
	m_flags.set(FUsingCondition, READ_IF_EXISTS(pSettings, r_bool, section, "use_condition", TRUE));

	CDelayedActionFuse::Initialize(pSettings->r_float(section, "time_to_explode"),
	                               pSettings->r_float(section, "condition_to_explode"));
	VERIFY(pSettings->line_exist (section,"set_timer_particles"));
}

void CExplosiveItem::net_Destroy()
{
	inherited::net_Destroy();
	CExplosive::net_Destroy();
}

BOOL CExplosiveItem::net_Spawn(CSE_Abstract* DC)
{
	if (!inherited::net_Spawn(DC)) return FALSE;
	// Map explosives are inventory objects, not CPhysicObject. Their authored
	// shell mass therefore never went through the crate/barrel mass adapter.
	if (netcoop::enabled() && OnServer() && !CanTake() && Visual() && PPhysicsShell() &&
		netcoop_prop_mass::classify(cNameVisual().c_str()) == netcoop_prop_mass::Kind::barrel)
	{
		Fvector center, half; Visual()->getVisData().box.get_CD(center, half);
		const float mass = netcoop_prop_mass::shell(netcoop_prop_mass::Kind::barrel, 2.f * half.x, 2.f * half.y, 2.f * half.z);
		if (mass > 0.f) PPhysicsShell()->setMass1(mass);
	}
	return TRUE;
}

//void CExplosiveItem::Hit(float P, Fvector &dir,	CObject* who, s16 element,
//						Fvector position_in_object_space, float impulse, 
//						ALife::EHitType hit_type)
void CExplosiveItem::Hit(SHit* pHDS)
{
	if (netcoop::pure_client()) return; // the authority owns condition and fuse
	//	inherited::Hit(P,dir,who,element,position_in_object_space,impulse,hit_type);
	if (CDelayedActionFuse::isActive())pHDS->power = 0.f;
	inherited::Hit(pHDS);
	if (!CDelayedActionFuse::isActive() &&
		CDelayedActionFuse::CheckCondition(GetCondition()))
	{
		//запомнить того, кто взорвал вещь
		SetInitiator(pHDS->who ? pHDS->who->ID() : ID());
		// Sleeping inventory objects need frame processing once the fuse is lit.
		processing_activate();
		if (netcoop::enabled()) Msg("[Lost Zone][explosive] armed %s (%u), initiator %u, condition %.3f", cNameSect().c_str(), ID(), Initiator(), GetCondition());
	}
}

void CExplosiveItem::StartTimerEffects()
{
	CParticlesPlayer::StartParticles(pSettings->r_string(*cNameSect(), "set_timer_particles"), Fvector().set(0, 1, 0),
	                                 ID());
}

void CExplosiveItem::OnEvent(NET_Packet& P, u16 type)
{
	CExplosive::OnEvent(P, type);
	inherited::OnEvent(P, type);
}

void CExplosiveItem::UpdateCL()
{
	UpdateFuse();
	CExplosive::UpdateCL();
	inherited::UpdateCL();
}

void CExplosiveItem::shedule_Update(u32 dt)
{
	inherited::shedule_Update(dt);
	UpdateFuse();
}

void CExplosiveItem::UpdateFuse()
{
	if (netcoop::pure_client()) return;
	if (CDelayedActionFuse::isActive() && CDelayedActionFuse::Update(GetCondition()))
	{
		Fvector normal;
		FindNormal(normal);
		CExplosive::GenExplodeEvent(Position(), normal);
		CParticlesPlayer::StopParticles(ID(), BI_NONE, true);
		::luabind::functor<void> funct;
		if (ai().script_engine().functor("_G.CExplosiveItem__OnExplode", funct))
		{
			funct(this->lua_game_object());
		}
	}
}

bool CExplosiveItem::shedule_Needed()
{
	//.	return true;

	return (inherited::shedule_Needed() || CDelayedActionFuse::isActive());
}

void CExplosiveItem::renderable_Render()
{
	inherited::renderable_Render();
}

void CExplosiveItem::net_Relcase(CObject* O)
{
	CExplosive::net_Relcase(O);
	inherited::net_Relcase(O);
}

void CExplosiveItem::ActivateExplosionBox(const Fvector& size, Fvector& in_out_pos)
{
	//PKinematics(Visual())->CalculateBones();
}

void CExplosiveItem::GetRayExplosionSourcePos(Fvector& pos)
{
	random_point_in_object_box(pos, this);
}
