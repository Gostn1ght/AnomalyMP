#pragma once

// GhenTuong: grenades and rockets extension
#ifndef CROCKETLAUNCHER_CHANGE
#define CROCKETLAUNCHER_CHANGE
#endif

class CCustomRocket;
class CGameObject;
class NET_Packet;

class CRocketLauncher
{
public:
	CRocketLauncher();
	~CRocketLauncher();

	virtual void Load(LPCSTR section);

	void AttachRocket(u16 rocket_id, CGameObject* parent_rocket_launcher);
	void DetachRocket(u16 rocket_id, bool bLaunch);

	void SpawnRocket(const shared_str& rocket_section, CGameObject* parent_rocket_launcher);
	void LaunchRocket(const Fmatrix& xform, const Fvector& vel, const Fvector& angular_vel);
	// Netcoop (owner 2026-10-17: "the RPG's rocket is not seen flying"): only
	// the server launches, so GE_LAUNCH_ROCKET carries the launch position,
	// direction and velocity; a client flies its copy from them.
	static void netcoop_write_launch(NET_Packet& P, CCustomRocket* rocket);
	void netcoop_read_launch(NET_Packet& P, u16 rocket_id);

protected:
	DEFINE_VECTOR(CCustomRocket*, ROCKET_VECTOR, ROCKETIT);
	ROCKET_VECTOR m_rockets;
	ROCKET_VECTOR m_launched_rockets;

	CCustomRocket* getCurrentRocket();
	void dropCurrentRocket();
	u32 getRocketCount();
	float m_fLaunchSpeed;
};
