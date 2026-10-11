#include "stdafx.h"
#include "xrServer.h"
#include "xrServer_Objects.h"

int g_Dump_Update_Read = 0;

void xrServer::Process_update(NET_Packet& P, ClientID sender)
{
	xrClientData* CL = ID_to_client(sender);
	R_ASSERT2(CL, "Process_update client not found");

#ifndef MASTER_GOLD
	if (g_Dump_Update_Read) Msg("---- UPDATE_Read --- ");
#endif // #ifndef MASTER_GOLD

	R_ASSERT(CL->flags.bLocal);
	// while has information
	while (!P.r_eof())
	{
		// find entity
		u16 ID;
		u8 size;

		P.r_u16(ID);
		P.r_u8(size);
		u32 _pos = P.r_tell();
		CSE_Abstract* E = ID_to_entity(ID);

		if (E)
		{
			//Msg				("sv_import: %d '%s'",E->ID,E->name_replace());
			E->net_Ready = TRUE;
			R_ASSERT2(_pos + size <= P.B.count, "update chunk exceeds its packet");
			// Each entity reads exactly its own chunk. Optional trailing fields are
			// detected with r_elapsed(), which on the shared packet also counted
			// the next entities' bytes; a newer sender's extra fields (the stalker
			// body yaw/torso look, 2026-10-09) stopped every dedicated server here.
			static thread_local NET_Packet own;
			own.construct(&P.B.data[_pos], size);
			own.r_pos = 0;
			own.timeReceive = P.timeReceive;
			E->UPDATE_Read(own);
			const u32 used = own.r_pos;
			P.r_advance(size);

			if (g_Dump_Update_Read) Msg("* %s : %d - %d", E->name(), size, used);

			if (used < size)
			{
				static u32 warned = 0;
				if (warned++ < 8)
					Msg("! update of %s [%d] left %u trailing byte(s) unread (newer sender)", E->name(), E->ID, size - used);
			}
			else if (used != size)
			{
				string16 tmp;
				CLSID2TEXT(E->m_tClassID, tmp);
				Debug.fatal(DEBUG_INFO,
				            "Beer from the creator of '%s'; initiator: 0x%08x, r_tell() = %d, pos = %d, objectID = %d, size = %d",
				            tmp,
				            CL->ID.value(),
				            _pos + used,
				            _pos,
				            E->ID,
							size
				);
			}
		}
		else
			P.r_advance(size);
	}
#ifndef MASTER_GOLD
	if (g_Dump_Update_Read) Msg("-------------------- ");
#endif // #ifndef MASTER_GOLD
}

void xrServer::Process_save(NET_Packet& P, ClientID sender)
{
	xrClientData* CL = ID_to_client(sender);
	R_ASSERT2(CL, "Process_save client not found");
	CL->net_Ready = TRUE;

	R_ASSERT(CL->flags.bLocal);
	// while has information
	while (!P.r_eof())
	{
		// find entity
		u16 ID;
		u16 size;

		P.r_u16(ID);
		P.r_u16(size);
		s32 _pos_start = P.r_tell();
		CSE_Abstract* E = ID_to_entity(ID);

		if (E)
		{
			E->net_Ready = TRUE;
			E->load(P);
		}
		else
			P.r_advance(size);
		s32 _pos_end = P.r_tell();
		s32 _size = size;
		if (_size != (_pos_end - _pos_start))
		{
			Msg("! load/save mismatch, object: '%s'", E ? E->name_replace() : "unknown");
			s32 _rollback = _pos_start + _size;
			P.r_seek(_rollback);
		}
	}
}
