"""Generate the reviewable patch against the pinned NetAnomaly source; never build locally."""
import argparse
import difflib
from pathlib import Path


def generate(source: Path) -> str:
    originals, changed = {}, {}

    def read(name):
        if name not in originals:
            originals[name] = (source / name).read_bytes().decode("utf-8") .replace("\r\n", "\n")
            changed[name] = originals[name]
        return changed[name]

    def replace(name, old, new, count=1):
        text = read(name)
        if text.count(old) != count:
            raise ValueError(f"Source mismatch in {name}: expected {count} anchors, got {text.count(old)}")
        changed[name] = text.replace(old, new)

    server = "src/xrNetServer/NET_Server.cpp"
    replace(server, '#include "NET_Log.h"', '#include "NET_Log.h"\n#include "GammaNetPolicy.h"')
    replace(server, "if (data_size >= NET_PacketSizeLimit)", "if (!data || data_size < sizeof(u16) || data_size >= NET_PacketSizeLimit)")
    text = read(server)
    begin = text.index('\tif (strstr(options, "maxplayers="))')
    end = text.index('#ifdef DEBUG\n\tMsg("MaxPlayers', begin)
    changed[server] = text[:begin] + '\tdwMaxPlayers = gamma_net::player_limit(options);\n' + text[end:]
    # Old CRC semantics read beyond the compressed payload. Isolate this corrected protocol.
    replace(server, '0x218fa8b, 0x515b', '0x218fa8d, 0x515b')
    replace("src/xrNetServer/NET_Client.cpp", '0x218fa8b, 0x515b', '0x218fa8d, 0x515b')
    replace('src/xrNetServer/NET_Client.cpp',
            '\t\t\t\t\tPDPNMSG_CONNECT_COMPLETE pMsg = (PDPNMSG_CONNECT_COMPLETE)pMessage;',
            '\t\t\t\t\tPDPNMSG_CONNECT_COMPLETE pMsg = (PDPNMSG_CONNECT_COMPLETE)pMessage;\n\t\t\t\t\tif (SUCCEEDED(pMsg->hResultCode)) net_ClientID.set(pMsg->dpnidLocal);')
    replace('src/xrNetServer/NET_Client.cpp', '\tnet_Connected = EnmConnectionWait;\n\tnet_Syncronised = FALSE;\n}',
            '\tnet_Connected = EnmConnectionWait;\n\tnet_Syncronised = FALSE;\n\tnet_ClientID.set(0);\n}')
    replace("src/xrGame/game_sv_base.h", '#define MAX_PLAYERS_COUNT 32',
            '#include "../xrNetServer/GammaNetPolicy.h"\n#define MAX_PLAYERS_COUNT gamma_net::max_client_states')
    replace("src/xrGame/Spectator.cpp", 'CActor* PossiblePlayers[32];', 'CActor* PossiblePlayers[MAX_PLAYERS_COUNT];')
    replace("src/xrGame/Spectator.cpp", '\t\tPossiblePlayers[PPCount++] = A;',
            '\t\tif (PPCount >= MAX_PLAYERS_COUNT) break;\n\t\tPossiblePlayers[PPCount++] = A;')
    replace("src/xrGame/DemoInfo.cpp", 'm_players_count < MAX_PLAYERS_COUNT', 'm_players_count <= MAX_PLAYERS_COUNT')

    common = "src/xrNetServer/NET_Common.cpp"
    replace(common, '#include "NET_Common.h"', '#include "NET_Common.h"\n#include "GammaNetPolicy.h"')
    replace(common, '\tMultipacketHeader* header = (MultipacketHeader*)packet_data;\n\tu8 data[MaxMultipacketSize];', '''\tif (!packet_data || packet_sz <= sizeof(MultipacketHeader) || packet_sz > MaxMultipacketSize)
        return;
    MultipacketHeader header_value;
    CopyMemory(&header_value, packet_data, sizeof(header_value));
    const MultipacketHeader* header = &header_value;
    if (header->unpacked_size < sizeof(u16) || header->unpacked_size > MaxMultipacketSize)
        return;
    u8 data[MaxMultipacketSize];''')
    replace(common, '\tCompressor.Decompress(data, sizeof(data),', '\tconst u16 decoded = Compressor.Decompress(data, sizeof(data),')
    replace(common, '\n#if NET_LOG_PACKETS\n    Msg( "#receive multi-packet %u", packet_sz );', '''
    if (decoded != header->unpacked_size ||
        !gamma_net::valid_frame(data, decoded, header->tag == NET_TAG_MERGED, NET_PacketSizeLimit))
        return;

#if NET_LOG_PACKETS
    Msg( "#receive multi-packet %u", packet_sz );''')
    compressor = "src/xrNetServer/NET_Compressor.cpp"
    replace(compressor, 'crc32(dest + offset, compressed_size)', 'crc32(dest + offset, compressed_size - offset)')
    replace(compressor, '\tVERIFY(dest);\n\tVERIFY(src);\n\tVERIFY(count);',
            '\tif (!dest || !src || !count) return 0;', count=2)
    replace(compressor, '\tif (*src != NET_TAG_COMPRESSED)\n\t{',
            '\tif (*src != NET_TAG_COMPRESSED && *src != NET_TAG_NONCOMPRESSED) return 0;\n\tif (*src == NET_TAG_NONCOMPRESSED)\n\t{\n\t\tif (count - 1 > dest_size) return 0;')
    begin = read(compressor).index('\tu32 crc = crc32(src + offset, count);')
    end = read(compressor).index('#endif // NET_USE_COMPRESSION_CRC', begin)
    changed[compressor] = read(compressor)[:begin] + '''    if (count <= offset) return 0;
    u32 expected_crc;
    CopyMemory(&expected_crc, src + 1, sizeof(expected_crc));
    if (crc32(src + offset, count - offset) != expected_crc) return 0;
''' + read(compressor)[end:]
    replace(compressor, '\treturn (u16(uncompressed_size));',
            '\treturn uncompressed_size <= dest_size && uncompressed_size <= 65535 ? u16(uncompressed_size) : 0;')
    rtc = "src/xrCore/rt_compressor9.cpp"
    text = read(rtc)
    begin = text.index('rtc9_decompress(void*')
    tail = text[begin:].replace('lzo1x_decompress(', 'lzo1x_decompress_safe(').replace(
        '\tVERIFY(r == LZO_E_OK);', '\tif (r != LZO_E_OK) return 0;')
    changed[rtc] = text[:begin] + tail

    game = "src/xrGame/xrServer.cpp"
    replace(game, '#include <functional>', '#include <functional>\n#include "../xrNetServer/GammaNetPolicy.h"')
    replace('src/xrGame/xrServer.h', '\tBOOL net_PassUpdates;', '\tbool gamma_snapshot_ready;\n\tBOOL net_PassUpdates;')
    replace(game, '\tnet_PassUpdates = TRUE;', '\tgamma_snapshot_ready = false;\n\tnet_PassUpdates = TRUE;')
    replace(game, '\tVERIFY(xr_client);\n\tif (!xr_client->net_Ready)', '\tVERIFY(xr_client);\n\txr_client->gamma_snapshot_ready = false;\n\tif (!xr_client->net_Ready)')
    replace(game, '\tNET_Packet Packet;\n\tu16 PacketType = M_UPDATE;', '\txr_client->gamma_snapshot_ready = true;\n\tNET_Packet Packet;\n\tu16 PacketType = M_UPDATE;')
    replace(game, '\tif (IsGameTypeSingle())\n\t\treturn;\n\n\tKickCheaters();',
            '\tif (IsGameTypeSingle() && !strstr(Core.Params, "-netcoop"))\n\t\treturn;\n\tif (!GetServerClient()) return;\n\n\tKickCheaters();')
    replace(game, 'u32(1000 / psNET_ServerUpdate)', 'u32(1000 / (psNET_ServerUpdate > 0 ? psNET_ServerUpdate : 30))')
    # A broadcast bypasses per-client readiness and congested send queues.
    replace(game, '\t\t\tSendBroadcast(GetServerClient()->ID, to_send, net_flags(FALSE,TRUE));', '''            struct SnapshotSender
            {
                xrServer* server;
                NET_Packet* packet;
                void operator()(IClient* client)
                {
                    xrClientData* peer = static_cast<xrClientData*>(client);
                    if (client == server->GetServerClient() || !client->flags.bConnected || !peer->gamma_snapshot_ready)
                        return;
                    server->SendTo(client->ID, *packet, net_flags(FALSE, TRUE));
                }
            } send = {this, &to_send};
            ForEachClientDo(send);''')
    replace(game, '\tForEachClientDoSender(sendtofd);\n\n\tif ((Device.dwTimeGlobal', '\n\tif ((Device.dwTimeGlobal')
    replace(game, '\t\tMakeUpdatePackets();', '\t\tForEachClientDoSender(sendtofd);\n\t\tMakeUpdatePackets();')
    replace(server, '(dwTime - C->dwTime_LastUpdate) > dwInterval', '(dwTime - C->dwTime_LastUpdate) >= dwInterval')
    replace(game, 'u32 xrServer::OnMessage(NET_Packet& P, ClientID sender) // Non-Zero means broadcasting with "flags" as returned\n{',
            'u32 xrServer::OnMessage(NET_Packet& P, ClientID sender) // Non-Zero means broadcasting with "flags" as returned\n{\n\tif (P.B.count < sizeof(u16)) return 0;')
    replace(game, 'u32 xrServer::OnDelayedMessage(NET_Packet& P, ClientID sender) // Non-Zero means broadcasting with "flags" as returned\n{',
            'u32 xrServer::OnDelayedMessage(NET_Packet& P, ClientID sender) // Non-Zero means broadcasting with "flags" as returned\n{\n\tif (P.B.count < sizeof(u16) || !ID_to_client(sender)) return 0;')
    replace(game, '\t\t\tm_file_transfers->on_message(&P, sender);', '\t\t\tif (m_file_transfers) m_file_transfers->on_message(&P, sender);')
    marker = '\txrClientData* CL = ID_to_client(sender);\n\n\tswitch (type)'
    # Delayed messages have the same lookup but intervening comments; only OnMessage matches.
    replace(game, marker, '''\txrClientData* CL = ID_to_client(sender);
    if (!CL) return 0;
    if (!CL->flags.bLocal)
    {
        switch (type)
        {
        case M_UPDATE: case M_SPAWN: case M_SAVE_GAME: case M_SAVE_PACKET:
        case M_LOAD_GAME: case M_RELOAD_GAME: case M_CHANGE_LEVEL:
        case M_CHANGE_LEVEL_GAME: case M_SWITCH_DISTANCE:
            return 0; // Only the authoritative ALife host can mutate global world state.
        default: break;
        }
    }

\tswitch (type)''')
    replace(game, '\t\t\t\ttmpP.B.count = P.r_u8();\n\t\t\t\tP.r(&tmpP.B.data, tmpP.B.count);', '''                tmpP.B.count = P.r_u8();
                if (tmpP.B.count < sizeof(u16) || tmpP.B.count > P.B.count - P.r_tell()) break;
                P.r(&tmpP.B.data, tmpP.B.count);
                u16 nested_type;
                CopyMemory(&nested_type, tmpP.B.data, sizeof(nested_type));
                if (nested_type == M_EVENT_PACK) break; // No recursive packs / stack exhaustion.''')
    replace(game, '\t\t\tif (!CL->net_PassUpdates)\n\t\t\t\tbreak;', '''            if (!CL->net_PassUpdates || !CL->owner || P.B.count < 8) break;
            u16 object_id;
            CopyMemory(&object_id, P.B.data + 2, sizeof(object_id));
            if (object_id != CL->owner->ID) break; // A client may update only its own actor.
            if (IsGameTypeSingle() && strstr(Core.Params, "-netcoop") &&
                !gamma_net::valid_coop_actor(P.B.data + 8, P.B.count - 8)) break;''')
    # Do not accumulate obsolete movement packets behind reliable retransmissions.
    replace(game, '\t\t\tif (SV_Client)\n\t\t\t\tSendTo(SV_Client->ID, P, net_flags(TRUE, TRUE));',
            '\t\t\tif (SV_Client)\n\t\t\t\tSendTo(SV_Client->ID, P, net_flags(FALSE, TRUE));')
    replace(game, '\tcase M_CL_INPUT:\n\t\t{', '''\tcase M_CL_INPUT:
        {
            if (!CL->owner || P.B.count < 4) break;
            u16 object_id;
            CopyMemory(&object_id, P.B.data + 2, sizeof(object_id));
            if (object_id != CL->owner->ID) break;''')
    # The inherited command channel stores plaintext passwords, auto-admins the first user,
    # invokes Lua from network callbacks and logs credentials. Disable remote commands.
    replace(game, '\tcase M_NETANOMALY_CMD:\n\t\t{', '\tcase M_NETANOMALY_CMD:\n\t\t{\n\t\t\tif (!CL->flags.bLocal) break;\n\t\t\tif (P.B.count < 3 || P.B.count > 4098 || !memchr(P.B.data + 2, 0, P.B.count - 2)) break;')
    replace(game, '\t\t\tMsg("[NetAnomaly] cmd from [%s] 0x%s eid=%d : %s", na_name, na_cid, na_eid, na_text);',
            '\t\t\tMsg("[NetAnomaly] local command from [%s] eid=%d", na_name, na_eid);')
    replace(game, '\tif (CL->process_id == GetCurrentProcessId())',
            '\tif (CL->process_id == GetCurrentProcessId() && CL->ID == Level().GetClientID())')

    level = "src/xrGame/Level_network.cpp"
    replace(level, 'if (g_tutorial2 && !g_tutorial->Persistent())', 'if (g_tutorial2 && !g_tutorial2->Persistent())')
    replace(level, 'if (GameID() != eGameIDSingle && OnClient())',
            'if ((GameID() != eGameIDSingle || strstr(Core.Params, "-netcoop")) && OnClient())')
    actor = "src/xrGame/Actor_Network.cpp"
    replace(actor, '#include "pch_script.h"', '#include "pch_script.h"\n#include "../xrNetServer/GammaNetPolicy.h"')
    replace(actor, 'H_Parent() || (GameID() == eGameIDSingle) || ((NumItems > 1) && OnClient())',
            'H_Parent() || (GameID() == eGameIDSingle && !strstr(Core.Params, "-netcoop")) || (NumItems > 1)')
    replace(actor, '\tif (OnServer())\n\t{\n\t\tE->s_flags.set(M_SPAWN_OBJECT_LOCAL, TRUE);',
            '\tif (OnServer() && !strstr(Core.Params, "-netcoop"))\n\t{\n\t\tE->s_flags.set(M_SPAWN_OBJECT_LOCAL, TRUE);')
    replace(actor, 'N.dwTimeStamp < NET.back().dwTimeStamp',
            'N.dwTimeStamp != NET.back().dwTimeStamp && !gamma_net::newer(N.dwTimeStamp, NET.back().dwTimeStamp)')
    replace(actor, 'N_A.dwTimeStamp < NET_A.back().dwTimeStamp',
            'N_A.dwTimeStamp != NET_A.back().dwTimeStamp && !gamma_net::newer(N_A.dwTimeStamp, NET_A.back().dwTimeStamp)')
    replace(actor, '\tif (!IsGameTypeSingle())\n\t{\n\t\tsetEnabled(TRUE);',
            '\tif (!IsGameTypeSingle() || strstr(Core.Params, "-netcoop"))\n\t{\n\t\tsetEnabled(TRUE);')
    replace(actor, '\t\treturn getSVU() | getLocal();',
            '\t\treturn (strstr(Core.Params, "-netcoop") != NULL) || getSVU() || getLocal();')
    single = "src/xrGame/game_sv_single.cpp"
    replace(single, '\tif (CL->process_id == GetCurrentProcessId())', '\tif (CL->flags.bLocal)')
    replace(single, '\t\tMsg("! [NetAnomaly] section [actor] is not an actor entity");\n\t\treturn;',
            '\t\tMsg("! [NetAnomaly] section [actor] is not an actor entity");\n\t\tF_entity_Destroy(E);\n\t\treturn;')
    # spawn_end can destroy the temporary spawn descriptor: log the saved position instead.
    replace(single, 'A->o_Position.x, A->o_Position.y, A->o_Position.z);', 'pos.x, pos.y, pos.z);')
    cl_single = "src/xrGame/game_cl_single.cpp"
    replace(cl_single, '\tActor()->OnDifficultyChanged();', '\tif (Actor()) Actor()->OnDifficultyChanged();')
    replace(cl_single, '\tLevel().Server->game->SetGameTimeFactor(fTimeFactor);',
            '\tif (Level().Server) { Level().Server->game->SetGameTimeFactor(fTimeFactor); }', count=2)

    return ''.join(''.join(difflib.unified_diff(originals[n].splitlines(True), changed[n].splitlines(True),
                                              fromfile='a/' + n, tofile='b/' + n))
                   for n in sorted(changed) if originals[n] != changed[n])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(generate(args.source), encoding='utf-8', newline='\n')
