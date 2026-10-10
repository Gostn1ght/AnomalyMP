#pragma once

//#include "weaponpistol.h"
#include "weaponcustompistol.h"
#include "rocketlauncher.h"
#include "script_export_space.h"

class CWeaponRPG7 : public CWeaponCustomPistol,
                    public CRocketLauncher
{
private:
	typedef CWeaponCustomPistol inherited;
public:
	CWeaponRPG7();
	virtual ~CWeaponRPG7();

	virtual BOOL net_Spawn(CSE_Abstract* DC);
	virtual void OnStateSwitch(u32 S, u32 oldState);
	virtual void OnEvent(NET_Packet& P, u16 type);
	virtual void ReloadMagazine();
	virtual void Load(LPCSTR section);
	virtual void switch2_Fire();
	virtual void FireTrace(const Fvector& P, const Fvector& D);
	bool netcoop_fire_shot(u8 kind, const Fvector& pos, const Fvector& dir) override;
	void netcoop_shot_effect(u8 kind) override;
	bool netcoop_launch_rocket(const Fvector& pos, const Fvector& dir);
	virtual void on_a_hud_attach();

	virtual void FireStart();
	virtual void SwitchState(u32 S);

	void UpdateMissileVisibility();
	virtual void UnloadMagazine(bool spawn_ammo = true);

	virtual void net_Import(NET_Packet& P); // import from server
protected:
	virtual bool AllowBore();
	virtual void PlayAnimReload();

	shared_str m_sRocketSection;
	bool m_netcoop_rocket_spawning = false;
	bool m_netcoop_launch_pending = false;
	u16 m_netcoop_launch_owner = 0xffff;
	Fvector m_netcoop_launch_pos, m_netcoop_launch_dir;

DECLARE_SCRIPT_REGISTER_FUNCTION
};
