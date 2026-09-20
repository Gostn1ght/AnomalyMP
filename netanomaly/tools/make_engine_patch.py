"""Generate the reviewable patch against the pinned NetAnomaly source; builds run in GitHub Actions only."""
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

    # Legacy PvP dedicated servers skip Lua/AI entirely. Coop ALife needs both.
    replace('src/xrGame/ai_space.cpp', '\tif (g_dedicated_server)\n\t\treturn;',
            '\tif (g_dedicated_server && !strstr(Core.Params, "-netcoop"))\n\t\treturn;', count=4)
    replace('src/xrGame/ai_space.h', '\tIC CScriptEngine& script_engine() const;',
            '\tIC CScriptEngine& script_engine() const;\n\tCScriptEngine* get_script_engine() const { return m_script_engine; }')
    replace('src/xrGame/console_commands.cpp',
            '\tsize_t lua_mem = lua_gc(ai().script_engine().lua(), LUA_GCCOUNT, 0);',
            '''    // Diagnostics can run before AI startup or during teardown.
    auto* scripts = g_ai_space ? g_ai_space->get_script_engine() : nullptr;
    size_t lua_mem = scripts && scripts->lua() ? lua_gc(scripts->lua(), LUA_GCCOUNT, 0) : 0;''')
    replace('src/xrServerEntities/script_engine.cpp', '\tai().script_engine().print_stack();',
            '\tif (g_ai_space && g_ai_space->get_script_engine()) g_ai_space->get_script_engine()->print_stack();', count=4)
    replace('src/xrServerEntities/script_storage.cpp', '\tlua_State* L = lua();\n\tlua_Debug l_tDebugInfo;',
            '\tlua_State* L = lua();\n\tif (!L) return;\n\tlua_Debug l_tDebugInfo;')
    startup = 'src/xrEngine/x_ray.cpp'
    replace(startup, '''#ifdef DEDICATED_SERVER
    {
        Console = xr_new<CTextConsole>();
    }
#else
\t// else
\t{
\t\tConsole = xr_new<CConsole>();
\t}
#endif''', '''    // Runtime -dedicated uses the same native GDI console as the dedicated build.
    // CConsole's DX shader resources do not exist in dedicated mode.
    if (g_dedicated_server)
        Console = xr_new<CTextConsole>();
    else
        Console = xr_new<CConsole>();''')
    device = 'src/xrEngine/device.cpp'
    replace(device, 'BOOL CRenderDevice::Begin()\n{',
            'BOOL CRenderDevice::Begin()\n{\n\tif (g_dedicated_server) return TRUE;')
    replace(device, 'void CRenderDevice::End(void)\n{',
            'void CRenderDevice::End(void)\n{\n\tif (g_dedicated_server) return;')
    replace(device, 'void CRenderDevice::Clear()\n{',
            'void CRenderDevice::Clear()\n{\n\tif (g_dedicated_server) return;')
    replace(device, 'void CRenderDevice::PreCache(u32 amount, bool b_draw_loadscreen, bool b_wait_user_input)\n{',
            'void CRenderDevice::PreCache(u32 amount, bool b_draw_loadscreen, bool b_wait_user_input)\n{\n\tif (g_dedicated_server) amount = 0;')
    replace(device, '\tif (b_is_Active && Begin())', '\tif (!g_dedicated_server && b_is_Active && Begin())')
    replace('src/xrEngine/xr_ioc_cmd.h', '''\t\tI[0] = 0;
\t\txr_token* tok = tokens;
\t\tfor (int Iter = 0;; Iter++)''', '''\t\tI[0] = 0;
\t\txr_token* tok = tokens;
            if (!tok)
            {
                xr_strcpy(I, "unavailable");
                return;
            }
\t\tfor (int Iter = 0;; Iter++)''')

    # GAMMA scripts cache font handles while Lua modules are loading. Dedicated
    # mode has no UI/font manager, so expose nil instead of dereferencing it.
    ui_window = 'src/xrGame/ui/UIWindow_script.cpp'
    replace(ui_window, '#include "UITrackBar.h"',
            '#include "UITrackBar.h"\n\nextern ENGINE_API bool g_dedicated_server;')
    for font in (
        'pFontStat', 'pFontMedium', 'pFontDI', 'pFontGraffiti19Russian',
        'pFontGraffiti22Russian', 'pFontLetterica16Russian',
        'pFontLetterica18Russian', 'pFontGraffiti32Russian',
        'pFontGraffiti50Russian', 'pFontLetterica25',
    ):
        replace(ui_window, f'\treturn mngr().{font};',
                f'\treturn g_dedicated_server ? nullptr : mngr().{font};')

    # ALife dedicated servers still need logical managers and script scheduling.
    level_source = 'src/xrGame/Level.cpp'
    for anchor in (
        '    if (!g_dedicated_server)\n    {\n        m_map_manager',
        '    if (!g_dedicated_server)\n    {\n        m_level_sound_manager',
        '    if (!g_dedicated_server)\n        ai().script_engine().remove_script_process',
        '\tif (!g_dedicated_server)\n\t{\n\t\tif (g_mt_config.test(mtMap))',
        '\tif (!g_dedicated_server)\n\t\tai().script_engine().script_process',
        '\tif (!g_dedicated_server)\n\t{\n\t\tif (g_mt_config.test(mtLUA_GC))',
    ):
        replace(level_source, anchor, anchor.replace('!g_dedicated_server', '!g_dedicated_server || strstr(Core.Params, "-netcoop")'))
    replace('src/xrGame/Level_load.cpp', '\tif (!g_dedicated_server)\n\t{\n\t\t// loading scripts',
            '\tif (!g_dedicated_server || strstr(Core.Params, "-netcoop"))\n\t{\n\t\t// loading scripts')
    replace('src/xrGame/Level_load.cpp', '''\tif (GamePersistent().GameType() == eGameIDSingle && !ai().get_alife() && FS.exist(fn_game, "$level$", "level.ai") &&
\t\t!net_Hosts.empty())''', '''\tif (GamePersistent().GameType() == eGameIDSingle && !ai().get_alife() && FS.exist(fn_game, "$level$", "level.ai") &&
\t\t(!net_Hosts.empty() || strstr(Core.Params, "-netcoop")))''')

    # A dedicated authority and a joining peer both spend part of startup with
    # no local actor. Stock single-player background code assumes Actor() and
    # CurrentEntity() always exist; make those paths wait or use neutral data.
    replace('src/xrGame/Entity.cpp',
            '\tif (IsGameTypeSingle() && (this->ID() == Actor()->ID()) && (bypass_actor_check != TRUE))',
            '\tif (IsGameTypeSingle() && Actor() && (this->ID() == Actor()->ID()) && (bypass_actor_check != TRUE))')
    replace('src/xrGame/ai/monsters/basemonster/base_monster.cpp',
            '\t\t\t\tif (Actor()->Position().distance_to(Position()) > db().m_fDistantIdleSndRange)',
            '\t\t\t\tif (Actor() && Actor()->Position().distance_to(Position()) > db().m_fDistantIdleSndRange)')
    replace('src/xrGame/ai/trader/ai_trader.cpp', 'void CAI_Trader::LookAtActor(CBoneInstance* B)\n{',
            'void CAI_Trader::LookAtActor(CBoneInstance* B)\n{\n\tif (!Level().CurrentEntity()) return;')
    crow = 'src/xrGame/ai/crow/ai_crow.cpp'
    replace(crow, '\t\t\tLevel().ObjectSpace.GetNearest(nearbyObjects, Position(), 300.0f, NULL);',
            '\t\t\tnearbyObjects.clear();\n\t\t\tdeadNPCs.clear();\n\t\t\tLevel().ObjectSpace.GetNearest(nearbyObjects, Position(), 300.0f, NULL);')
    replace(crow, '\t\t\telse \n\t\t\t{\n\t\t\t\tvP = Actor()->Position();\n'
            '\t\t\t\tfloat distanceToActor = Position().distance_to(vP);\n'
            '\t\t\t\tif (distanceToActor > 500.0f) \n\t\t\t\t{\n'
            '\t\t\t\t\tfGoalChangeTime = 30.0f;\n\t\t\t\t}\n\t\t\t}', '''\t\t\telse if (Actor())
\t\t\t{
\t\t\t\tvP = Actor()->Position();
\t\t\t\tfloat distanceToActor = Position().distance_to(vP);
\t\t\t\tif (distanceToActor > 500.0f)
\t\t\t\t\tfGoalChangeTime = 30.0f;
\t\t\t}
\t\t\telse
\t\t\t{
\t\t\t\t// Keep server-side crows active without targeting a missing player.
\t\t\t\tvP.mad(Position(), Direction(), 50.0f);
\t\t\t}''')
    replace(crow, '\t\t\tdest_dir.sub(Actor()->Position(), Position());',
            '\t\t\tdest_dir.sub(vP, Position());')

    task = 'src/xrGame/GameTask.cpp'
    replace(task, '\tActor()->callback(GameObject::eTaskStateChange)(this, GetTaskState());',
            '\tif (Actor()) Actor()->callback(GameObject::eTaskStateChange)(this, GetTaskState());')
    replace(task, '''bool CGameTask::CheckInfo(const xr_vector<shared_str>& v) const
{''', '''bool CGameTask::CheckInfo(const xr_vector<shared_str>& v) const
{
\tif (!v.empty() && !Actor()) return false;''')
    replace(task, '''void CGameTask::SendInfo(const xr_vector<shared_str>& v)
{''', '''void CGameTask::SendInfo(const xr_vector<shared_str>& v)
{
\tif (!Actor()) return;''')
    phrase = 'src/xrGame/PhraseScript.cpp'
    replace(phrase, '''bool CDialogScriptHelper::CheckInfo(const CInventoryOwner* pOwner) const
{
\tTHROW(pOwner);''', '''bool CDialogScriptHelper::CheckInfo(const CInventoryOwner* pOwner) const
{
\tTHROW(pOwner);
\tif ((!m_HasInfo.empty() || !m_DontHasInfo.empty()) && !Actor()) return false;''')
    replace(phrase, '''void CDialogScriptHelper::TransferInfo(const CInventoryOwner* pOwner) const
{
\tTHROW(pOwner);''', '''void CDialogScriptHelper::TransferInfo(const CInventoryOwner* pOwner) const
{
\tTHROW(pOwner);
\tif (!Actor()) return;''')

    inventory = 'src/xrGame/Inventory.cpp'
    replace(inventory, '''\tif (smart_cast<CWeapon*>(pObj))
\t{
\t\tFvector dir = Actor()->Direction();
\t\tdir.y = sin(-45.f * PI / 180.f);
\t\tdir.normalize();
\t\tsmart_cast<CWeapon*>(pObj)->SetActivationSpeedOverride(dir.mul(7));''', '''\tif (smart_cast<CWeapon*>(pObj))
\t{
\t\tif (Actor())
\t\t{
\t\t\tFvector dir = Actor()->Direction();
\t\t\tdir.y = sin(-45.f * PI / 180.f);
\t\t\tdir.normalize();
\t\t\tsmart_cast<CWeapon*>(pObj)->SetActivationSpeedOverride(dir.mul(7));
\t\t}''')
    replace(inventory, '\tif (Actor()->m_inventory == this)', '\tif (Actor() && Actor()->m_inventory == this)')
    replace(inventory, '''\t\tif (pItemToEat->IsUsingCondition() && pItemToEat->GetRemainingUses() < 1 && pItemToEat->CanDelete())
\t\t\tCurrentGameUI()->GetActorMenu().RefreshCurrentItemCell();

\t\tCurrentGameUI()->GetActorMenu().SetCurrentItem(NULL);''', '''\t\tif (CurrentGameUI())
\t\t{
\t\t\tif (pItemToEat->IsUsingCondition() && pItemToEat->GetRemainingUses() < 1 && pItemToEat->CanDelete())
\t\t\t\tCurrentGameUI()->GetActorMenu().RefreshCurrentItemCell();
\t\t\tCurrentGameUI()->GetActorMenu().SetCurrentItem(NULL);
\t\t}''')
    replace('src/xrGame/InventoryBox.cpp', '\t\t\tif (m_in_use)\n\t\t\t{',
            '\t\t\tif (m_in_use && Actor())\n\t\t\t{')

    map_location = 'src/xrGame/map_location.cpp'
    replace(map_location, '''\telse if (Level().name() == map->MapName() && GetSpotPointer(sp))
\t{''', '''\telse if (Level().name() == map->MapName() && GetSpotPointer(sp))
\t{
\t\tif (!Actor()) return;''')
    replace(map_location, '''void CMapLocation::UpdateSpotPointer(CUICustomMap* map, CMapSpotPointer* sp)
{''', '''void CMapLocation::UpdateSpotPointer(CUICustomMap* map, CMapSpotPointer* sp)
{
\tif (!Level().CurrentEntity()) return;''')
    replace(map_location, '''\t\t\t\tCActor* pAct = smart_cast<CActor*>(Level().Objects.net_Find(m_pInvOwnerActorID));
\t\t\t\tCHelmet* helm''', '''\t\t\t\tCActor* pAct = smart_cast<CActor*>(Level().Objects.net_Find(m_pInvOwnerActorID));
\t\t\t\tif (!pAct || !pObj) return false;
\t\t\t\tCHelmet* helm''')
    replace(map_location, 'Actor()->memory().visual().visible_now(pObj)',
            'pAct->memory().visual().visible_now(pObj)', count=2)
    replace(map_location, '''\t\t\tCActor* pAct = smart_cast<CActor*>(Level().Objects.net_Find(m_pInvOwnerActorID));
\t\t\tif (/*pAct->Position()''', '''\t\t\tCActor* pAct = smart_cast<CActor*>(Level().Objects.net_Find(m_pInvOwnerActorID));
\t\t\tif (!pAct || !pObj) return false;
\t\t\tif (/*pAct->Position()''')
    replace('src/xrGame/Level_network_spawn.cpp', '\t\tif (!g_dedicated_server)\n\t\t\tclient_spawn_manager()',
            '\t\tif (!g_dedicated_server || strstr(Core.Params, "-netcoop"))\n\t\t\tclient_spawn_manager()', count=2)
    game_object = 'src/xrGame/GameObject.cpp'
    replace(game_object, 'm_ai_location = !g_dedicated_server ? xr_new<CAI_ObjectLocation>() : 0;',
            'm_ai_location = (!g_dedicated_server || strstr(Core.Params, "-netcoop")) ? xr_new<CAI_ObjectLocation>() : 0;')
    for call in ('ai_location().reinit();', 'CScriptBinder::reload(*cNameSect());',
                 'CScriptBinder::reinit();', 'CScriptBinder::shedule_Update(dt);'):
        replace(game_object, '\tif (!g_dedicated_server)\n\t\t' + call,
                '\tif (!g_dedicated_server || strstr(Core.Params, "-netcoop"))\n\t\t' + call)
    binder = 'src/xrGame/script_binder.cpp'
    replace(binder, '#include "gameobject.h"', '#include "gameobject.h"\n#include "Actor.h"')
    replace(binder, 'void CScriptBinder::reload(LPCSTR section)\n{', '''void CScriptBinder::reload(LPCSTR section)
{
    if (strstr(Core.Params, "-netcoop"))
    {
        // Reject before invoking the Lua constructor: actor_binder constructors
        // themselves modify singleton db.actor_binder, even if set_object rejects them.
        if (!strstr(Core.Params, "server(")) return;
        CActor* actor = smart_cast<CActor*>(this);
        if (actor && !actor->Local()) return;
    }''')

    server = "src/xrNetServer/NET_Server.cpp"
    replace(server, '#include "NET_Log.h"', '#include "NET_Log.h"\n#include "GammaNetPolicy.h"')
    replace(server, "if (data_size >= NET_PacketSizeLimit)", "if (!data || data_size < sizeof(u16) || data_size >= NET_PacketSizeLimit)")
    text = read(server)
    begin = text.index('\tif (strstr(options, "maxplayers="))')
    end = text.index('#ifdef DEBUG\n\tMsg("MaxPlayers', begin)
    changed[server] = text[:begin] + '\tdwMaxPlayers = gamma_net::player_limit(options);\n' + text[end:]
    # Old CRC semantics read beyond the compressed payload. Isolate this corrected protocol.
    replace(server, '0x218fa8b, 0x515b', '0x218fa8e, 0x515b')
    replace("src/xrNetServer/NET_Client.cpp", '0x218fa8b, 0x515b', '0x218fa8e, 0x515b')
    replace('src/xrNetServer/NET_Server.h', '\tu32 process_id;\n\n\tSClientConnectData()',
            '\tu32 process_id;\n\tchar gamma_ticket[65];\n\tchar gamma_content[65];\n\n\tSClientConnectData()')
    replace('src/xrNetServer/NET_Server.h', '\t\tprocess_id = 0;',
            '\t\tprocess_id = 0;\n\t\tgamma_ticket[0] = gamma_content[0] = 0;')
    replace('src/xrNetServer/NET_Client.cpp', '#include "NET_Log.h"',
            '#include "NET_Log.h"\n#include "GammaPeerAuth.h"')
    replace('src/xrNetServer/NET_Client.cpp', '\t\t\txr_strcpy(cl_data.pass, user_pass);', '''\t\t\txr_strcpy(cl_data.pass, user_pass);
            if (strstr(Core.Params, "-netcoop"))
            {
                string_path file;
                FS.update_path(file, "$app_data_root$", "gamma_ticket.txt");
                const auto ticket = gamma_net::read_client_ticket(file);
                xr_strcpy(cl_data.gamma_ticket, ticket.c_str());
                FS.update_path(file, "$game_config$", "gamma_net_role.ltx");
                if (FS.exist(file))
                {
                    CInifile configuration(file);
                    if (configuration.line_exist("network", "content_sha256"))
                    {
                        const std::string content = configuration.r_string("network", "content_sha256");
                        if (gamma_net::hex_identity(content, 64))
                            xr_strcpy(cl_data.gamma_content, content.c_str());
                    }
                }
            }''')
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
    replace(game, '#include <functional>', '#include <functional>\n#include "../xrNetServer/GammaNetPolicy.h"\n#include "../xrNetServer/GammaPeerAuth.h"')
    replace('src/xrGame/xrServer.h', '\tBOOL net_Accepted;', '\tbool GammaIsAdmin() const;\n\tBOOL net_Accepted;')
    replace(game, 'void xrClientData::Clear()', '''bool xrClientData::GammaIsAdmin() const
{
    if (!gamma_authenticated) return false;
    string_path roles;
    FS.update_path(roles, "$app_data_root$", "account_roles\\\\");
    return gamma_net::account_is_admin(roles, *gamma_account);
}

void xrClientData::Clear()''')
    replace('src/xrGame/xrServer.h', '#include "xrClientsPool.h"', '#include "xrClientsPool.h"\n#include <atomic>')
    replace('src/xrGame/xrServer.h', '\tBOOL net_Accepted;',
            '\tBOOL net_Accepted;\n\tu32 gamma_role_checked_at;\n\tstd::atomic<bool> gamma_authenticated;\n\tshared_str gamma_account;\n\tshared_str gamma_ticket;\n\tshared_str gamma_content;')
    replace(game, '\tnet_Accepted = FALSE;',
            '\tnet_Accepted = FALSE;\n\tgamma_role_checked_at = 0;\n\tgamma_authenticated = false;\n\tgamma_account = "";\n\tgamma_ticket = "";\n\tgamma_content = "";')
    replace(game, '''\t\tif (pOwner)
\t\t{
\t\t\tgame->CleanDelayedEventFor(pOwner->ID);
\t\t}''', '''        if (pOwner)
        {
            game->CleanDelayedEventFor(pOwner->ID);
            // Stock single-player only removes spectators on disconnect. A remote
            // netcoop actor would otherwise remain as a ghost with its inventory.
            // The transport has already removed this peer. Use the explicit
            // server cleanup path; packet-driven destruction still checks ownership.
            if (strstr(Core.Params, "-netcoop") && !alife_client->flags.bLocal && !pS)
            {
                NET_Packet destroy;
                destroy.w_begin(M_EVENT);
                destroy.w_u32(Level().timeServer());
                destroy.w_u16(GE_DESTROY);
                destroy.w_u16(pOwner->ID);
                u16 ignored;
                destroy.r_begin(ignored);
                Process_event_destroy(destroy, alife_client->ID, Level().timeServer(), pOwner->ID, NULL, true);
                pOwner = NULL;
            }
        }''')
    replace('src/xrGame/xrServer.h', 'void Process_event_destroy(NET_Packet& P, ClientID sender, u32 time, u16 ID, NET_Packet* pEPack);',
            'void Process_event_destroy(NET_Packet& P, ClientID sender, u32 time, u16 ID, NET_Packet* pEPack, bool disconnected_cleanup = false);')
    destroy_source = 'src/xrGame/xrServer_process_event_destroy.cpp'
    replace(destroy_source, 'NET_Packet* pEPack)\n{', 'NET_Packet* pEPack, bool disconnected_cleanup)\n{')
    replace(destroy_source, '\tR_ASSERT(c_dest == c_from); // assure client ownership of event',
            '\tR_ASSERT(disconnected_cleanup || c_dest == c_from); // Cleanup originates only in client_Destroy, never a packet.')
    replace(destroy_source, 'Process_event_destroy(P, sender, time, *e_dest->children.begin(), pEventPack);',
            'Process_event_destroy(P, sender, time, *e_dest->children.begin(), pEventPack, disconnected_cleanup);')
    replace('src/xrGame/xrServer_Connect.cpp', '\tCL->pass._set(cl_data->pass);', '''\tCL->pass._set(cl_data->pass);
    cl_data->gamma_ticket[64] = cl_data->gamma_content[64] = 0;
    xrClientData* gamma_client = static_cast<xrClientData*>(CL);
    gamma_client->gamma_ticket = cl_data->gamma_ticket;
    gamma_client->gamma_content = cl_data->gamma_content;''')
    replace('src/xrGame/xrServer.h', '\tBOOL net_PassUpdates;', '\tbool gamma_snapshot_ready;\n\tBOOL net_PassUpdates;')
    replace('src/xrGame/xrServer_CL_connect.cpp',
            '\tP.w_stringZ(Level().m_caServerOptions);', '''\tP.w_stringZ(Level().m_caServerOptions);
    if (strstr(Core.Params, "-netcoop"))
    {
        const shared_str actual_level = game->level_name(Level().m_caServerOptions);
        const shared_str actual_version = level_version(Level().m_caServerOptions);
        P.w_stringZ(actual_level);
        P.w_stringZ(actual_version);
    }''')
    replace('src/xrGame/xrServer_CL_connect.cpp', '\tCL->net_Accepted = TRUE;', '''\tCL->net_Accepted = TRUE;
    if (strstr(Core.Params, "-netcoop") && !CL->ps)
    {
        // A remote single-player client requests world data before sending the
        // multiplayer CREATE_PLAYER_STATE event. Create an empty authoritative
        // state now so export, account auth, and actor ownership have one record.
        CL->ps = game->createPlayerState(nullptr);
        CL->ps->resetFlag(GAME_PLAYER_FLAG_SKIP);
        CL->ps->resetFlag(GAME_PLAYER_HAS_ADMIN_RIGHTS);
        CL->ps->m_account.set_player_name(CL->name.c_str());
        CL->ps->m_online_time = Level().timeServer();
        CL->ps->DeathTime = Device.dwTimeGlobal;
    }''')
    replace('src/xrGame/Level_network.cpp', '\tSetClientID(tmp_client_id);', '''\tSetClientID(tmp_client_id);
    if (result && strstr(Core.Params, "-netcoop"))
    {
        P->r_u8(); // server-client flag
        shared_str server_options, actual_level, actual_version;
        P->r_stringZ(server_options);
        P->r_stringZ(actual_level);
        P->r_stringZ(actual_version);
        m_caServerOptions = server_options;
        xr_strcpy(m_game_description.map_name, actual_level.c_str());
        xr_strcpy(m_game_description.map_version, actual_version.c_str());
        Msg("[NetAnomaly] server level %s version %s", actual_level.c_str(), actual_version.c_str());
    }''')
    replace('src/xrGame/xrServerMapSync.cpp', '''\tif (strstr(Core.Params, "-netcoop")) //netcoop: host runs a single-player level, skip map/crc validation
\t{
\t\tresponseP.w_u8(static_cast<u8>(SuccessSync));
\t\tMsg("[NetAnomaly] map sync forced OK for client 0x%08x", clientID);
\t\tSendTo(clientID, responseP, net_flags(TRUE, TRUE));
\t\treturn;
\t}

''', '')
    replace('src/xrGame/xrServerMapSync.cpp',
            '\telse if (!Level().IsChecksumsEqual(client_geom_crc32))',
            '\telse if (!strstr(Core.Params, "-netcoop") && !Level().IsChecksumsEqual(client_geom_crc32))')
    replace('src/xrGame/xrServer.h', '\tbool gamma_snapshot_ready;', '\tgamma_net::movement_limiter gamma_movement;\n\tbool gamma_snapshot_ready;')
    replace(game, '\tnet_PassUpdates = TRUE;', '\tgamma_snapshot_ready = false;\n\tnet_PassUpdates = TRUE;')
    replace(game, '\tgamma_snapshot_ready = false;', '\tgamma_movement = gamma_net::movement_limiter{};\n\tgamma_snapshot_ready = false;')
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
    if (strstr(Core.Params, "-netcoop") && !CL->flags.bLocal)
    {
        switch (type)
        {
        case M_CL_UPDATE: case M_EVENT: case M_EVENT_PACK: case M_CHAT_MESSAGE:
        case M_CLIENTREADY: case M_CLIENT_REQUEST_CONNECTION_DATA:
        case M_CL_AUTH: case M_CREATE_PLAYER_STATE:
        case M_SECURE_KEY_SYNC: case M_SECURE_MESSAGE:
        case M_SV_MAP_NAME: case M_SV_DIGEST:
        case M_GAMESPY_CDKEY_VALIDATION_CHALLENGE_RESPOND: case M_CL_PING_CHALLENGE_RESPOND:
        case M_REMOTE_CONTROL_AUTH: case M_REMOTE_CONTROL_CMD: case M_NETANOMALY_CMD: case M_FILE_TRANSFER:
            break;
        default: return 0; // Server snapshots, game messages and unsupported request paths are never client input.
        }
        if (type == M_CL_AUTH && P.B.count != 10) return 0;
        if (type == M_SECURE_KEY_SYNC && P.B.count != 6) return 0;
        if (type == M_REMOTE_CONTROL_AUTH || type == M_REMOTE_CONTROL_CMD || type == M_NETANOMALY_CMD || type == M_FILE_TRANSFER)
            if (!CL->GammaIsAdmin()) return 0; // Client flags and legacy passwords confer no authority.
        if (!CL->gamma_authenticated)
        {
            switch (type)
            {
            case M_CLIENTREADY: case M_CLIENT_REQUEST_CONNECTION_DATA:
            case M_CL_AUTH: case M_CREATE_PLAYER_STATE:
            case M_SECURE_KEY_SYNC: case M_SECURE_MESSAGE:
            case M_SV_MAP_NAME: case M_SV_DIGEST:
            case M_GAMESPY_CDKEY_VALIDATION_CHALLENGE_RESPOND:
            case M_CL_PING_CHALLENGE_RESPOND:
                break;
            default: return 0; // No gameplay before the account owns an authenticated actor.
            }
        }
    }
    if (strstr(Core.Params, "-netcoop"))
    {
        switch (type)
        {
        case M_SAVE_GAME: case M_SAVE_PACKET: case M_LOAD_GAME: case M_RELOAD_GAME:
            Msg("! [GAMMA NetAnomaly] Single-player save/load packet rejected");
            return 0; // Also reject the internal host: SP snapshots cannot persist multiplayer accounts.
        default: break;
        }
    }
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
                !gamma_net::valid_coop_actor(P.B.data + 8, P.B.count - 8)) break;
            if (strstr(Core.Params, "-netcoop") && !CL->flags.bLocal)
            {
                float candidate[3];
                CopyMemory(candidate, P.B.data + 17, sizeof(candidate));
                if (!CL->gamma_movement.initialized)
                    CL->gamma_movement.reset(&CL->owner->o_Position.x, Device.dwTimeGlobal);
                if (!CL->gamma_movement.accept(candidate, Device.dwTimeGlobal)) break;
            }''')
    # Do not accumulate obsolete movement packets behind reliable retransmissions.
    replace(game, '\t\t\tif (SV_Client)\n\t\t\t\tSendTo(SV_Client->ID, P, net_flags(TRUE, TRUE));',
            '\t\t\tif (SV_Client)\n\t\t\t\tSendTo(SV_Client->ID, P, net_flags(FALSE, TRUE));')
    replace(game, '\tcase M_CL_INPUT:\n\t\t{', '''\tcase M_CL_INPUT:
        {
            if (!CL->owner || P.B.count < 4) break;
            u16 object_id;
            CopyMemory(&object_id, P.B.data + 2, sizeof(object_id));
            if (object_id != CL->owner->ID) break;''')
    replace(game, '\tcase M_CHAT_MESSAGE:\n\t\t{', '''\tcase M_CHAT_MESSAGE:
        {
            if (strstr(Core.Params, "-netcoop"))
            {
                std::string body;
                if (!CL->ps || !gamma_net::read_chat_body(P.B.data + 2, P.B.count - 2, body)) break;
                NET_Packet canonical;
                canonical.w_begin(M_CHAT_MESSAGE);
                canonical.w_s16(-1);
                canonical.w_stringZ(CL->name.c_str()); // Never display a sender name supplied by the packet.
                canonical.w_stringZ(body.c_str());
                canonical.w_s16(0);
                u16 ignored;
                canonical.r_begin(ignored);
                OnChatMessage(&canonical, CL);
                break;
            }''')
    # Keep the command channel, but execute Lua only from the delayed main-thread handler.
    text = read(game)
    begin = text.index('\tcase M_NETANOMALY_CMD:\n\t\t{')
    end = text.index('\n\tcase ', begin + 10)
    handler = text[begin:end]
    handler = handler.replace('\t\t{', '\t\t{\n            if (strstr(Core.Params, "-netcoop") && !CL->flags.bLocal && !CL->GammaIsAdmin()) break;\n            if (P.B.count < 3 || P.B.count > 4098 || !memchr(P.B.data + 2, 0, P.B.count - 2)) break;', 1)
    changed[game] = text[:begin] + '\tcase M_NETANOMALY_CMD:\n        AddDelayedPacket(P, sender);\n        break;\n' + text[end:]
    text = read(game)
    position = text.index('\tcase M_CLIENT_REQUEST_CONNECTION_DATA:\n\t\t{', text.index('u32 xrServer::OnDelayedMessage'))
    changed[game] = text[:position] + handler + '\n' + text[position:]
    replace(game, '\t\t\tMsg("[NetAnomaly] cmd from [%s] 0x%s eid=%d : %s", na_name, na_cid, na_eid, na_text);',
            '\t\t\tMsg("[NetAnomaly] administrative command from [%s] eid=%d", na_name, na_eid);')
    replace(game, '\t\t\tif (CL->m_admin_rights.m_has_admin_rights)',
            '\t\t\tif (strstr(Core.Params, "-netcoop") ? CL->GammaIsAdmin() : CL->m_admin_rights.m_has_admin_rights)')
    replace(game, '\t\t\t\tstring1024 buff;', '\t\t\t\tif (P.B.count < 3 || P.B.count > 1026 || !memchr(P.B.data + 2, 0, P.B.count - 2)) break;\n\t\t\t\tstring1024 buff;')
    replace(game, '\tcase M_REMOTE_CONTROL_AUTH:\n\t\t{', '''\tcase M_REMOTE_CONTROL_AUTH:
        {
            if (strstr(Core.Params, "-netcoop"))
            {
                NET_Packet answer;
                answer.w_begin(M_REMOTE_CONTROL_AUTH);
                answer.w_stringZ(CL->GammaIsAdmin() ? "Account is administrator" : "Access denied");
                SendTo(CL->ID, answer, net_flags(TRUE, TRUE));
                break; // No plaintext radmins.ltx authentication in GAMMA multiplayer.
            }''')

    console = 'src/xrEngine/XR_IOConsole.cpp'
    replace('src/xrEngine/XR_IOConsole.h', '//refs', 'extern ENGINE_API bool gamma_console_allowed;\n\n//refs')
    replace(console, 'void CConsole::ExecuteCommand(LPCSTR cmd_str, bool record_cmd)\n{', '''bool gamma_console_allowed = false;

void CConsole::ExecuteCommand(LPCSTR cmd_str, bool record_cmd)
{
    if (record_cmd && strstr(Core.Params, "-netcoop") && !strstr(Core.Params, "-dedicated") && !gamma_console_allowed) return;''')
    replace(console, 'void CConsole::Show()\n{', '''void CConsole::Show()
{
    if (strstr(Core.Params, "-netcoop") && !strstr(Core.Params, "-dedicated") && !gamma_console_allowed) return;''')
    client_base = 'src/xrGame/game_cl_base.cpp'
    replace(client_base, '#include "game_cl_base.h"', '#include "game_cl_base.h"\n#include "../xrEngine/XR_IOConsole.h"')
    replace(client_base, '\t\t\t\tgame_PlayerState::skip_Import(P); //this mean that local_player not created yet ..',
            '\t\t\t\tif (strstr(Core.Params, "-netcoop") && local_player) local_player->net_Import(P);\n\t\t\t\telse game_PlayerState::skip_Import(P); // No local state yet.')
    replace(client_base, '\t\tgame_PlayerState::skip_Import(P);\n\t};',
            '\t\tif (strstr(Core.Params, "-netcoop") && ID == local_svdpnid && local_player) local_player->net_Import(P);\n\t\telse game_PlayerState::skip_Import(P);\n\t};')
    for name in ('game_cl_GameState::game_cl_GameState()', 'game_cl_GameState::~game_cl_GameState()'):
        replace(client_base, name + '\n{', name + '\n{\n    if (strstr(Core.Params, "-netcoop")) gamma_console_allowed = false;')
    replace(client_base, '\tnet_import_GameTime(P);', '''    if (strstr(Core.Params, "-netcoop"))
    {
        gamma_console_allowed = local_player && local_player->testFlag(GAME_PLAYER_HAS_ADMIN_RIGHTS);
        if (!gamma_console_allowed && Console->bVisible) Console->Hide();
    }
\tnet_import_GameTime(P);''', count=2)
    replace(game, 'void xrServer::Update()\n{', '''void xrServer::Update()
{
    if (strstr(Core.Params, "-netcoop"))
    {
        auto refresh_roles = [](IClient* client)
        {
            xrClientData* peer = static_cast<xrClientData*>(client);
            if (peer->flags.bLocal || !peer->ps) return;
            if (peer->gamma_role_checked_at && Device.dwTimeGlobal - peer->gamma_role_checked_at < 1000) return;
            peer->gamma_role_checked_at = Device.dwTimeGlobal;
            const bool admin = peer->GammaIsAdmin();
            peer->m_admin_rights.m_has_admin_rights = admin;
            if (admin) peer->ps->setFlag(GAME_PLAYER_HAS_ADMIN_RIGHTS);
            else peer->ps->resetFlag(GAME_PLAYER_HAS_ADMIN_RIGHTS);
        };
        ForEachClientDo(refresh_roles);
    }''')
    replace(game, '\tif (CL->process_id == GetCurrentProcessId())',
            '\tif (CL->process_id == GetCurrentProcessId() && CL->ID == Level().GetClientID())')

    level = "src/xrGame/Level_network.cpp"
    replace(level, 'if (g_tutorial2 && !g_tutorial->Persistent())', 'if (g_tutorial2 && !g_tutorial2->Persistent())')
    replace(level, 'if (GameID() != eGameIDSingle && OnClient())',
            'if ((GameID() != eGameIDSingle || strstr(Core.Params, "-netcoop")) && OnClient())')
    actor = "src/xrGame/Actor_Network.cpp"
    replace('src/xrGame/Actor.h', '\tu32 NET_Time; // server time of last update',
            '\tu32 gamma_net_trace_time;\n\tu32 NET_Time; // server time of last update')
    replace(actor, '#include "pch_script.h"', '#include "pch_script.h"\n#include "../xrNetServer/GammaNetPolicy.h"')
    replace(actor, 'BOOL CActor::net_Spawn(CSE_Abstract* DC)\n{',
            'BOOL CActor::net_Spawn(CSE_Abstract* DC)\n{\n\tgamma_net_trace_time = 0;')
    replace(actor, 'void CActor::net_Import_Base_proceed()\n{', '''void CActor::net_Import_Base_proceed()
{
    if (strstr(Core.Params, "-net_trace") &&
        Device.dwTimeGlobal - gamma_net_trace_time >= 1000)
    {
        gamma_net_trace_time = Device.dwTimeGlobal;
        const Fvector& sample = NET.empty() ? Position() : NET.back().p_pos;
        Msg("[NetTrace] actor=%u name=%s local=%d server=%d visible=%d visual=%d pos=%.3f,%.3f,%.3f sample=%.3f,%.3f,%.3f samples=%u",
            ID(), *cName(), int(Local()), int(OnServer()), int(getVisible()), int(Visual() != NULL),
            Position().x, Position().y, Position().z, sample.x, sample.y, sample.z, u32(NET.size()));
    }''')
    replace(actor, 'H_Parent() || (GameID() == eGameIDSingle) || ((NumItems > 1) && OnClient())',
            'H_Parent() || (GameID() == eGameIDSingle && !strstr(Core.Params, "-netcoop")) || (NumItems > 1)')
    replace(actor, '\tif (OnServer())\n\t{\n\t\tE->s_flags.set(M_SPAWN_OBJECT_LOCAL, TRUE);',
            '\tif (OnServer() && !strstr(Core.Params, "-netcoop"))\n\t{\n\t\tE->s_flags.set(M_SPAWN_OBJECT_LOCAL, TRUE);')
    replace(actor, 'N.dwTimeStamp < NET.back().dwTimeStamp',
            'N.dwTimeStamp != NET.back().dwTimeStamp && !gamma_net::newer(N.dwTimeStamp, NET.back().dwTimeStamp)')
    replace(actor, 'N_A.dwTimeStamp < NET_A.back().dwTimeStamp',
            'N_A.dwTimeStamp != NET_A.back().dwTimeStamp && !gamma_net::newer(N_A.dwTimeStamp, NET_A.back().dwTimeStamp)')
    replace(actor, '\tif (OnClient())SetfHealth(health);',
            '\tif (OnClient() && !(strstr(Core.Params, "-netcoop") && strstr(Core.Params, "-dedicated"))) SetfHealth(health);')
    replace(actor, '\tid_Team = P.r_u8();\n\tid_Squad = P.r_u8();\n\tid_Group = P.r_u8();', '''    const u8 team = P.r_u8(), squad = P.r_u8(), group = P.r_u8();
    if (!(strstr(Core.Params, "-netcoop") && strstr(Core.Params, "-dedicated")))
    {
        id_Team = team;
        id_Squad = squad;
        id_Group = group;
    } // The client's movement packet cannot change server-owned faction fields.''')
    replace(actor, '\tif (!IsGameTypeSingle())\n\t{\n\t\tsetEnabled(TRUE);',
            '\tif (!IsGameTypeSingle() || strstr(Core.Params, "-netcoop"))\n\t{\n\t\tsetEnabled(TRUE);')
    replace(actor, '\t\treturn getSVU() | getLocal();',
            '\t\treturn (strstr(Core.Params, "-netcoop") != NULL) || getSVU() || getLocal();')
    # All actors start with cam_active=eacFirstEye, including remote players.
    # Only the viewed actor may use the first-person body/legs rendering path.
    render = 'src/xrGame/Actor.cpp'
    replace(render, '\tif (cam_active == eacFirstEye)\n\t{\n\t\tif (::Render->active_phase() == 0)',
            '\tif (cam_active == eacFirstEye && this == Level().CurrentViewEntity())\n\t{\n\t\tif (::Render->active_phase() == 0)')
    replace(render, '    return g_legs_enabled\n',
            '    return g_legs_enabled && actor == Level().CurrentViewEntity()\n')
    replace('src/xrGame/player_hud_legs.cpp',
            '    actor->XFORMShadow.set(actor->XFORM());\n\n    if (!g_legs_enabled || showActorBody != 0 || !actor)',
            '    if (actor) actor->XFORMShadow.set(actor->XFORM());\n\n    if (!actor || actor != Level().CurrentViewEntity() || !g_legs_enabled || showActorBody != 0)')
    single = "src/xrGame/game_sv_single.cpp"
    replace(single, '#include "../xrEngine/no_single.h"',
            '#include "../xrEngine/no_single.h"\n#include "../xrNetServer/GammaPeerAuth.h"')
    alife_graph_registry = 'src/xrGame/alife_graph_registry.cpp'
    replace(alife_graph_registry, 'using namespace ALife;',
            'using namespace ALife;\n\nextern ENGINE_API bool g_dedicated_server;')
    replace(alife_graph_registry, '''void CALifeGraphRegistry::setup_current_level()
{
\tm_level = xr_new<CALifeLevelRegistry>(ai().game_graph().vertex(actor()->m_tGraphID)->level_id());''', '''void CALifeGraphRegistry::setup_current_level()
{
    if (strstr(Core.Params, "-netcoop") && g_dedicated_server)
    {
        actor()->m_tGraphID = GameGraph::_GRAPH_ID(136);
        actor()->m_tNodeID = 75660;
        actor()->o_Position.set(-140.56f, 1.50f, -317.99f);
        actor()->o_Angle.set(0.f, 0.f, 0.f);
        Msg("[NetAnomaly] dedicated authority initial level forced to k00_marsh/hidden_base");
    }
\tm_level = xr_new<CALifeLevelRegistry>(ai().game_graph().vertex(actor()->m_tGraphID)->level_id());''')
    custom_zone = 'src/xrGame/CustomZone.cpp'
    replace(custom_zone, '''\tif (Level().CurrentEntity())
\t{
\t\tFvector P = Level().CurrentControlEntity()->Position();''', '''\tCObject* control_entity = Level().CurrentControlEntity();
\tif (control_entity)
\t{
\t\tFvector P = control_entity->Position();''')
    replace(custom_zone,
            '\t\tfloat act_distance = Level().CurrentControlEntity()->Position().distance_to(P) - s.R;',
            '''        CObject* zone_reference = Level().CurrentControlEntity();
        if (!zone_reference)
            zone_reference = Level().CurrentEntity();
        const float act_distance = zone_reference ? zone_reference->Position().distance_to(P) - s.R : 0.f;''')
    stalker = 'src/xrGame/ai/stalker/ai_stalker.cpp'
    replace(stalker, '''\t\t\t\t::luabind::functor<bool> funct;
\t\t\t\tfloat distance = Actor()->Position().distance_to(Position());
\t\t\t\tauto luaObject = lua_game_object();
\t\t\t\tif (luaObject && distance < NPCsLookAtActorMinDistance && ai().script_engine().functor("_G.CNPCBeforeLookAtActor", funct))
\t\t\t\t{
\t\t\t\t\tLookAtActorLuaResult = funct(luaObject, distance);
\t\t\t\t}''', '''                // ALife schedules stalkers before the authority actor has spawned.
                // Only the optional look-at callback needs an actor; NPC AI below
                // must continue updating while the server waits for a player.
                CActor* actor = Actor();
                auto luaObject = lua_game_object();
                if (actor && luaObject)
                {
                    const float distance = actor->Position().distance_to(Position());
                    ::luabind::functor<bool> funct;
                    if (distance < NPCsLookAtActorMinDistance &&
                        ai().script_engine().functor("_G.CNPCBeforeLookAtActor", funct))
                        LookAtActorLuaResult = funct(luaObject, distance);
                }''')
    replace('src/xrEngine/Text_Console.h', '\tvoid OnPaint();', '\tvoid OnPaint();\n\tvoid ScrollLog(short delta);')
    replace('src/xrEngine/Text_Console.cpp', '\tm_pMainWnd = &Device.m_hWnd;', '''\tm_pMainWnd = &Device.m_hWnd;
    SetWindowText(*m_pMainWnd, "GAMMA Dedicated Server Console [DEBUG]");
    SetWindowLongPtr(*m_pMainWnd, GWL_STYLE, WS_OVERLAPPEDWINDOW | WS_VISIBLE);
    SetWindowPos(*m_pMainWnd, NULL, 0, 0, 1000, 700,
        SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW);
    ClipCursor(NULL);
    while (ShowCursor(TRUE) < 0) {}''')
    replace('src/xrEngine/Text_Console.cpp', 'void CTextConsole::OnFrame()\n{', '''void CTextConsole::ScrollLog(short delta)
{
    const int lines = delta / WHEEL_DELTA;
    scroll_delta = _max(0, scroll_delta + lines * 3);
    InvalidateRect(m_hLogWnd, NULL, FALSE);
}

void CTextConsole::OnFrame()
{''')
    replace('src/xrEngine/Text_Console_WndProc.cpp', '''\tcase WM_ERASEBKGND:
\t\treturn (LRESULT)1; // Say we handled it.

\tcase WM_PAINT:''', '''\tcase WM_ERASEBKGND:
\t\treturn (LRESULT)1; // Say we handled it.

    case WM_MOUSEWHEEL:
        {
            CTextConsole* pTextConsole = (CTextConsole*)Console;
            pTextConsole->ScrollLog(GET_WHEEL_DELTA_WPARAM(wParam));
            return (LRESULT)0;
        }
\tcase WM_PAINT:''')
    replace(single, 'void game_sv_Single::OnPlayerConnectFinished(ClientID id_who)\n{', '''void game_sv_Single::OnPlayerConnectFinished(ClientID id_who)
{
    if (netcoop_mode() && m_server)
    {
        xrClientData* peer = static_cast<xrClientData*>(m_server->ID_to_client(id_who));
        if (!peer) return;
        if (!peer->flags.bLocal && !peer->gamma_authenticated)
        {
            string_path config_path, tickets_path;
            FS.update_path(config_path, "$game_config$", "gamma_net_role.ltx");
            FS.update_path(tickets_path, "$app_data_root$", "auth_tickets\\\\");
            if (!FS.exist(config_path)) { m_server->DisconnectClient(peer, "GAMMA server configuration missing"); return; }
            CInifile config(config_path);
            gamma_net::peer_ticket ticket;
            const std::string content = config.line_exist("network", "content_sha256") ?
                config.r_string("network", "content_sha256") : "";
            bool accepted = gamma_net::inspect_ticket(tickets_path, *peer->gamma_ticket,
                *peer->gamma_content, content, std::time(nullptr), ticket);
            bool duplicate = false;
            if (accepted)
            {
                auto check_duplicate = [&](IClient* client)
                {
                    xrClientData* other = static_cast<xrClientData*>(client);
                    if (other != peer && other->flags.bConnected && other->gamma_authenticated &&
                        ticket.account == *other->gamma_account) duplicate = true;
                };
                m_server->ForEachClientDo(check_duplicate);
            }
            if (!accepted || duplicate || !gamma_net::consume_ticket(ticket))
            {
                m_server->DisconnectClient(peer, "GAMMA account ticket rejected or account already connected");
                return;
            }
            peer->gamma_account = ticket.account.c_str();
            peer->gamma_authenticated = true;
            peer->gamma_ticket = ""; // No bearer token remains in the active player record.
        }
    }''')
    replace(single, '\tif (CL->process_id == GetCurrentProcessId())', '\tif (CL->flags.bLocal)')
    replace(single, '\t\tMsg("! [NetAnomaly] section [actor] is not an actor entity");\n\t\treturn;',
            '\t\tMsg("! [NetAnomaly] section [actor] is not an actor entity");\n\t\tF_entity_Destroy(E);\n\t\treturn;')
    # spawn_end can destroy the temporary spawn descriptor: log the saved position instead.
    replace(single, 'A->o_Position.x, A->o_Position.y, A->o_Position.z);', 'pos.x, pos.y, pos.z);')
    cl_single = "src/xrGame/game_cl_single.cpp"
    replace(cl_single, '\tActor()->OnDifficultyChanged();', '\tif (Actor()) Actor()->OnDifficultyChanged();')
    replace(cl_single, '\tLevel().Server->game->SetGameTimeFactor(fTimeFactor);',
            '\tif (Level().Server) { Level().Server->game->SetGameTimeFactor(fTimeFactor); }', count=2)

    bindings = 'src/xrGame/console_registrator_script.cpp'
    replace(bindings, '#include "console_registrator.h"', '#include "console_registrator.h"\n#include <cstdlib>\n#include <string>\n#include "level.h"\n#include "xrServer.h"\n#include "../xrNetServer/GammaPeerAuth.h"')
    replace(bindings, 'CConsole* console()\n{', '''bool gamma_admin_allowed()
{
    return strstr(Core.Params, "-netcoop") &&
        (strstr(Core.Params, "-dedicated") || gamma_console_allowed);
}

bool gamma_admin_peer_allowed(LPCSTR identity)
{
    if (!g_pGameLevel || !Level().Server || !strstr(Core.Params, "-dedicated")) return false;
    if (!xr_strcmp(identity, "console")) return true;
    if (!gamma_net::hex_identity(identity, 8)) return false;
    ClientID id;
    id.set(static_cast<u32>(std::strtoul(identity, nullptr, 16)));
    xrClientData* peer = Level().Server->ID_to_client(id);
    return peer && peer->GammaIsAdmin();
}

bool gamma_send_admin_request(LPCSTR command)
{
    if (!g_pGameLevel || !gamma_admin_allowed() || strstr(Core.Params, "-dedicated") ||
        !command || !*command || xr_strlen(command) > 4095) return false;
    NET_Packet packet;
    packet.w_begin(M_NETANOMALY_CMD);
    packet.w_stringZ(command);
    Level().Send(packet, net_flags(TRUE, TRUE));
    return true;
}

static bool gamma_presentation_command(LPCSTR command)
{
    if (!command || strchr(command, '\\n') || strchr(command, '\\r') || strchr(command, ';')) return false;
    const std::string text(command);
    for (const auto* prefix : {"r_", "r2_", "r3_", "r4_", "rs_", "snd_", "vid_", "texture_", "mouse_"})
        if (text.compare(0, strlen(prefix), prefix) == 0) return true;
    return text == "hide" || text == "main_menu off" || text == "main_menu on";
}

CConsole* console()
{''')
    replace(bindings, '#include "xrServer.h"', '#include "xrServer.h"\n#include "Actor.h"\n#include "xrserver_objects_alife_monsters.h"\n#include "xrserver_objects_alife_items.h"')
    replace(bindings, 'bool gamma_send_admin_request(LPCSTR command)', '''CScriptGameObject* gamma_admin_actor(LPCSTR identity)
{
    if (!gamma_admin_peer_allowed(identity) || !gamma_net::hex_identity(identity, 8)) return nullptr;
    ClientID id;
    id.set(static_cast<u32>(std::strtoul(identity, nullptr, 16)));
    xrClientData* peer = Level().Server->ID_to_client(id);
    if (!peer || !peer->owner) return nullptr;
    CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(peer->owner->ID));
    return actor ? actor->lua_game_object() : nullptr;
}

bool gamma_admin_spawn_item(LPCSTR identity, LPCSTR section, unsigned count)
{
    if (!gamma_admin_actor(identity) || !section || !*section || count < 1 || count > 50 ||
        xr_strlen(section) > 63 || !pSettings->section_exist(section) || !pSettings->line_exist(section, "class")) return false;
    ClientID id;
    id.set(static_cast<u32>(std::strtoul(identity, nullptr, 16)));
    xrServer* server = Level().Server;
    xrClientData* peer = server->ID_to_client(id);
    CSE_ALifeCreatureActor* parent = smart_cast<CSE_ALifeCreatureActor*>(peer->owner);
    CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(peer->owner->ID));
    IClient* authority = server->GetServerClient();
    if (!parent || !actor || !authority || !server->game) return false;
    for (unsigned n = 0; n < count; ++n)
    {
        CSE_Abstract* entity = server->game->spawn_begin(section);
        if (!entity) return false;
        CSE_ALifeInventoryItem* item = smart_cast<CSE_ALifeInventoryItem*>(entity);
        CSE_ALifeDynamicObject* dynamic = smart_cast<CSE_ALifeDynamicObject*>(entity);
        if (!item || !dynamic) { F_entity_Destroy(entity); return false; }
        entity->ID_Parent = parent->ID;
        entity->o_Position = actor->Position();
        dynamic->m_tNodeID = parent->m_tNodeID;
        dynamic->m_tGraphID = parent->m_tGraphID;
        dynamic->m_bALifeControl = false;
        if (!server->game->spawn_end(entity, authority->ID)) return false;
    }
    return true;
}

bool gamma_send_admin_request(LPCSTR command)''')

    events = 'src/xrGame/xrServer_process_event.cpp'
    replace(events, '#include "xrServer.h"', '#include "xrServer.h"\n#include "xr_level_controller.h"\n#include "../xrNetServer/GammaNetPolicy.h"')
    replace(events, 'void xrServer::Process_event(NET_Packet& P, ClientID sender)\n{', '''void xrServer::Process_event(NET_Packet& P, ClientID sender)
{
    if (P.r_tell() > P.B.count || P.B.count - P.r_tell() < 8) return;
''')
    replace(events, '\tCSE_Abstract* receiver = game->get_entity_from_eid(destination);', '''    if (strstr(Core.Params, "-netcoop"))
    {
        xrClientData* peer = ID_to_client(sender);
        if (!peer) return;
        if (!peer->flags.bLocal)
        {
            if (!peer->gamma_authenticated || !peer->owner || destination != peer->owner->ID) return;
            // Clients submit bounded input; money, hits, healing, spawning, ownership,
            // upgrades, visual changes, teleportation and destruction are server events.
            if (type != GE_INV_ACTION || P.B.count - P.r_tell() != 14 || !SV_Client) return;
            static_assert(kWPN_1 == 22 && kWPN_6 == 27 && kWPN_NEXT == 29 &&
                kWPN_FIRE == 30 && kWPN_FIREMODE_NEXT == 37, "Update the GAMMA input protocol for changed key IDs");
            if (!gamma_net::valid_inventory_input(P.B.data + P.r_tell(), P.B.count - P.r_tell())) return;
            SendTo(SV_Client->ID, P, net_flags(TRUE, TRUE));
            return; // No receiver->OnEvent or global mutation from an untrusted request.
        }
    }
\tCSE_Abstract* receiver = game->get_entity_from_eid(destination);''')
    replace('src/xrGame/Actor_Events.cpp', '\t\t\ts32 ShotRndSeed = P.r_s32();', '''\t\t\ts32 ShotRndSeed = P.r_s32();
            if (strstr(Core.Params, "-netcoop") && strstr(Core.Params, "-dedicated"))
            {
                ZoomRndSeed = Random.randI(0x7fffffff);
                ShotRndSeed = Random.randI(0x7fffffff);
                if (g_Alive()) inventory().Action(cmd, flags);
                break; // A remote actor's IR handler rejects Remote(); execute bounded weapon input directly on server.
            } // Server chooses authoritative weapon randomness on the simulation thread.''')
    replace('src/xrGame/game_sv_base.cpp', '\t\t\tCL->ps = createPlayerState(&tNetPacket);', '''            if (strstr(Core.Params, "-netcoop"))
            {
                if (CL->ps) break; // Do not replace a connected player's state with a replayed handshake.
                CL->ps = createPlayerState(nullptr);
                CL->ps->resetFlag(GAME_PLAYER_FLAG_SKIP);
                CL->ps->resetFlag(GAME_PLAYER_HAS_ADMIN_RIGHTS);
                CL->ps->m_account.set_player_name(CL->name.c_str());
            }
            else CL->ps = createPlayerState(&tNetPacket); // Never import client balances, roles or stats in netcoop.''')
    secure = 'src/xrGame/xrServer_secure_messaging.cpp'
    replace(secure, 'void xrServer::OnSecureMessage(NET_Packet& P, xrClientData* xrClSender)\n{', '''void xrServer::OnSecureMessage(NET_Packet& P, xrClientData* xrClSender)
{
    if (!xrClSender || P.B.count < 8) return;''')
    replace(secure, '\tVERIFY2(checksum == real_checksum, "caught cheater");',
            '\tif (!strstr(Core.Params, "-netcoop")) VERIFY2(checksum == real_checksum, "caught cheater");')
    replace(secure, '\tOnMessage(dec_packet, xrClSender->ID);', '''    u16 nested_type;
    CopyMemory(&nested_type, dec_packet.B.data, sizeof(nested_type));
    if (nested_type == M_SECURE_MESSAGE || nested_type == M_EVENT_PACK) return; // No recursive encrypted wrappers.
\tOnMessage(dec_packet, xrClSender->ID); // Re-enter the same account/packet/event gates.''')
    replace(secure, '\tVERIFY2(new_seed == xrCL->m_last_key_sync_request_seed, "cracker detected !");',
            '\tif (new_seed != xrCL->m_last_key_sync_request_seed) return;')

    for name, position, story_actor, count in (
        ('src/xrGame/alife_dynamic_object.cpp', 'o_Position', 'alife().graph().actor()->o_Position', 2),
        ('src/xrGame/alife_online_offline_group.cpp', '(*I).second->o_Position', 'alife().graph().actor()->o_Position', 2),
        ('src/xrGame/alife_group_abstract.cpp', 'tpGroupMember->o_Position', 'I->alife().graph().actor()->o_Position', 1),
    ):
        replace(name, '#include "stdafx.h"', '#include "stdafx.h"\n#include "GammaALife.h"')
        replace(name, story_actor + '.distance_to(' + position + ')',
                'gamma_alife_distance(' + position + ', ' + story_actor + ')', count=count)
    replace(bindings, '\tEngine.Event.Defer("KERNEL:console", size_t(xr_strdup(string_to_execute)));', '''    if (strstr(Core.Params, "-netcoop") && !strstr(Core.Params, "-dedicated") && !gamma_presentation_command(string_to_execute))
    {
        if (gamma_admin_allowed()) gamma_send_admin_request((std::string("cmd ") + string_to_execute).c_str());
        return;
    }
\tEngine.Event.Defer("KERNEL:console", size_t(xr_strdup(string_to_execute)));''')
    replace(bindings, 'static void console_execute(lua_State* L, CConsole* c, LPCSTR cmd)\n{', '''static void console_execute(lua_State* L, CConsole* c, LPCSTR cmd)
{
    if (strstr(Core.Params, "-netcoop") && !strstr(Core.Params, "-dedicated") && !gamma_presentation_command(cmd))
    {
        if (gamma_admin_allowed()) gamma_send_admin_request((std::string("cmd ") + cmd).c_str());
        return;
    }''')
    replace(bindings, '::luabind::object get_console_bounds(CConsole* c, LPCSTR cmd)', '''static void gamma_execute_script(CConsole* c, LPCSTR file)
{
    if (strstr(Core.Params, "-netcoop") && !strstr(Core.Params, "-dedicated")) return;
    c->ExecuteScript(file);
}

::luabind::object get_console_bounds(CConsole* c, LPCSTR cmd)''')
    replace(bindings, 'def("get_console", &console),', 'def("get_console", &console),\n        def("gamma_admin_allowed", &gamma_admin_allowed),\n        def("gamma_admin_peer_allowed", &gamma_admin_peer_allowed),\n        def("gamma_send_admin_request", &gamma_send_admin_request),')
    replace(bindings, 'def("gamma_admin_peer_allowed", &gamma_admin_peer_allowed),',
            'def("gamma_admin_peer_allowed", &gamma_admin_peer_allowed),\n        def("gamma_admin_actor", &gamma_admin_actor),\n        def("gamma_admin_spawn_item", &gamma_admin_spawn_item),')
    replace(bindings, '.def("execute_script", &CConsole::ExecuteScript)', '.def("execute_script", &gamma_execute_script)')
    replace(game, '"netanomaly_server.on_client_command"', '"gamma_admin.on_client_command"')
    replace('src/xrGame/console_commands.cpp', '"netanomaly_server.on_client_command"', '"gamma_admin.on_client_command"')

    # Console commands also serve quicksave, quickload and Lua calls. Block before
    # screenshots, pause changes, last-save state or world packets are produced.
    commands = 'src/xrGame/console_commands.cpp'
    for command in ('CCC_ALifeSave', 'CCC_ALifeLoadFrom', 'CCC_LoadLastSave'):
        text = read(commands)
        begin = text.index('class ' + command + ' :')
        entry = '\tvirtual void Execute(LPCSTR args)\n\t{'
        position = text.index(entry, begin) + len(entry)
        changed[commands] = text[:position] + '''
        if (strstr(Core.Params, "-netcoop"))
        {
            Msg("! [GAMMA NetAnomaly] Single-player save/load is disabled in multiplayer");
            return;
        }
''' + text[position:]

    replace('src/xrEngine/xr_ioc_cmd.cpp', '\t\tstrlwr(op_server);\n\t\tprotect_Name_strlwr(op_client);', '''\t\tstrlwr(op_server);
        if (strstr(Core.Params, "-netcoop") && strstr(op_server, "/load"))
        {
            Msg("! [GAMMA NetAnomaly] Starting from a single-player save is disabled");
            return;
        }
\t\tprotect_Name_strlwr(op_client);''')

    return ''.join(''.join(difflib.unified_diff(originals[n].splitlines(True), changed[n].splitlines(True),
                                              fromfile='a/' + n, tofile='b/' + n))
                   for n in sorted(changed) if originals[n] != changed[n])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(generate(args.source), encoding='utf-8', newline='\n')
