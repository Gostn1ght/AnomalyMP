#pragma once
#include "physicsexternalcommon.h"

class IPHStaticGeomShell
{
protected:
	virtual ~IPHStaticGeomShell() =0
	{
	}

	//	virtual void						set_ObjectContactCallback	(ObjectContactCallbackFun* callback);											
};

class IPhysicsShellHolder;
class IClimableObject;
XRPHYSICS_API IPHStaticGeomShell* P_BuildStaticGeomShell(IPhysicsShellHolder* obj,
                                                         ObjectContactCallbackFun* object_contact_callback);
XRPHYSICS_API IPHStaticGeomShell* P_BuildLeaderGeomShell(IClimableObject* obj, ObjectContactCallbackFun* callback,
                                                         const Fobb& b);
XRPHYSICS_API void DestroyStaticGeomShell(IPHStaticGeomShell* & p);
// A fixed box (in the object's local space) that characters collide with.
XRPHYSICS_API IPHStaticGeomShell* P_BuildStaticGeomShellBox(IPhysicsShellHolder* obj,
                                                            ObjectContactCallbackFun* object_contact_callback, const Fobb& b);

//CPHStaticGeomShell* P_BuildStaticGeomShell(CGameObject* obj,ObjectContactCallbackFun* object_contact_callback,Fobb &b);
//void				P_BuildStaticGeomShell(CPHStaticGeomShell* shell,CGameObject* obj,ObjectContactCallbackFun* object_contact_callback,Fobb &b);
