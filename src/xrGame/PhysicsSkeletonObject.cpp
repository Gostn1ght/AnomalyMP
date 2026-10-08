#include "stdafx.h"
#include "physicsskeletonobject.h"
//#include "PhysicsShell.h"
#include "../xrphysics/physicsshell.h"
#include "phsynchronize.h"
#include "xrserver_objects_alife.h"
#include "../Include/xrRender/Kinematics.h"
#include "../xrEngine/xr_collide_form.h"

CPhysicsSkeletonObject::CPhysicsSkeletonObject()
{
}

CPhysicsSkeletonObject::~CPhysicsSkeletonObject()
{
}


BOOL CPhysicsSkeletonObject::net_Spawn(CSE_Abstract* DC)
{
	CSE_Abstract* e = (CSE_Abstract*)(DC);

	BOOL res = inherited::net_Spawn(DC);
	if (!res) return FALSE;
	xr_delete(collidable.model);
	collidable.model = xr_new<CCF_Skeleton>(this);
	CPHSkeleton::Spawn(e);
	setVisible(TRUE);
	setEnabled(TRUE);
	if (!PPhysicsShell() || !PPhysicsShell()->isBreakable())
		SheduleUnregister();
	return res;
}

void CPhysicsSkeletonObject::SpawnInitPhysics(CSE_Abstract* D)
{
	CreatePhysicsShell(D);
	IKinematics* K = smart_cast<IKinematics*>(Visual());
	if (K)
	{
		K->CalculateBones_Invalidate();
		K->CalculateBones(TRUE);
	}
}

void CPhysicsSkeletonObject::net_Destroy()
{
	inherited::net_Destroy();
	CPHSkeleton::RespawnInit();
}

void CPhysicsSkeletonObject::Load(LPCSTR section)
{
	inherited::Load(section);
	CPHSkeleton::Load(section);
}

void CPhysicsSkeletonObject::CreatePhysicsShell(CSE_Abstract* e)
{
	CSE_PHSkeleton* po = smart_cast<CSE_PHSkeleton*>(e);
	if (m_pPhysicsShell) return;
	if (!Visual()) return;
	m_pPhysicsShell = P_build_Shell(this, !po->_flags.test(CSE_PHSkeleton::flActive));
}


void CPhysicsSkeletonObject::shedule_Update(u32 dt)
{
	inherited::shedule_Update(dt);

	CPHSkeleton::Update(dt);
}

bool CPhysicsSkeletonObject::netcoop_capture_saved_physics(CSE_Abstract* entity)
{
	CSE_ALifePHSkeletonObject* target = smart_cast<CSE_ALifePHSkeletonObject*>(entity);
	const u16 count = PHGetSyncItemsNumber();
	// Use the existing stock codec, including the fractured bone mask/root.
	if (!target || target->ID != ID() || getDestroy() || H_Parent() ||
		!PPhysicsShell() || !count || 37u + 8u * count >= NET_PacketSizeLimit)
		return false;
	Fvector angles;
	XFORM().getXYZ(angles);
	if (!_valid(Position()) || !_valid(angles)) return false;
	NET_Packet packet;
	packet.B.count = 0;
	CPHSkeleton::SaveNetState(packet);
	packet.r_seek(0);
	const u8 flags = packet.r_u8();
	// A pending split still references a live source and cannot be restored
	// independently. Normal Spawn clears this flag before checkpointing.
	if (flags & CSE_PHSkeleton::flSpawnCopy) return false;
	SPHBonesData bones;
	bones.net_Load(packet);
	if (!packet.r_eof() || bones.bones.size() != count) return false;
	target->saved_bones = bones;
	target->_flags.assign(flags);
	target->_flags.set(CSE_PHSkeleton::flSavedData, TRUE);
	target->o_Position = Position();
	target->o_Angle = angles;
	return true;
}

void CPhysicsSkeletonObject::net_Save(NET_Packet& P)
{
	inherited::net_Save(P);
	CPHSkeleton::SaveNetState(P);
}


BOOL CPhysicsSkeletonObject::net_SaveRelevant()
{
	return TRUE; //!m_flags.test(CSE_ALifeObjectPhysic::flSpawnCopy);
}


BOOL CPhysicsSkeletonObject::UsedAI_Locations()
{
	return (FALSE);
}

void CPhysicsSkeletonObject::UpdateCL()
{
	inherited::UpdateCL();
	PHObjectPositionUpdate();
}

void CPhysicsSkeletonObject::PHObjectPositionUpdate()
{
	if (m_pPhysicsShell)
	{
		m_pPhysicsShell->InterpolateGlobalTransform(&XFORM());
	}
}
