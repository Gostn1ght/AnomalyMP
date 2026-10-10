#include "stdafx.h"
#include "weaponrpg7.h"
#include "xrserver_objects_alife_items.h"
#include "explosiverocket.h"
#include "entity.h"
#include "level.h"
#include "player_hud.h"
#include "hudmanager.h"
#include "netcoop.h"

CWeaponRPG7::CWeaponRPG7()
{
}

CWeaponRPG7::~CWeaponRPG7()
{
}

void CWeaponRPG7::Load(LPCSTR section)
{
	inherited::Load(section);
	CRocketLauncher::Load(section);

	m_zoom_params.m_fScopeZoomFactor = pSettings->r_float(section, "max_zoom_factor");

	m_sRocketSection = pSettings->r_string(section, "rocket_class");
}

bool CWeaponRPG7::AllowBore()
{
	return inherited::AllowBore() && 0 != iAmmoElapsed;
}

void CWeaponRPG7::FireTrace(const Fvector& P, const Fvector& D)
{
	if (netcoop::enabled() && ParentIsActor())
	{
		// The server launches the rocket; no invisible hitscan bullet as well.
		if (netcoop::pure_client())
		{
			netcoop_send_shot(P, D, 1);
			netcoop_consume_projectile();
		}
		UpdateMissileVisibility();
		return;
	}
	inherited::FireTrace(P, D);
	UpdateMissileVisibility();
}

void CWeaponRPG7::on_a_hud_attach()
{
	inherited::on_a_hud_attach();
	UpdateMissileVisibility();
}

bool CWeaponRPG7::netcoop_launch_rocket(const Fvector& pos, const Fvector& direction)
{
	CExplosiveRocket* rocket = smart_cast<CExplosiveRocket*>(getCurrentRocket());
	if (!rocket || !H_Parent() || !OnServer()) return false;
	Fvector velocity; velocity.set(direction).normalize_safe();
	Fmatrix launch; launch.identity(); launch.k.set(velocity);
	Fvector::generate_orthonormal_basis(launch.k, launch.j, launch.i);
	launch.c.set(pos);
	velocity.mul(m_fLaunchSpeed);
	CRocketLauncher::LaunchRocket(launch, velocity, zero_vel);
	rocket->SetInitiator(H_Parent()->ID());
	NET_Packet packet;
	u_EventGen(packet, GE_LAUNCH_ROCKET, ID());
	packet.w_u16(rocket->ID());
	u_EventSend(packet);
	return true;
}

bool CWeaponRPG7::netcoop_fire_shot(u8 kind, const Fvector& pos, const Fvector& dir)
{
	if (kind != 1 || !iAmmoElapsed || m_magazine.empty() || m_netcoop_launch_pending) return false;
	if (!getRocketCount())
	{
		// Rocket spawning is asynchronous. Reserve the shot now and launch on
		// ownership arrival instead of losing a freshly reloaded first shot.
		m_netcoop_launch_pending = true;
		m_netcoop_launch_owner = H_Parent()->ID();
		m_netcoop_launch_pos.set(pos); m_netcoop_launch_dir.set(dir);
		if (!m_netcoop_rocket_spawning)
		{
			m_netcoop_rocket_spawning = true;
			CRocketLauncher::SpawnRocket(m_sRocketSection, this);
		}
	}
	else if (!netcoop_launch_rocket(pos, dir)) return false;
	OnShot();
	netcoop_consume_projectile();
	UpdateMissileVisibility();
	return true;
}

void CWeaponRPG7::netcoop_shot_effect(u8 kind)
{
	if (kind == 1) OnShot();
}

void CWeaponRPG7::UpdateMissileVisibility()
{
	bool vis_hud, vis_weap;
	vis_hud = (!!iAmmoElapsed || GetState() == eReload);
	vis_weap = !!iAmmoElapsed;

	if (GetHUDmode())
	{
		HudItemData()->set_bone_visible("grenade", vis_hud,TRUE);
	}

	IKinematics* pWeaponVisual = smart_cast<IKinematics*>(Visual());
	VERIFY(pWeaponVisual);
	if (pWeaponVisual) pWeaponVisual->LL_SetBoneVisible(pWeaponVisual->LL_BoneID("grenade"), vis_weap, TRUE);
}

BOOL CWeaponRPG7::net_Spawn(CSE_Abstract* DC)
{
	BOOL l_res = inherited::net_Spawn(DC);

	UpdateMissileVisibility();
	if (iAmmoElapsed && !getCurrentRocket())
	{
		m_netcoop_rocket_spawning = netcoop::enabled() && OnServer();
		CRocketLauncher::SpawnRocket(m_sRocketSection, this);
	}

	return l_res;
}

void CWeaponRPG7::OnStateSwitch(u32 S, u32 oldState)
{
	inherited::OnStateSwitch(S, oldState);
	UpdateMissileVisibility();
}

void CWeaponRPG7::UnloadMagazine(bool spawn_ammo)
{
	inherited::UnloadMagazine(spawn_ammo);
	UpdateMissileVisibility();
}

void CWeaponRPG7::ReloadMagazine()
{
	inherited::ReloadMagazine();

	if (iAmmoElapsed && !getRocketCount() && (!netcoop::enabled() || !m_netcoop_rocket_spawning))
	{
		m_netcoop_rocket_spawning = netcoop::enabled() && OnServer();
		CRocketLauncher::SpawnRocket(m_sRocketSection.c_str(), this);
	}
}

void CWeaponRPG7::SwitchState(u32 S)
{
	inherited::SwitchState(S);
}

void CWeaponRPG7::FireStart()
{
	inherited::FireStart();
}

#include "inventory.h"
#include "inventoryOwner.h"

void CWeaponRPG7::switch2_Fire()
{
	m_iShotNum = 0;
	m_bFireSingleShot = true;
	bWorking = false;
	if (netcoop::enabled() && ParentIsActor() && (netcoop::pure_client() || netcoop::server_player_copy(H_Parent()))) return;

	if (GetState() == eFire && getRocketCount())
	{
		Fvector p1, d1, p;
		Fvector p2, d2, d;
		p1.set(get_LastFP());
		d1.set(get_LastFD());
		p = p1;
		d = d1;
		CEntity* E = smart_cast<CEntity*>(H_Parent());
		if (E)
		{
			E->g_fireParams(this, p2, d2);
			p = p2;
			d = d2;

			if (IsHudModeNow())
			{
				Fvector p0;
				float dist = GetRQ().range;
				p0.mul(d2, dist);
				p0.add(p1);
				p = p1;
				d.sub(p0, p1);
				d.normalize_safe();
			}
		}

		Fmatrix launch_matrix;
		launch_matrix.identity();
		launch_matrix.k.set(d);
		Fvector::generate_orthonormal_basis(launch_matrix.k,
		                                    launch_matrix.j, launch_matrix.i);
		launch_matrix.c.set(p);

		d.normalize();
		d.mul(m_fLaunchSpeed);

		CRocketLauncher::LaunchRocket(launch_matrix, d, zero_vel);

		CExplosiveRocket* pGrenade = smart_cast<CExplosiveRocket*>(getCurrentRocket());
		VERIFY(pGrenade);
		pGrenade->SetInitiator(H_Parent()->ID());

		if (OnServer())
		{
			NET_Packet P;
			u_EventGen(P, GE_LAUNCH_ROCKET, ID());
			P.w_u16(u16(getCurrentRocket()->ID()));
			u_EventSend(P);
		}
	}
}

void CWeaponRPG7::PlayAnimReload()
{
	VERIFY(GetState()==eReload);
	PlayHUDMotion("anm_reload", TRUE, this, GetState(), 1.f, 0.f, false);
}

void CWeaponRPG7::OnEvent(NET_Packet& P, u16 type)
{
	inherited::OnEvent(P, type);
	if (type == GE_WPN_STATE_CHANGE && netcoop::server_player_copy(H_Parent()) &&
		iAmmoElapsed && !getRocketCount() && !m_netcoop_rocket_spawning)
	{
		m_netcoop_rocket_spawning = true;
		CRocketLauncher::SpawnRocket(m_sRocketSection, this);
	}
	u16 id;
	switch (type)
	{
	case GE_OWNERSHIP_TAKE:
		{
			P.r_u16(id);
			CRocketLauncher::AttachRocket(id, this);
			m_netcoop_rocket_spawning = false;
			if (m_netcoop_launch_pending)
			{
				m_netcoop_launch_pending = false;
				if (H_Parent() && H_Parent()->ID() == m_netcoop_launch_owner)
					netcoop_launch_rocket(m_netcoop_launch_pos, m_netcoop_launch_dir);
			}
		}
		break;
	case GE_OWNERSHIP_REJECT:
	case GE_LAUNCH_ROCKET:
		{
			bool bLaunch = (type == GE_LAUNCH_ROCKET);
			P.r_u16(id);
			CRocketLauncher::DetachRocket(id, bLaunch);
			if (bLaunch)
				UpdateMissileVisibility();
		}
		break;
	}
}

void CWeaponRPG7::net_Import(NET_Packet& P)
{
	inherited::net_Import(P);
	UpdateMissileVisibility();
}
