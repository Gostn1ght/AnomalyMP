#include "pch_script.h"
#include "netcoop.h"
#include "../xrEngine/netcoop_menu_camera.h"

#include <bcrypt.h>
#include <io.h>
#include "netcoop_storage_policy.h"
#include <wincrypt.h>
#include <winhttp.h>
#include "../3rd party/nlohmann/json.hpp"
#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "bcrypt.lib")

#include "xrServer.h"
#include "game_sv_base.h"
#include "inventory_space.h"
#include "xrMessages.h"
#include "Level.h"
#include "Actor.h"
#include "Actor_Flags.h"
#include "ui_base.h"
#include "string_table.h"
#include "xr_level_controller.h"
#include "InventoryOwner.h"
#include "Inventory.h"
#include "PDA.h"
#include "inventory_item.h"
#include "entity_alive.h"
#include "trade.h"
#include "ai_space.h"
#include "game_graph.h"
#include "level_graph.h"
#include "ai_object_location.h"
#include "Weapon.h"
#include "script_engine.h"
#include "xrServer_Objects_ALife_Monsters.h"
#include "game_base_space.h"
#include "PhraseDialog.h"
#include "PhraseDialogManager.h"
#include "game_sv_single.h"
#include "GameTaskManager.h"
#include "GameTask.h"
#include "alife_registry_wrappers.h"
#include "UIGameCustom.h"
#include "ui/UIPdaWnd.h"
#include "game_news.h"
#include "../xrPhysics/PhysicsShell.h"
#include "../xrServerEntities/PHSynchronize.h"
#include "../xrEngine/gamemtllib.h"
#include "../Include/xrRender/Kinematics.h"
#include "../Include/xrRender/KinematicsAnimated.h"

namespace netcoop
{
// ---------------------------------------------------------------------------
// common helpers
// ---------------------------------------------------------------------------
static const u32 client_key_iterations = 20000;
static const u32 server_hash_iterations = 60000;
static const u32 key_bytes = 32;
static const u32 salt_bytes = 16;
static const float trade_max_distance = 6.f;

bool enabled()
{
	static int state = -1;
	if (state < 0)
		state = strstr(Core.Params, "-netcoop") ? 1 : 0;
	return state == 1;
}

bool pure_client()
{
	return enabled() && g_pGameLevel && !Level().Server;
}

LPCSTR role_name(u8 role)
{
	switch (role)
	{
	case role_admin: return "admin";
	case role_player: return "player";
	default: return "none";
	}
}

bool read_string(NET_Packet& P, LPSTR dest, u32 dest_size)
{
	dest[0] = 0;
	if (P.r_pos >= P.B.count)
		return false;
	const u8* start = P.B.data + P.r_pos;
	const u32 available = P.B.count - P.r_pos;
	const void* end = memchr(start, 0, available);
	if (!end)
		return false;
	const u32 length = u32((const u8*)end - start);
	if (length + 1 > dest_size)
		return false;
	CopyMemory(dest, start, length + 1);
	P.r_pos += length + 1;
	return true;
}

static void to_lower(xr_string& s)
{
	for (u32 i = 0; i < s.size(); ++i)
		s[i] = (char)tolower((unsigned char)s[i]);
}

static bool login_valid(LPCSTR login)
{
	const u32 n = xr_strlen(login);
	if (n < 3 || n > 20)
		return false;
	for (u32 i = 0; i < n; ++i)
	{
		const char c = login[i];
		if (!isalnum((unsigned char)c) && c != '_' && c != '-' && c != '.')
			return false;
	}
	return true;
}

static bool key_valid(LPCSTR key)
{
	if (xr_strlen(key) != key_bytes * 2)
		return false;
	for (LPCSTR c = key; *c; ++c)
	{
		if (!((*c >= '0' && *c <= '9') || (*c >= 'a' && *c <= 'f')))
			return false;
	}
	return true;
}

static xr_string to_hex(const u8* data, u32 size)
{
	static const char digits[] = "0123456789abcdef";
	xr_string out;
	out.resize(size * 2);
	for (u32 i = 0; i < size; ++i)
	{
		out[i * 2] = digits[data[i] >> 4];
		out[i * 2 + 1] = digits[data[i] & 15];
	}
	return out;
}

static bool pbkdf2(const void* secret, u32 secret_size, const void* salt, u32 salt_size, u32 iterations, u8* out,
                   u32 out_size)
{
	BCRYPT_ALG_HANDLE alg = NULL;
	if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, BCRYPT_ALG_HANDLE_HMAC_FLAG)))
		return false;
	const NTSTATUS status = BCryptDeriveKeyPBKDF2(alg, (PUCHAR)secret, secret_size, (PUCHAR)salt, salt_size,
	                                              iterations, out, out_size, 0);
	BCryptCloseAlgorithmProvider(alg, 0);
	return BCRYPT_SUCCESS(status);
}

static bool random_bytes(u8* out, u32 size)
{
	return BCRYPT_SUCCESS(BCryptGenRandom(NULL, out, size, BCRYPT_USE_SYSTEM_PREFERRED_RNG));
}

static bool constant_time_equal(const xr_string& a, const xr_string& b)
{
	if (a.size() != b.size())
		return false;
	u8 diff = 0;
	for (u32 i = 0; i < a.size(); ++i)
		diff |= u8(a[i] ^ b[i]);
	return diff == 0;
}

static void call_lua(LPCSTR function, bool ok, u8 role, LPCSTR message)
{
	::luabind::functor<void> f;
	if (ai().script_engine().functor(function, f))
	{
		try
		{
			f(ok, int(role), message);
		}
		catch (...)
		{
			Msg("! [Lost Zone] %s failed", function);
		}
	}
}

// ---------------------------------------------------------------------------
// client
// ---------------------------------------------------------------------------
static xr_string s_client_login;
static xr_string s_client_key;
static bool s_client_register = false;
static bool s_client_loaded = false;
static bool s_client_approved = false;
static bool s_client_remembered = false;
static u8 s_client_role = role_none;
static bool s_client_role_verified = false;
static u8 s_client_character_slot = 1;
static xr_string s_client_character_name, s_client_character_faction = "stalker", s_client_character_loadout;
static xr_string s_client_description, s_client_history;
static bool firebase_enabled();
static u8 s_client_character_economy = 1;

static void client_credentials_path(string_path& path)
{
	FS.update_path(path, "$app_data_root$", "netcoop_login.txt");
}

static void client_store_credentials()
{
    xr_string plain = s_client_login + "|" + s_client_key + (s_client_approved ? "|1|" : "|0|") + role_name(s_client_role);
    DATA_BLOB input = {u32(plain.size()), (BYTE*)plain.data()}, output = {};
    // DPAPI encrypts for this Windows user on this computer. Copying the
    // remembered file to a different machine does not grant an account.
    if (!CryptProtectData(&input, L"NetAnomaly remembered account", NULL, NULL, NULL, CRYPTPROTECT_UI_FORBIDDEN, &output)) return;
    string_path path, temp;
    client_credentials_path(path); xr_sprintf(temp, "%s.tmp", path);
    FILE* f = fopen(temp, "wb");
    if (f)
    {
        const u32 magic = 0x324c434e;
        fwrite(&magic, 4, 1, f); fwrite(output.pbData, 1, output.cbData, f);
        const bool ok = !ferror(f); fclose(f);
        if (ok && MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) s_client_remembered = true;
    }
    SecureZeroMemory(output.pbData, output.cbData); LocalFree(output.pbData);
    SecureZeroMemory(&plain[0], plain.size());
}

static void client_load_credentials()
{
    if (s_client_loaded) return;
    s_client_loaded = true;
    string_path path; client_credentials_path(path);
    FILE* f = fopen(path, "rb");
    if (!f) return;
    u8 data[8192]; const u32 size = u32(fread(data, 1, sizeof(data), f)); fclose(f);
    xr_string plain;
    bool migrate = false;
    u32 magic = 0; if (size >= 4) CopyMemory(&magic, data, 4);
    if (magic == 0x324c434e)
    {
        DATA_BLOB input = {size - 4, data + 4}, output = {};
        if (!CryptUnprotectData(&input, NULL, NULL, NULL, NULL, CRYPTPROTECT_UI_FORBIDDEN, &output)) return;
        plain.assign((char*)output.pbData, output.cbData);
        SecureZeroMemory(output.pbData, output.cbData); LocalFree(output.pbData);
    }
    else
    {
        // Upgrade the old derived-key file once, without losing the login.
        plain.assign((char*)data, size); migrate = true;
    }
    const size_t separator = plain.find('|');
    if (separator != xr_string::npos)
    {
        xr_string login = plain.substr(0, separator), key = plain.substr(separator + 1);
        const size_t state = key.find('|');
        // Remembered accounts written before moderation remain approved.
        s_client_approved = state == xr_string::npos || key.substr(state + 1, 1) == "1";
        if (state != xr_string::npos)
        {
            s_client_role = key.substr(state + 3) == "admin" ? role_admin : role_none;
            key.resize(state);
        }
        const size_t end = key.find_first_of("\r\n"); if (end != xr_string::npos) key.resize(end);
        if (login_valid(login.c_str()) && key_valid(key.c_str()))
        { s_client_login = login; s_client_key = key; s_client_remembered = true; if (migrate) client_store_credentials(); }
        if (!key.empty()) SecureZeroMemory(&key[0], key.size());
    }
    if (!plain.empty()) SecureZeroMemory(&plain[0], plain.size());
    SecureZeroMemory(data, sizeof(data));
}

bool derive_client_key(LPCSTR login, LPCSTR password, xr_string& key_hex)
{
	xr_string lower = login;
	to_lower(lower);
	xr_string salt = "NetAnomaly/";
	salt += lower;

	u8 key[key_bytes];
	if (!pbkdf2(password, xr_strlen(password), salt.c_str(), (u32)salt.size(), client_key_iterations, key, key_bytes))
		return false;
	key_hex = to_hex(key, key_bytes);
	SecureZeroMemory(key, sizeof(key));
	return true;
}

bool client_set_credentials(LPCSTR login, LPCSTR password, bool register_account)
{
	if (!login || !password || !login_valid(login))
	{
		Msg("! [Lost Zone] login must be 3-20 characters: letters, digits, _ - .");
		return false;
	}
	const u32 password_length = xr_strlen(password);
	if (password_length < 4 || password_length > 64)
	{
		Msg("! [Lost Zone] password must be 4-64 characters");
		return false;
	}

	xr_string key_hex;
	if (!derive_client_key(login, password, key_hex))
	{
		Msg("! [Lost Zone] cannot derive the account key");
		return false;
	}

	s_client_loaded = true;
	s_client_login = login;
	s_client_key = key_hex;
	s_client_register = register_account;
	s_client_approved = false;
	s_client_remembered = false;
	// Persist only when the server confirms the account. A mistyped password,
	// occupied nickname or offline server must not lock the registration form.
	return true;
}

bool client_has_credentials()
{
	client_load_credentials();
	return !s_client_login.empty() && !s_client_key.empty();
}

LPCSTR client_login()
{
	client_load_credentials();
	return s_client_login.c_str();
}

u8 client_role()
{
	if (firebase_enabled()) return s_client_role;
	client_load_credentials();
	return s_client_role;
}

static xr_string client_device_key()
{
    // Prefer the firmware system UUID. Never send SMBIOS data or serials.
    xr_string identity;
    const DWORD provider = 0x52534d42; // 'RSMB'
    const UINT size = GetSystemFirmwareTable(provider, 0, nullptr, 0);
    if (size >= 8 && size <= 1024 * 1024)
    {
        xr_vector<u8> firmware(size);
        if (GetSystemFirmwareTable(provider, 0, firmware.data(), size) == size)
        {
            for (u32 at = 8; at + 4 <= size;)
            {
                const u32 length = firmware[at + 1];
                if (length < 4 || at + length > size) break;
                if (firmware[at] == 1 && length >= 25)
                {
                    bool all_zero = true, all_ff = true;
                    for (u32 n = 8; n < 24; ++n) { all_zero &= firmware[at + n] == 0; all_ff &= firmware[at + n] == 255; }
                    if (!all_zero && !all_ff) identity = to_hex(&firmware[at + 8], 16);
                    break;
                }
                at += length;
                while (at + 1 < size && (firmware[at] || firmware[at + 1])) ++at;
                at += 2;
            }
        }
    }
    // Virtual machines / missing UUID: bind to the Windows installation.
    if (identity.empty())
    {
        HKEY key = nullptr;
        if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Cryptography", 0,
            KEY_QUERY_VALUE | KEY_WOW64_64KEY, &key) == ERROR_SUCCESS)
        {
            char guid[128] = {}; DWORD size = sizeof(guid), type = 0;
            if (RegQueryValueExA(key, "MachineGuid", nullptr, &type, (BYTE*)guid, &size) == ERROR_SUCCESS &&
                type == REG_SZ && size > 1 && size <= sizeof(guid) && guid[size - 1] == 0) identity = guid;
            RegCloseKey(key);
        }
    }
    if (identity.empty()) return xr_string();
    u8 digest[32];
    const char salt[] = "NetAnomaly device binding v1";
    if (!pbkdf2(identity.data(), u32(identity.size()), salt, sizeof(salt) - 1, 1000, digest, sizeof(digest))) return xr_string();
    return to_hex(digest, sizeof(digest));
}

#include "netcoop_firebase.inc"

struct StorageRequest
{
    bool active=false; u8 op=0,slot=1; u16 index=0; u32 revision=0; xr_string id;
};
static StorageRequest s_storage_request;
void storage_write_auth(NET_Packet& P)
{
    if (!s_storage_request.active || s_client_character_slot) return;
    P.w_u32(0x54535a4c); P.w_u8(s_storage_request.op); P.w_u8(s_storage_request.slot);
    P.w_u16(s_storage_request.index); P.w_u32(s_storage_request.revision); P.w_stringZ(s_storage_request.id.c_str());
    s_storage_request.active=false;
}
bool script_storage_prepare(int op,int slot,int index,int revision)
{
    if (g_pGameLevel || op<0 || op>2 || slot<1 || slot>10 || index<0 || index>511) return false;
    u8 nonce[16]; if (BCryptGenRandom(nullptr,nonce,sizeof(nonce),BCRYPT_USE_SYSTEM_PREFERRED_RNG)!=0) return false;
    s_storage_request.active=true; s_storage_request.op=u8(op); s_storage_request.slot=u8(slot);
    s_storage_request.index=u16(index); s_storage_request.revision=u32(revision); s_storage_request.id=to_hex(nonce,sizeof(nonce));
    return true;
}
void client_write_auth(NET_Packet& P)
{
	client_load_credentials();
    const bool cloud = firebase_enabled() && !s_firebase_session.id.empty();
	P.w_u8(cloud ? 3 : s_client_register ? auth_register : auth_login);
	P.w_stringZ(cloud ? s_firebase_session.username.c_str() : s_client_login.c_str());
	P.w_stringZ(cloud ? s_firebase_session.id.c_str() : s_client_key.c_str());
    P.w_u8(s_client_character_slot);
    P.w_stringZ(s_client_character_name.empty() ? s_client_login.c_str() : s_client_character_name.c_str());
    P.w_stringZ(s_client_character_faction.c_str());
    P.w_u8(s_client_character_economy);
    P.w_stringZ(s_client_character_name.empty() ? "device_pda_1" : s_client_character_loadout.c_str());
    P.w_stringZ(client_device_key().c_str());
    if (cloud) { P.w_stringZ(s_client_description.c_str()); P.w_stringZ(s_client_history.c_str()); }
	storage_write_auth(P);
	s_client_register = false;
	s_client_role = role_none;
    s_client_role_verified = false;
}

void client_on_auth_result(NET_Packet& P)
{
	client_marks_reset();
	const u8 ok = P.r_u8();
	const u8 role = P.r_u8();
	string512 message;
	if (!read_string(P, message, sizeof(message)))
		xr_strcpy(message, "");

	s_client_role = ok ? role : u8(role_none);
    s_client_role_verified = !!ok;
    const bool cloud = firebase_enabled() && !s_firebase_session.id.empty();
	if (ok) { s_client_approved = true; if (!cloud) client_store_credentials(); }
    else if (!xr_strcmp(message, "Registration pending administrator approval") || !xr_strcmp(message, "Registration rejected by administrator"))
    { s_client_approved = false; if (!cloud) client_store_credentials(); }
    else if (!cloud && !s_client_remembered)
    {
        s_client_login.clear(); s_client_key.clear();
        s_client_loaded = false; client_load_credentials();
    }
	Msg("%s [Lost Zone] %s", ok ? "*" : "!", message);
    if (ok && P.r_elapsed())
    {
        char names[1024];
        if (read_string(P, names, sizeof(names)))
        {
            ::luabind::functor<void> cache;
            if (ai().script_engine().functor("netcoop_login_ui.cache_characters", cache)) cache(names);
            char previews[14336];
            if (P.r_elapsed() && read_string(P, previews, sizeof(previews)) && previews[0] && ai().script_engine().functor("netcoop_login_ui.cache_previews", cache)) cache(previews);
        }
    }
    xr_string storage_reply;
    char storage[14336];
    if (ok && P.r_elapsed() && read_string(P,storage,sizeof(storage))) storage_reply=storage;
	call_lua("netcoop_client_compat.on_auth_result", !!ok, s_client_role, message);
    if (!storage_reply.empty())
    {
        ::luabind::functor<void> callback;
        if (ai().script_engine().functor("netcoop_login_ui.on_storage_result",callback)) callback(storage_reply.c_str());
    }
}

static bool s_trade_refresh = false;

void client_on_trade_result(NET_Packet& P)
{
	const u8 ok = P.r_u8();
	string512 message;
	if (!read_string(P, message, sizeof(message)))
		xr_strcpy(message, "");
	Msg("%s [Lost Zone] trade: %s", ok ? "*" : "!", message);
	s_trade_refresh = true;
	call_lua("netcoop_client_compat.on_trade_result", !!ok, s_client_role, message);
}

bool client_take_trade_refresh()
{
	const bool refresh = s_trade_refresh;
	s_trade_refresh = false;
	return refresh;
}

void client_on_server_text(LPCSTR text)
{
	::luabind::functor<void> f;
	if (ai().script_engine().functor("netcoop_client_compat.on_server_text", f))
	{
		try
		{
			f(text);
		}
		catch (...)
		{
		}
	}
}

void client_send_command(LPCSTR text)
{
	if (!text || !xr_strlen(text) || xr_strlen(text) > 4000 || !g_pGameLevel)
		return;
	NET_Packet P;
	P.w_begin(M_NETANOMALY_CMD);
	P.w_stringZ(text);
	Level().Send(P, net_flags(TRUE, TRUE));
}

// Lua entry points.
bool script_login(LPCSTR login, LPCSTR password, bool register_account)
{
	if (!register_account && password && !password[0])
    {
        client_load_credentials();
        return login && s_client_login == login && key_valid(s_client_key.c_str());
    }
    return client_set_credentials(login, password, register_account);
}

bool client_admin_authorized() { return s_client_role_verified && s_client_role == role_admin; }
int script_role() { return client_role(); }
LPCSTR script_account() { return client_login(); }
int script_account_state() { return !client_has_credentials() || !s_client_remembered ? 0 : s_client_approved ? 2 : 1; }
static IRenderVisual* s_preview_visual = nullptr;
static xr_string s_preview_name, s_preview_motion, s_preview_item_name;
static IRenderVisual* s_preview_item = nullptr;
static Fmatrix s_preview_item_offset;
static bool s_preview_armed = false;
static u32 s_preview_torso_restart = 0;
static xr_string s_preview_torso_motion;
static float s_preview_heading = 0.f;
static int s_preview_facing_axis = 0;
static bool s_preview_facing_ready = false;
static u32 s_preview_restart = 0;
static bool s_preview_seated=false;
static u32 s_preview_idle_change=0,s_preview_frame=0;
static xr_vector<shared_str> s_preview_seated_motions;
static u32 s_preview_idle_seed=0x31415926;
static u32 preview_random() { s_preview_idle_seed=1664525u*s_preview_idle_seed+1013904223u; return s_preview_idle_seed; }
// Preview tracks are advanced by the continual menu clock in draw(), once.
// CalculateBones must not advance them again using the world clock.
static struct PreviewTracks : IUpdateTracksCallback
{
    bool operator()(float,IKinematicsAnimated&) override { return true; }
} s_preview_tracks;
static void preview_loop(IKinematicsAnimated* skeleton,MotionID motion,float speed)
{
    struct Loop : IterateBlendsCallback
    {
        MotionID id; float rate;
        Loop(MotionID motion,float speed):id(motion),rate(speed) {}
        void operator()(CBlend& blend) override
        {
            if (blend.motionID.slot!=id.slot || blend.motionID.idx!=id.idx) return;
            blend.stop_at_end=FALSE; blend.fall_at_end=FALSE;
            blend.stop_at_end_callback=FALSE; blend.playing=TRUE; blend.speed=rate;
        }
    } callback(motion,speed);
    skeleton->LL_IterateBlends(callback);
}

void script_preview_clear()
{
    menu_room::reset();
    // Input and Lua callbacks can occur during rendering. Defer through the pool.
    if (s_preview_item) Render->model_Delete(s_preview_item, FALSE);
    if (s_preview_visual) Render->model_Delete(s_preview_visual, FALSE);
    s_preview_item_name.clear(); s_preview_armed = false;
    s_preview_torso_motion.clear(); s_preview_torso_restart = 0; s_preview_facing_ready = false;
    s_preview_name.clear(); s_preview_motion.clear(); s_preview_restart = 0;
    s_preview_seated=false; s_preview_idle_change=s_preview_frame=0; s_preview_seated_motions.clear();
}

bool script_preview_model(LPCSTR model, int pose)
{
    if (g_pGameLevel || !model || !Render->models_Exists(model)) return false;
    if (s_preview_name != model)
    {
        script_preview_clear();
        s_preview_visual = Render->model_Create(model);
        if (!Render->PrepareUIModel(s_preview_visual)) { script_preview_clear(); return false; }
        s_preview_name = model;
    }
    auto k = s_preview_visual->dcast_PKinematicsAnimated();
    if (!k) return true;
    LPCSTR motion = "norm_idle_0";

    s_preview_seated=pose==-2;
    k->SetUpdateTracksCalback(s_preview_seated ? &s_preview_tracks : nullptr);
    s_preview_armed = pose == -1 && s_preview_item;
    if (s_preview_seated)
    {
        s_preview_seated_motions.clear();
        for (LPCSTR candidate:{"animpoint_sit_low_idle_1","animpoint_sit_low_idle_rnd_1","animpoint_sit_low_idle_rnd_2","animpoint_sit_low_idle_rnd_3","animpoint_sit_low_idle_rnd_4"})
            if (k->ID_Cycle_Safe(candidate).valid()) s_preview_seated_motions.push_back(candidate);
        if (s_preview_seated_motions.empty())
            for (LPCSTR candidate:{"animpoint_sit_high_idle_1","jup_b15_zulus_sit_idle"})
                if(k->ID_Cycle_Safe(candidate).valid()) { s_preview_seated_motions.push_back(candidate); break; }
        if(s_preview_seated_motions.empty()) { script_preview_clear(); return false; }
        motion=s_preview_seated_motions.front().c_str();
        s_preview_idle_seed=Device.dwTimeContinual|1; s_preview_idle_change=Device.dwTimeContinual+12000;
        Msg("[Lost Zone] sofa preview: %s, %u available idle motions",motion,u32(s_preview_seated_motions.size()));
    }
    if (pose >= 0 && pose < int(rp_anims().size()))
        for (const auto& candidate : rp_anims()[pose].mid)
            if (k->ID_Cycle_Safe(candidate.c_str()).valid()) { motion = candidate.c_str(); break; }
    const MotionID id = k->ID_Cycle_Safe(motion);
    if (!id.valid()) return false;
    // Cancel previous RP tracks before starting the selected preview.
    k->PlayCycle("norm_idle_0", FALSE);
    k->UpdateTracks();
    auto bones = s_preview_visual->dcast_PKinematics();
    if (bones && !s_preview_facing_ready)
    {
        bones->CalculateBones_Invalidate(); bones->CalculateBones(TRUE);
        const u16 root = bones->LL_BoneID("bip01");
        if (root != BI_NONE)
        {
            const auto& transform = bones->LL_GetTransform(root);
            const Fvector axes[] = {transform.i,transform.j,transform.k};
            float largest = 0.f;
            for(int axis=0;axis<3;++axis)
            {
                const float length = axes[axis].x*axes[axis].x+axes[axis].z*axes[axis].z;
                if(length>largest) { largest=length;s_preview_facing_axis=axis; }
            }
            const auto& forward=axes[s_preview_facing_axis];
            s_preview_heading=atan2f(forward.x,forward.z);s_preview_facing_ready=true;
        }
    }
    s_preview_torso_motion.clear(); s_preview_torso_restart=0;
    s_preview_motion = motion;
    CBlend* blend = k->PlayCycle(id, FALSE);
    if (s_preview_seated) preview_loop(k,id,.94f);
    if (blend) { blend->speed = _min(blend->speed, 1.f); s_preview_restart = Device.dwTimeGlobal + u32(blend->timeTotal / _max(.1f, blend->speed) * 1000.f); }
    if (pose == -1)
    {
        LPCSTR torso = "norm_torso_0_aim_0";
        string128 armed;
        if (s_preview_item && pSettings->line_exist(s_preview_item_name.c_str(),"animation_slot"))
        {
            // Actor's slot zero uses animation set one.
            xr_sprintf(armed,"norm_torso_%u_aim_1",pSettings->r_u32(s_preview_item_name.c_str(),"animation_slot")+1);
            if(k->ID_Cycle_Safe(armed).valid()) torso=armed;
        }
        if(k->ID_Cycle_Safe(torso).valid())
        {
            s_preview_torso_motion=torso;
            if(auto torsoBlend=k->PlayCycle(torso,FALSE))
                s_preview_torso_restart=Device.dwTimeGlobal+u32(torsoBlend->timeTotal/_max(.1f,torsoBlend->speed)*1000.f);
        }
        if(k->ID_Cycle_Safe("head_idle_0").valid()) k->PlayCycle("head_idle_0",FALSE);
    }
    return true;
}

bool script_preview_weapon(LPCSTR section)
{
    if (s_preview_item) Render->model_Delete(s_preview_item, FALSE);
    s_preview_item_name.clear(); s_preview_armed = false;
    if (!section || !section[0]) return true;
    if (g_pGameLevel || !pSettings->section_exist(section) || !pSettings->line_exist(section, "visual")) return false;
    LPCSTR model = pSettings->r_string(section, "visual");
    if (!Render->models_Exists(model)) return false;
    s_preview_item = Render->model_Create(model);
    if (!Render->PrepareUIModel(s_preview_item)) { Render->model_Delete(s_preview_item, FALSE); return false; }
    Fvector position, orientation; position.set(0, 0, 0); orientation.set(0, 0, 0);
    if (pSettings->line_exist(section, "position")) position = pSettings->r_fvector3(section, "position");
    if (pSettings->line_exist(section, "orientation")) orientation = pSettings->r_fvector3(section, "orientation");
    orientation.mul(PI / 180.f); s_preview_item_offset.setHPB(orientation.x, orientation.y, orientation.z);
    s_preview_item_offset.translate_over(position); s_preview_item_name = section;
    return true;
}
// Project the actual room interaction points into the 1024 x 768 UI space.
Fvector2 script_preview_point(int object)
{
    Fvector point=menu_room::interaction(object);
    Fmatrix view, projection, combined;
    menu_room::matrices(view,projection);
    Fvector local; view.transform_tiny(local,point);
    Fvector2 result; result.set(-10000,-10000);
    if (local.z<=.08f) return result;
    combined.mul(projection, view); combined.transform(point);
    result.set((point.x + 1.f) * 512.f, (1.f - point.y) * 384.f); return result;
}

void script_preview_focus(int object) { menu_room::focus(object); }
// Room object under a UI point (1024 x 768), -1 when none; hover(-1) clears.
int script_preview_pick(float x, float y) { return menu_room::pick(x, y); }
void script_preview_hover(int object) { menu_room::hover(object); }
bool script_preview_ready() { return menu_room::ready(); }

void script_preview_draw()
{
    if (!s_preview_visual || g_pGameLevel) return;
    if (auto k = s_preview_visual->dcast_PKinematicsAnimated())
    {
        if (s_preview_seated)
        {
            const u32 now=Device.dwTimeContinual;
            if(now>=s_preview_idle_change)
            {
                s_preview_motion=s_preview_seated_motions[preview_random()%s_preview_seated_motions.size()].c_str();
                const MotionID id=k->ID_Cycle_Safe(s_preview_motion.c_str());
                if (k->PlayCycle(id,TRUE)) preview_loop(k,id,.90f+float(preview_random()%15)*.01f);
                s_preview_idle_change=now+12000+preview_random()%10000;
            }
            // The menu runs on a continual clock, independently of a paused game.
            k->LL_UpdateTracks(s_preview_frame ? _min(.066f,float(now-s_preview_frame)/1000.f) : 0.f,true,false);
            s_preview_frame=now;
        }
        if (!s_preview_seated && s_preview_restart && Device.dwTimeGlobal >= s_preview_restart)
        {
            CBlend* blend = k->PlayCycle(s_preview_motion.c_str(), FALSE);
            if (blend) { blend->speed = _min(blend->speed, 1.f); s_preview_restart = Device.dwTimeGlobal + u32(blend->timeTotal / _max(.1f, blend->speed) * 1000.f); }
        }
        if (s_preview_torso_restart && Device.dwTimeGlobal >= s_preview_torso_restart)
            if (auto blend=k->PlayCycle(s_preview_torso_motion.c_str(),FALSE))
                s_preview_torso_restart=Device.dwTimeGlobal+u32(blend->timeTotal/_max(.1f,blend->speed)*1000.f);
        if(!s_preview_seated) k->UpdateTracks();
    }
    float heading=menu_room::seat_heading();
    if (auto k = s_preview_visual->dcast_PKinematics())
    {
        k->CalculateBones(TRUE);
        const u16 root=k->LL_BoneID("bip01");
        if(s_preview_facing_ready && root!=BI_NONE)
        {
            const auto& transform=k->LL_GetTransform(root);
            const Fvector axes[]={transform.i,transform.j,transform.k};
            const auto& forward=axes[s_preview_facing_axis];
            if(forward.x*forward.x+forward.z*forward.z>EPS_S)
                heading+=s_preview_heading-atan2f(forward.x,forward.z);
        }
    }
    Fmatrix world; world.rotateY(heading);
    // The preview's lowest bound rests on the room's y=0 floor.
    world.c.y=_max(-.25f,_min(.25f,-s_preview_visual->getVisData().box.min.y));
    if(s_preview_seated)
    {
        if(auto skeleton=s_preview_visual->dcast_PKinematics())
        {
            const u16 pelvis=skeleton->LL_BoneID("bip01_pelvis");
            if(pelvis!=BI_NONE)
            {
                Fvector local; world.transform_dir(local,skeleton->LL_GetTransform(pelvis).c);
                world.c.sub(menu_room::seat_position(),local);
            }
        }
    }
    Fmatrix itemWorld;
    IRenderVisual* item = nullptr;
    if (s_preview_item && s_preview_armed)
    {
        auto skeleton = s_preview_visual->dcast_PKinematics();
        const u16 right = skeleton ? skeleton->LL_BoneID("bip01_r_finger1") : BI_NONE;
        const u16 left = skeleton ? skeleton->LL_BoneID("bip01_l_finger1") : BI_NONE;
        if (right != BI_NONE && left != BI_NONE)
        {
            const Fmatrix& r = skeleton->LL_GetTransform(right);
            const Fmatrix& l = skeleton->LL_GetTransform(left);
            Fvector direction, axis, normal;
            direction.sub(l.c, r.c);
            Fmatrix grip = r;
            if (direction.square_magnitude() > EPS_S)
            {
                direction.normalize(); axis.crossproduct(r.j, direction);
                if (axis.square_magnitude() < EPS_S) axis.crossproduct(r.i, direction);
                if (axis.square_magnitude() > EPS_S)
                {
                    axis.normalize(); normal.crossproduct(direction, axis); normal.normalize();
                    grip.set(axis, normal, direction, r.c);
                }
            }
            Fmatrix local; local.mul_43(grip, s_preview_item_offset); itemWorld.mul_43(world, local);
            if (auto animated = s_preview_item->dcast_PKinematicsAnimated()) animated->UpdateTracks();
            if (auto bones = s_preview_item->dcast_PKinematics()) bones->CalculateBones(TRUE);
            item = s_preview_item;
        }
    }
    if(s_preview_seated && s_preview_item)
    {
        item=s_preview_item; itemWorld.setHPB(PI*.6f,0,PI*.5f);
        itemWorld.c.set(.3f,.70f,.57f);
        if (auto k=item->dcast_PKinematicsAnimated()) k->UpdateTracks();
        if (auto k=item->dcast_PKinematics()) k->CalculateBones(TRUE);
    }
    Render->DrawUIModel(s_preview_visual, world, item, item ? &itemWorld : nullptr);
}
void script_command(LPCSTR text) { client_send_command(text); }

// Lua trade UIs (GAMMA ui_inventory) ask the server for a deal: the items
// (space separated ids) the actor sells to or buys from the partner. The
// server prices and executes it; M_NETCOOP_TRADE_RESULT reports back.
bool script_trade(u16 partner_id, bool actor_sells, LPCSTR ids)
{
	if (!pure_client() || !ids)
		return false;
	xr_vector<u16> list;
	for (LPCSTR p = ids; *p;)
	{
		char* end = 0;
		const unsigned long id = strtoul(p, &end, 10);
		if (end == p)
		{
			++p;
			continue;
		}
		if (id < 0xffff)
			list.push_back(u16(id));
		p = end;
	}
	if (list.empty() || list.size() > 256)
		return false;
	NET_Packet P;
	P.w_begin(M_NETCOOP_TRADE);
	P.w_u16(partner_id);
	P.w_u8(actor_sells ? trade_actor_sells : trade_actor_buys);
	P.w_u16(u16(list.size()));
	for (u32 i = 0; i < list.size(); ++i)
		P.w_u16(list[i]);
	Level().Send(P, net_flags(TRUE, TRUE));
	return true;
}
bool script_pure_client() { return pure_client(); }

// ---------------------------------------------------------------------------
// server: account storage
// ---------------------------------------------------------------------------
struct Account
{
    xr_string firebase_uid;
	// 0: pending, 1: approved, 2: rejected. Old account files default to approved.
	u8 approval = 1;
	xr_string device;
	xr_string login; // as registered
	u8 role;
	xr_string salt;
	xr_string hash;
	bool has_money;
	u32 money;
	u32 failures;
	u32 locked_until;
};

typedef xr_map<xr_string, Account> Accounts;
static Accounts s_accounts;
static bool s_accounts_loaded = false;
static bool s_accounts_dirty = false;

static void accounts_path(string_path& path)
{
	FS.update_path(path, "$app_data_root$", "netcoop_accounts.txt");
}

static void accounts_load()
{
	if (s_accounts_loaded)
		return;
	s_accounts_loaded = true;

	string_path path;
	accounts_path(path);
	FILE* f = fopen(path, "rb");
	if (!f)
		return;

	char line[512];
	while (fgets(line, sizeof(line), f))
	{
		line[strcspn(line, "\r\n")] = 0;
		if (!line[0] || line[0] == '#')
			continue;

		// login|role|salt|hash|money
		char* fields[8] = {};
		u32 count = 0;
		char* cursor = line;
		while (count < 8)
		{
			fields[count++] = cursor;
			char* sep = strchr(cursor, '|');
			if (!sep)
				break;
			*sep = 0;
			cursor = sep + 1;
		}
		if (count < 4 || !login_valid(fields[0]))
			continue;

		Account a;
        a.firebase_uid = count >= 8 ? fields[7] : "";
		a.approval = count >= 7 ? (!xr_strcmp(fields[6], "pending") ? 0 : !xr_strcmp(fields[6], "rejected") ? 2 : 1) : 1;
		a.login = fields[0];
		a.device = count >= 6 && key_valid(fields[5]) ? fields[5] : "";
		a.role = !xr_strcmp(fields[1], "admin") ? u8(role_admin) : u8(role_player);
		a.salt = fields[2];
		a.hash = fields[3];
		a.has_money = count >= 5 && fields[4][0] && fields[4][0] != '-';
		a.money = a.has_money ? (u32)strtoul(fields[4], NULL, 10) : 0;
		a.failures = 0;
		a.locked_until = 0;

		xr_string key = a.login;
		to_lower(key);
		s_accounts[key] = a;
	}
	fclose(f);
	Msg("[Lost Zone] loaded %u account(s) from %s", (u32)s_accounts.size(), path);
}

static void accounts_save()
{
	if (!s_accounts_dirty)
		return;

	string_path path, temp;
	accounts_path(path);
	xr_sprintf(temp, "%s.tmp", path);
	FILE* f = fopen(temp, "wb");
	if (!f)
	{
		Msg("! [Lost Zone] cannot write %s", temp);
		return;
	}
	fprintf(f, "# NetAnomaly accounts: login|role|salt|pbkdf2-sha256|money|device-digest|approval\n");
	for (Accounts::const_iterator it = s_accounts.begin(); it != s_accounts.end(); ++it)
	{
		const Account& a = it->second;
		if (a.has_money)
			fprintf(f, "%s|%s|%s|%s|%u|%s|%s|%s\n", a.login.c_str(), role_name(a.role), a.salt.c_str(), a.hash.c_str(), a.money, a.device.c_str(), a.approval == 0 ? "pending" : a.approval == 2 ? "rejected" : "approved", a.firebase_uid.c_str());
		else
			fprintf(f, "%s|%s|%s|%s|-|%s|%s|%s\n", a.login.c_str(), role_name(a.role), a.salt.c_str(), a.hash.c_str(), a.device.c_str(), a.approval == 0 ? "pending" : a.approval == 2 ? "rejected" : "approved", a.firebase_uid.c_str());
	}
	fclose(f);
	if (!MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
	{
		Msg("! [Lost Zone] cannot replace %s", path);
		return;
	}
	s_accounts_dirty = false;
}

static Account* account_find(LPCSTR login)
{
	accounts_load();
	xr_string key = login;
	to_lower(key);
	Accounts::iterator it = s_accounts.find(key);
	return it == s_accounts.end() ? NULL : &it->second;
}

bool server_reset_device(LPCSTR login)
{
    Account* account = account_find(login);
    if (!account) return false;
    account->device.clear(); s_accounts_dirty = true; accounts_save();
    return true;
}

bool script_registration_decide(LPCSTR login, bool accept)
{
    if (!enabled() || !g_pGameLevel || !Level().Server || !login || !login_valid(login)) return false;
    Account* account = account_find(login);
    if (!account || account->approval != 0) return false;
    account->approval = accept ? 1 : 2;
    s_accounts_dirty = true; accounts_save();
    Msg("[Lost Zone] registration '%s' %s", login, accept ? "approved" : "rejected");
    return true;
}

struct NotifyRegistration
{
    xrServer* server;
    LPCSTR login;
    void operator()(IClient* client) const
    {
        xrClientData* CL = static_cast<xrClientData*>(client);
        if (!CL || CL->flags.bLocal || CL->netcoop_role != role_admin) return;
        NET_Packet P; P.w_begin(M_NETCOOP_SCRIPT);
        P.w_stringZ("registration"); P.w_stringZ(login);
        server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
    }
};

static bool server_hash(LPCSTR client_key, const xr_string& salt_hex, xr_string& out)
{
	u8 hash[key_bytes];
	if (!pbkdf2(client_key, xr_strlen(client_key), salt_hex.c_str(), (u32)salt_hex.size(), server_hash_iterations,
	            hash, key_bytes))
		return false;
	out = to_hex(hash, key_bytes);
	return true;
}

bool server_account_money(LPCSTR login, u32& money)
{
	Account* a = login && login[0] ? account_find(login) : NULL;
	if (!a || !a->has_money)
		return false;
	money = a->money;
	return true;
}

bool server_set_role(LPCSTR login, u8 role, xr_string& message)
{
	Account* a = login ? account_find(login) : NULL;
	if (!a)
	{
		message = "account not found";
		return false;
	}
	a->role = role;
	if (role == role_admin) a->approval = 1; // console bootstrap of the first administrator
	s_accounts_dirty = true;
	accounts_save();
	message = a->login;
	message += " is now ";
	message += role_name(role);
	return true;
}

void server_list_accounts(xr_string& out)
{
	accounts_load();
	string256 line;
	xr_sprintf(line, "%u account(s):", (u32)s_accounts.size());
	out = line;
	for (Accounts::const_iterator it = s_accounts.begin(); it != s_accounts.end(); ++it)
	{
		const Account& a = it->second;
		if (a.has_money)
			xr_sprintf(line, "\n  %-20s %-7s %u RU", a.login.c_str(), role_name(a.role), a.money);
		else
			xr_sprintf(line, "\n  %-20s %-7s -", a.login.c_str(), role_name(a.role));
		out += line;
	}
}

static u32 storage_capacity(bool safe);
static u32 storage_section_cost(LPCSTR section);
#include "netcoop_characters.inc"
#include "netcoop_storage.inc"
#include "netcoop_pda.inc"
#include "netcoop_marks.inc"

// ---------------------------------------------------------------------------
// server: authentication
// ---------------------------------------------------------------------------
struct LoginInUse
{
	xr_string login;
	xrClientData* self;
	bool operator()(IClient* client) const
	{
		xrClientData* other = static_cast<xrClientData*>(client);
		if (other == self || !other->netcoop_login.size())
			return false;
		xr_string name = other->netcoop_login.c_str();
		to_lower(name);
		return name == login;
	}
};

static void send_auth_result(xrServer* server, xrClientData* CL, bool ok, u8 role, LPCSTR message, LPCSTR storage=nullptr)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_AUTH_RESULT);
	P.w_u8(ok ? 1 : 0);
	P.w_u8(role);
	P.w_stringZ(message);
    if (ok)
    {
        xr_string names;
        for (u8 slot = 1; slot <= (role == role_admin ? 10 : 1); ++slot)
        {
            Character* character = character_load(CL->netcoop_login.c_str(), slot);
            if (slot > 1) names += "|";
            if (character) names += character->name;
        }
        P.w_stringZ(names.c_str());
        xr_string previews;
        for (u8 slot = 1; slot <= (role == role_admin ? 10 : 1); ++slot)
        {
            Character* character = character_load(CL->netcoop_login.c_str(), slot);
            xr_string visual = "actors\\stalker_neutral\\stalker_neutral_1.ogf", items;
            if (character)
                for (const auto& item : character->items)
                {
                    SInvItemPlace place; place.value = item.place;
                    if (!item.parent && place.type == eItemPlaceSlot && place.slot_id == OUTFIT_SLOT && pSettings->line_exist(item.section.c_str(), "actor_visual"))
                        visual = pSettings->r_string(item.section.c_str(), "actor_visual");
                    if (items.size() + item.section.size() < 1100) { if (!items.empty()) items += ","; items += item.section; }
                }
            previews += visual + "|" + (character ? character->faction : "stalker") + "|" + items + "\n";
        }
        // Storage snapshots occupy a separate bounded payload. Full account
        // previews can approach the packet limit and are omitted in that case.
        P.w_stringZ(storage ? "" : previews.c_str());
        if (storage) P.w_stringZ(storage);
    }
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
}

static void reject(xrServer* server, xrClientData* CL, LPCSTR message)
{
	Msg("! [Lost Zone] login rejected for 0x%08x: %s", CL->ID.value(), message);
	send_auth_result(server, CL, false, role_none, message);
	string512 reason;
	xr_sprintf(reason, "@%s", message);
	server->DisconnectClient(CL, reason);
}

// The server's PBKDF2 (60000 rounds) took ~100 ms of a frame for every
// login; with many players joining the world stuttered for everyone. It runs
// on a worker thread; the result is applied on the main thread by
// server_auth_update, and the client's player state waits for it.
struct PendingAuth
{
    bool firebase = false;
    xr_string firebase_api, firebase_uid, description, history;
	xr_string device;
	ClientID client;
	xr_string login;
	xr_string key;
	xr_string salt;
	bool create;
    StorageRequest storage;
	u8 slot = 1, economy = 1;
	xr_string character_name, faction = "stalker", loadout;
	xr_string hash;
	bool hashed;
	volatile LONG done;
	NET_Packet* player_state; // M_CREATE_PLAYER_STATE that arrived meanwhile
};
static xr_vector<PendingAuth*> s_pending_auth;

static void auth_worker(void* data)
{
	PendingAuth* pending = static_cast<PendingAuth*>(data);
    if (pending->firebase)
    {
        FirebaseSession identity; std::string error;
        pending->hashed = firebase_lookup(pending->key.c_str(), pending->firebase_api.c_str(), identity, error) &&
            identity.verified && identity.username == pending->login.c_str() && identity.uid.size() <= 128 &&
            identity.uid.find_first_of("|\r\n") == std::string::npos;
        if (pending->hashed) pending->firebase_uid = identity.uid.c_str();
    }
    else pending->hashed = server_hash(pending->key.c_str(), pending->salt, pending->hash);
	InterlockedExchange(&pending->done, 1);
}

static PendingAuth* pending_auth_of(ClientID id)
{
	for (PendingAuth* pending : s_pending_auth)
		if (pending->client == id)
			return pending;
	return NULL;
}

void server_on_auth(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || CL->flags.bLocal || CL == server->GetServerClient())
		return;
	if (CL->netcoop_role != role_none || pending_auth_of(CL->ID))
		return; // already authenticated or being checked on this connection

	if (P.r_elapsed() < 1)
	{
		reject(server, CL, "Malformed login request");
		return;
	}
	const u8 mode = P.r_u8();
	char login[64];
	char key[4097];
	if (!read_string(P, login, sizeof(login)) || !read_string(P, key, sizeof(key)) || !login_valid(login) ||
		(mode == 3 ? !firebase_enabled() || xr_strlen(key) < 100 : !key_valid(key)))
	{
		reject(server, CL, "Invalid login or password");
		return;
	}

	LoginInUse in_use;
	in_use.login = login;
	to_lower(in_use.login);
	in_use.self = CL;
	if (server->FindClient(in_use))
	{
		reject(server, CL, "This account is already online");
		return;
	}

	PendingAuth* pending = xr_new<PendingAuth>();
    pending->firebase = mode == 3;
    pending->firebase_api = s_firebase_api;
	pending->client = CL->ID;
	pending->login = login;
	pending->key = key;
	pending->hashed = false;
	pending->done = 0;
	pending->player_state = NULL;
    if (P.r_elapsed())
    {
        char name[64], faction[32], loadout[4097];
        pending->slot = P.r_u8();
        if (!read_string(P, name, sizeof(name)) || !read_string(P, faction, sizeof(faction)) || P.r_elapsed() < 1)
        { xr_delete(pending); reject(server, CL, "Invalid character request"); return; }
        pending->economy = P.r_u8();
        if (!read_string(P, loadout, sizeof(loadout)))
        { xr_delete(pending); reject(server, CL, "Invalid character loadout"); return; }
        pending->character_name = name; pending->faction = faction; pending->loadout = loadout;
        if (P.r_elapsed())
        {
            char device[65];
            if (!read_string(P, device, sizeof(device)) || !key_valid(device))
            { xr_delete(pending); reject(server, CL, "Device identity unavailable"); return; }
            pending->device = device;
            if (pending->firebase)
            {
                char description[513], history[1537];
                if (!read_string(P, description, sizeof(description)) || !read_string(P, history, sizeof(history)))
                { xr_delete(pending); reject(server, CL, "Invalid character profile"); return; }
                pending->description = description; pending->history = history;
            }
            if (P.r_elapsed())
            {
                char id[33];
                if (pending->slot!=0 || P.r_elapsed()<13 || P.r_u32()!=0x54535a4c)
                { xr_delete(pending); reject(server,CL,"Invalid storage request"); return; }
                pending->storage.active=true; pending->storage.op=P.r_u8(); pending->storage.slot=P.r_u8();
                pending->storage.index=P.r_u16(); pending->storage.revision=P.r_u32();
                if (!read_string(P,id,sizeof(id)) || xr_strlen(id)!=32 || P.r_elapsed() || pending->storage.op>2)
                { xr_delete(pending); reject(server,CL,"Invalid storage request"); return; }
                pending->storage.id=id;
            }
        }
    }
    else
    {
        // Older clients and headless test bots keep the first slot.
        pending->character_name = login;
        pending->loadout = "device_pda_1";
    }

	Account* a = account_find(login);
	pending->create = mode == auth_register || ((mode == auth_auto || pending->firebase) && !a);
	if (pending->create)
	{
		if (a)
		{
			xr_delete(pending);
			reject(server, CL, "Account already exists, use Login");
			return;
		}
		u8 salt[salt_bytes];
		if (!random_bytes(salt, salt_bytes))
		{
			xr_delete(pending);
			reject(server, CL, "Server error: no random source");
			return;
		}
		pending->salt = to_hex(salt, salt_bytes);
	}
	else
	{
		if (a && !pending->firebase && !a->firebase_uid.empty())
        { xr_delete(pending); reject(server, CL, "Use Firebase sign-in for this account"); return; }
		if (!a)
		{
			xr_delete(pending);
			reject(server, CL, "Unknown account, use Register");
			return;
		}
		const u32 now = GetTickCount();
		if (a->locked_until && now < a->locked_until)
		{
			xr_delete(pending);
			reject(server, CL, "Too many failed logins, try again in a minute");
			return;
		}
		pending->salt = a->salt;
	}
	s_pending_auth.push_back(pending);
	thread_spawn(auth_worker, "netcoop-auth", 0, pending);
}

static void finish_auth(xrServer* server, PendingAuth* pending)
{
	xrClientData* CL = static_cast<xrClientData*>(server->ID_to_client(pending->client));
	if (!CL)
		return; // disconnected meanwhile

	LoginInUse in_use;
	in_use.login = pending->login;
	to_lower(in_use.login);
	in_use.self = CL;
	if (server->FindClient(in_use))
	{
		reject(server, CL, "This account is already online");
		return;
	}
	if (!pending->hashed)
	{
		reject(server, CL, pending->firebase ? "Firebase identity or verified email could not be confirmed" : "Server error: cannot hash password");
		return;
	}

	Account* a = account_find(pending->login.c_str());
	if (pending->create)
	{
		if (a)
		{
			reject(server, CL, "Account already exists, use Login");
			return;
		}
		Account created;
        created.firebase_uid = pending->firebase_uid;
		created.login = pending->login;
		created.role = role_player; // only the server console grants admin
		created.approval = 0;
		created.device = pending->device;
		created.salt = pending->salt;
		created.hash = pending->firebase ? "firebase" : pending->hash;
		created.has_money = false;
		created.money = 0;
		created.failures = 0;
		created.locked_until = 0;
		s_accounts[in_use.login] = created;
		s_accounts_dirty = true;
		accounts_save();
		a = &s_accounts[in_use.login];
		Msg("[Lost Zone] account '%s' registered", pending->login.c_str());
		NotifyRegistration notice = {server, pending->login.c_str()};
		server->ForEachClientDo(notice);
	}
	else
	{
		if (!a || a->salt != pending->salt)
		{
			reject(server, CL, "Unknown account, use Register");
			return;
		}
		if (pending->firebase ? a->firebase_uid.empty() || a->firebase_uid != pending->firebase_uid : !constant_time_equal(pending->hash, a->hash))
		{
			if (++a->failures >= 5)
			{
				a->failures = 0;
				a->locked_until = GetTickCount() + 60000;
			}
			reject(server, CL, "Wrong password");
			return;
		}
		a->failures = 0;
		a->locked_until = 0;
	}

    if (!a->device.empty() && !constant_time_equal(a->device, pending->device))
    {
        reject(server, CL, "Account is bound to another device; contact the server administrator");
        return;
    }
    if (a->device.empty() && !pending->device.empty())
    { a->device = pending->device; s_accounts_dirty = true; accounts_save(); }
	if (a->approval != 1)
	{
		reject(server, CL, a->approval == 0 ? "Registration pending administrator approval" : "Registration rejected by administrator");
		return;
	}
	CL->netcoop_login = a->login.c_str();
    CL->netcoop_role = a->role;
    // Slot zero authenticates the front-end and fetches slots without creating
    // an Actor or touching an existing character's inventory.
    if (pending->slot == 0)
    {
        if (pending->storage.active)
        {
            const xr_string result=storage_execute(server,CL,pending->storage);
            send_auth_result(server,CL,true,a->role,"Account verified",result.c_str());
        }
        else send_auth_result(server, CL, true, a->role, "Account verified");
        server->DisconnectClient(CL, "@Account verified");
        return;
    }
    if (!character_select(CL, pending->slot, pending->character_name.c_str(), pending->faction.c_str(), pending->economy, pending->loadout.c_str()))
    {
        CL->netcoop_login = NULL;
        reject(server, CL, "Character unavailable or starting items exceed the point budget");
        return;
    }
    if (Character* character = character_load(CL->netcoop_login.c_str(), pending->slot))
        if (!character->initialized && pending->firebase)
        { character->description = pending->description; character->history = pending->history; character_save(*character); }
	CL->netcoop_role = a->role;
	CL->name = a->login.c_str();

	string256 message;
	xr_sprintf(message, "Logged in as %s (%s)", a->login.c_str(), role_name(a->role));
	Msg("[Lost Zone] client 0x%08x %s", CL->ID.value(), message);
	send_auth_result(server, CL, true, a->role, message);
    if (a->role == role_admin)
        for (const auto& entry : s_accounts)
            if (entry.second.approval == 0)
            {
                NotifyRegistration notice = {server, entry.second.login.c_str()};
                notice(CL);
            }

	if (pending->player_state)
		server->game->AddDelayedEvent(*pending->player_state, GAME_EVENT_CREATE_PLAYER_STATE, 0, CL->ID);
}

void server_auth_update(xrServer* server)
{
	for (u32 i = 0; i < s_pending_auth.size();)
	{
		PendingAuth* pending = s_pending_auth[i];
		if (!InterlockedCompareExchange(&pending->done, 0, 0))
		{
			++i;
			continue;
		}
		s_pending_auth.erase(s_pending_auth.begin() + i);
		finish_auth(server, pending);
		SecureZeroMemory(&pending->key[0], pending->key.size());
		xr_delete(pending->player_state);
		xr_delete(pending);
	}
}

bool server_defer_player_state(xrClientData* CL, NET_Packet& P)
{
	PendingAuth* pending = CL ? pending_auth_of(CL->ID) : NULL;
	if (!pending)
		return false;
	if (!pending->player_state)
		pending->player_state = xr_new<NET_Packet>();
	CopyMemory(pending->player_state, &P, sizeof(NET_Packet));
	return true;
}

bool server_requires_login(xrServer* server, xrClientData* CL)
{
	return enabled() && CL && !CL->flags.bLocal && CL != server->GetServerClient() && CL->netcoop_role == role_none;
}

static xrCriticalSection s_pending_lock;
static xr_vector<u16> s_pending_actor_destroy;
static void server_release_task_manager(u16 actor_id);

static void store_money(xrClientData* CL)
{
	if (!CL || !CL->netcoop_login.size() || !CL->owner || CL->netcoop_character_slot != 1)
		return;
	CSE_ALifeTraderAbstract* trader = smart_cast<CSE_ALifeTraderAbstract*>(CL->owner);
	if (!trader)
		return;
	Account* a = account_find(CL->netcoop_login.c_str());
	if (!a)
		return;
	if (!a->has_money || a->money != trader->m_dwMoney)
	{
		a->has_money = true;
		a->money = trader->m_dwMoney;
		s_accounts_dirty = true;
	}
}

void server_on_client_disconnect(xrClientData* CL)
{
	if (!enabled() || !CL)
		return;
	store_money(CL);
	accounts_save();

	// Remove the player's Actor instead of migrating it to the server, so a
	// reconnect does not leave an abandoned body in the world. This runs on
	// the transport thread; the game object is destroyed from server_update.
	if (!CL->flags.bLocal && CL->owner && smart_cast<CSE_ALifeCreatureActor*>(CL->owner))
	{
		s_pending_lock.Enter();
		s_pending_actor_destroy.push_back(CL->owner->ID);
		s_pending_lock.Leave();
	}
}

// The disconnected client no longer exists, so the server takes over the
// Actor and everything it carries before destroying it.
static void give_to_server(xrServer* server, CSE_Abstract* entity, u32 depth)
{
	if (!entity || depth > 8)
		return;
	entity->owner = static_cast<xrClientData*>(server->GetServerClient());
	for (u32 i = 0; i < entity->children.size(); ++i)
		give_to_server(server, server->game->get_entity_from_eid(entity->children[i]), depth + 1);
}

static void destroy_pending_actors(xrServer* server)
{
	xr_vector<u16> ids;
	s_pending_lock.Enter();
	ids.swap(s_pending_actor_destroy);
	s_pending_lock.Leave();

	for (u32 i = 0; i < ids.size() && g_pGameLevel; ++i)
	{
		CGameObject* actor_object = smart_cast<CGameObject*>(Level().Objects.net_Find(ids[i]));
		if (actor_object && smart_cast<CActor*>(actor_object) && server->GetServerClient())
		{
            server_character_save_actor(ids[i]);
            s_actor_character.erase(ids[i]);
			give_to_server(server, server->game->get_entity_from_eid(ids[i]), 0);
            if (!smart_cast<CActor*>(actor_object)->g_Alive()) continue; // retain lootable corpse
			Msg("[Lost Zone] removing Actor %u of a disconnected player", ids[i]);
			// An NPC still talking to this Actor would keep a dangling partner.
			CActor* leaving = smart_cast<CActor*>(actor_object);
			if (leaving && leaving->IsTalking())
			{
				if (CInventoryOwner* partner = leaving->GetTalkPartner())
					partner->StopTalk();
				leaving->StopTalk();
			}
			server_release_task_manager(ids[i]);
			actor_object->DestroyObject();
		}
	}
}

struct StoreMoney
{
	void operator()(IClient* client) const { store_money(static_cast<xrClientData*>(client)); }
};

void server_talk_prune(xrServer* server);

void server_update(xrServer* server)
{
	if (!enabled())
		return;
	// The runtime god mode (cutscenes) is cleared by showing the game UI; a
	// dedicated server has none, and the flag also stopped condition damage
	// (UpdateCondition, CanBeHarmed). Keep it off here.
	psActorFlags.set(AF_GODMODE_RT, FALSE);
	destroy_pending_actors(server);
	server_talk_prune(server);
	server_physics_update(server);
	characters_update(server);
	server_pda_update(server);
	server_marks_update(server);
	if (!s_accounts_loaded)
		return;
	StoreMoney store;
	server->ForEachClientDo(store);
	accounts_save();
}

// ---------------------------------------------------------------------------
// server: event validation
// ---------------------------------------------------------------------------
static bool living_npc(CSE_Abstract* entity)
{
	if (!entity || smart_cast<CSE_ALifeCreatureActor*>(entity))
		return false;
	CSE_ALifeCreatureAbstract* creature = smart_cast<CSE_ALifeCreatureAbstract*>(entity);
	return creature && creature->g_Alive();
}

static bool accessible_corpse(xrClientData* CL, CSE_Abstract* entity)
{
	if (!CL || !CL->owner || !entity) return false;
	CEntityAlive* body = smart_cast<CEntityAlive*>(Level().Objects.net_Find(entity->ID));
	CEntityAlive* actor = smart_cast<CEntityAlive*>(Level().Objects.net_Find(CL->owner->ID));
	CInventoryOwner* inventory = smart_cast<CInventoryOwner*>(body);
	return body && !body->g_Alive() && actor && actor->g_Alive() && inventory &&
		!inventory->deadbody_closed_status() && actor->Position().distance_to(body->Position()) <= 3.f;
}

bool server_remote_event_allowed(xrServer* server, xrClientData* CL, NET_Packet& P, u16 type, u16 destination)
{
	if (!enabled() || !CL || CL->flags.bLocal)
		return true;

	switch (type)
	{
	case GE_MONEY:
		return false; // money changes only on the server

	case GEG_PLAYER_ITEM_EAT:
	case GEG_PLAYER_ITEM2SLOT:
	case GEG_PLAYER_ITEM2BELT:
	case GEG_PLAYER_ITEM2RUCK:
	case GEG_PLAYER_ACTIVATEARTEFACT:
	case GEG_PLAYER_ACTIVATE_SLOT:
		{
			// Players use and arrange items only in their own inventory.
			CSE_Abstract* dest = server->game->get_entity_from_eid(destination);
			return dest && dest == CL->owner;
		}

	case GE_NETCOOP_RP:
		{
			// Only for the sender's own Actor.
			CSE_Abstract* dest = server->game->get_entity_from_eid(destination);
			return dest && dest == CL->owner;
		}

	case GE_NETCOOP_ITEM_STATE:
	case GE_NETCOOP_WPN_AIM:
		{
			// Only for an item the sender's own Actor holds.
			CSE_Abstract* weapon = server->game->get_entity_from_eid(destination);
			return weapon && CL->owner && weapon->ID_Parent == CL->owner->ID;
		}

	case GE_TRADE_BUY:
	case GE_TRADE_SELL:
	case GE_OWNERSHIP_TAKE:
	case GE_OWNERSHIP_REJECT:
		{
			CSE_Abstract* dest = server->game->get_entity_from_eid(destination);
			if (!dest)
				return true; // the normal handler reports it

			if (smart_cast<CSE_ALifeCreatureActor*>(dest) && dest != CL->owner && !accessible_corpse(CL, dest))
				return false; // another player's inventory
			if (living_npc(dest))
				return false; // living NPC inventories change through server trade

			if (P.r_elapsed() >= sizeof(u16))
			{
				const u32 pos = P.r_pos;
				const u16 item_id = P.r_u16();
				P.r_pos = pos;
				CSE_Abstract* item = server->game->get_entity_from_eid(item_id);
				CSE_Abstract* holder = item && item->ID_Parent != 0xffff
					? server->game->get_entity_from_eid(item->ID_Parent)
					: NULL;
				if (holder && holder != dest)
				{
					if (smart_cast<CSE_ALifeCreatureActor*>(holder) && holder != CL->owner && !accessible_corpse(CL, holder))
						return false;
					if (living_npc(holder))
						return false;
				}
			}
			return true;
		}
	default:
		return true;
	}
}

// ---------------------------------------------------------------------------
// server: trade
// ---------------------------------------------------------------------------
static void prepare_trade(u16 partner_id)
{
	if (!enabled() || !g_pGameLevel || !Level().Server) return;
	::luabind::functor<void> prepare;
	if (ai().script_engine().functor("netcoop_server_compat.prepare_trade", prepare))
	{
		try { prepare(partner_id); }
		catch (...) { Msg("! [Lost Zone] trader %u profile preparation failed", partner_id); }
	}
}

static void send_trade_result(xrServer* server, xrClientData* CL, bool ok, LPCSTR message)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_TRADE_RESULT);
	P.w_u8(ok ? 1 : 0);
	P.w_stringZ(message);
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
	if (!ok)
		Msg("! [Lost Zone] trade rejected for '%s': %s", CL->netcoop_login.c_str(), message);
}

void server_on_trade(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || !CL->owner || !g_pGameLevel)
		return;
	if (P.r_elapsed() < 2 + 1 + 2)
		return;

	const u16 partner_id = P.r_u16();
	const u8 direction = P.r_u8();
	const u16 count = P.r_u16();
	if (count == 0 || count > 256 || P.r_elapsed() != u32(count) * sizeof(u16) || direction > trade_actor_sells)
	{
		send_trade_result(server, CL, false, "Malformed trade request");
		return;
	}

	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	CObject* partner_object = Level().Objects.net_Find(partner_id);
	CInventoryOwner* partner = smart_cast<CInventoryOwner*>(partner_object);
	CEntityAlive* partner_alive = smart_cast<CEntityAlive*>(partner_object);
	if (!actor || !actor->g_Alive() || !partner || !partner_alive || !partner_alive->g_Alive() ||
		smart_cast<CActor*>(partner_object))
	{
		send_trade_result(server, CL, false, "Trader is not available");
		return;
	}
	if (actor->Position().distance_to(partner_object->Position()) > trade_max_distance)
	{
		send_trade_result(server, CL, false, "Trader is too far away");
		return;
	}

	// The partner's CTrade: bBuying == true means the partner buys (actor sells).
	ServerActorScope trade_actor_scope(actor);
	prepare_trade(partner_id);
	if (!partner->IsTradeEnabled())
	{
		send_trade_result(server, CL, false, "This character does not trade");
		return;
	}
	const bool partner_buys = direction == trade_actor_sells;
	CObject* seller = partner_buys ? static_cast<CObject*>(actor) : partner_object;

	xr_vector<PIItem> items;
	items.reserve(count);
	for (u16 i = 0; i < count; ++i)
	{
		const u16 id = P.r_u16();
		PIItem item = smart_cast<PIItem>(Level().Objects.net_Find(id));
		if (!item || item->object().H_Parent() != seller || item->object().getDestroy())
		{
			send_trade_result(server, CL, false, "Item is no longer available");
			return;
		}
		if (std::find(items.begin(), items.end(), item) != items.end())
			continue;
		items.push_back(item);
	}

	CTrade* trade = partner->GetTrade();
	if (!trade)
	{
		send_trade_result(server, CL, false, "Trader is not available");
		return;
	}
	trade->StartTradeEx(actor);
	if (!partner_buys)
	{
		u32 cells=storage_live_cells(server,CL->owner);
		for (auto item:items) cells+=storage_section_cost(item->object().cNameSect().c_str());
		if (cells>storage_capacity(false))
		{
			trade->StopTrade(); send_trade_result(server,CL,false,"No free inventory slots"); return;
		}
	}

	u32 total = 0;
	for (u32 i = 0; i < items.size(); ++i)
	{
		const u32 price = trade->GetItemPrice(items[i], partner_buys);
		if (price == 0)
		{
			trade->StopTrade();
			send_trade_result(server, CL, false, partner_buys ? "Trader does not buy this item"
			                                                  : "Trader does not sell this item");
			return;
		}
		total += price;
	}

	if (partner_buys)
	{
		if (!partner->InfinitiveMoney() && partner->get_money() < total)
		{
			trade->StopTrade();
			send_trade_result(server, CL, false, "Trader does not have enough money");
			return;
		}
	}
	else if (actor->get_money() < total)
	{
		trade->StopTrade();
		send_trade_result(server, CL, false, "Not enough money");
		return;
	}

	if (partner_buys)
		trade->OnPerformTrade(0, total);
	else
		trade->OnPerformTrade(total, 0);

	for (u32 i = 0; i < items.size(); ++i)
		trade->TransferItem(items[i], partner_buys);

	// TransferItem changes money locally; publish the server result to everyone.
	actor->set_money(actor->get_money(), true);
	partner->set_money(partner->get_money(), true);
	trade->StopTrade();

	string256 message;
	xr_sprintf(message, "%s %u item(s) for %u RU", partner_buys ? "sold" : "bought", (u32)items.size(), total);
	Msg("[Lost Zone] '%s' %s", CL->netcoop_login.c_str(), message);
	send_trade_result(server, CL, true, message);
}
} // namespace netcoop

// ---------------------------------------------------------------------------
// dialogue
// ---------------------------------------------------------------------------
namespace netcoop
{
enum ETalkOp : u8
{
	talk_start = 0,
	talk_choose = 1,
	talk_stop = 2,
};

enum ETalkFlags : u8
{
	talk_flag_open = 1,
	talk_flag_trade = 2,
};

static const u32 talk_max_text = 1024;
static const u32 talk_max_entries = 64;
static const float talk_max_distance = 5.f;
static xr_deque<TalkState> s_talk_states;

void client_talk_start(u16 npc_id)
{
	s_talk_states.clear();
	Msg("[Lost Zone] talk request to NPC %u", npc_id);
	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK);
	P.w_u8(talk_start);
	P.w_u16(npc_id);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_talk_choose(LPCSTR id)
{
	if (!id || !id[0] || xr_strlen(id) >= 256)
		return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK);
	P.w_u8(talk_choose);
	P.w_stringZ(id);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_talk_stop()
{
	if (!g_pGameLevel)
		return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK);
	P.w_u8(talk_stop);
	Level().Send(P, net_flags(TRUE, TRUE));
}

void client_on_talk_state(NET_Packet& P)
{
	if (P.r_elapsed() < 2 + 1 + 2)
		return;
	TalkState state;
	state.npc = P.r_u16();
	const u8 flags = P.r_u8();
	state.open = !!(flags & talk_flag_open);
	state.trade = !!(flags & talk_flag_trade);
	Msg("[Lost Zone] talk state from server: NPC %u open=%d trade=%d", state.npc, state.open ? 1 : 0, state.trade ? 1 : 0);

	string1024 text;
	string256 id;
	const u16 lines = P.r_u16();
	for (u16 i = 0; i < lines && i < talk_max_entries; ++i)
	{
		if (P.r_elapsed() < 1)
			return;
		TalkLine line;
		line.npc = !!P.r_u8();
		if (!read_string(P, text, sizeof(text)))
			return;
		line.text = text;
		state.lines.push_back(line);
	}
	if (P.r_elapsed() < 2)
		return;
	const u16 choices = P.r_u16();
	for (u16 i = 0; i < choices && i < talk_max_entries; ++i)
	{
		TalkChoice choice;
		if (!read_string(P, id, sizeof(id)) || !read_string(P, text, sizeof(text)) || P.r_elapsed() < 1)
			return;
		choice.id = id;
		choice.text = text;
		choice.finalizer = !!P.r_u8();
		state.choices.push_back(choice);
	}
	s_talk_states.push_back(state);
}

bool client_take_talk_state(TalkState& out)
{
	if (s_talk_states.empty())
		return false;
	out = s_talk_states.front();
	s_talk_states.pop_front();
	return true;
}

struct TalkSession
{
	u16 npc;
	DIALOG_SHARED_PTR current;
};

typedef xr_map<u32, TalkSession> TalkSessions;
static TalkSessions s_talk_sessions;
static TalkState* s_talk_capture = NULL;

static void capture_line(bool npc, LPCSTR text)
{
	if (!s_talk_capture || !text || !text[0] || s_talk_capture->lines.size() >= talk_max_entries)
		return;
	TalkLine line;
	line.npc = npc;
	line.text = text;
	s_talk_capture->lines.push_back(line);
}

bool talk_capture_answer(LPCSTR text)
{
	if (!s_talk_capture)
		return false;
	capture_line(true, text);
	return true;
}

// ---------------------------------------------------------------------------
// server: per-player tasks
// ---------------------------------------------------------------------------
// The engine keeps one task list per level. A netcoop server keeps one per
// player Actor (stored in the ALife registry under that Actor's id) and makes
// it the level's list while that player is served.
typedef xr_map<u16, CGameTaskManager*> TaskManagers;
static TaskManagers s_task_managers;

static CGameTaskManager* server_task_manager(u16 actor_id)
{
	TaskManagers::iterator it = s_task_managers.find(actor_id);
	if (it != s_task_managers.end())
		return it->second;
	CGameTaskManager* manager = xr_new<CGameTaskManager>(actor_id);
	s_task_managers.insert(std::make_pair(actor_id, manager));
	return manager;
}

static void clear_tasks(CGameTaskManager* manager)
{
	vGameTasks& tasks = manager->GetGameTasks();
	for (u32 i = 0; i < tasks.size(); ++i)
	{
		if (tasks[i].game_task)
			tasks[i].game_task->RemoveMapLocations(false);
		tasks[i].destroy();
	}
	tasks.clear();
	manager->MarkChanged();
}

static void server_release_task_manager(u16 actor_id)
{
	TaskManagers::iterator it = s_task_managers.find(actor_id);
	if (it == s_task_managers.end())
		return;
	CGameTaskManager* manager = it->second;
	s_task_managers.erase(it);
	if (g_pGameLevel && Level().GameTaskManagerPtr() == manager)
		Level().SetGameTaskManager(NULL);
	clear_tasks(manager);
	xr_delete(manager);
}

// True when a player other than actor_id has this task in progress.
bool server_task_taken_by_other(u16 actor_id, LPCSTR task_id)
{
	if (!task_id || !task_id[0])
		return false;
	const shared_str id = task_id;
	for (TaskManagers::iterator it = s_task_managers.begin(); it != s_task_managers.end(); ++it)
		if (it->first != actor_id && it->second->HasGameTask(id, true))
			return true;
	return false;
}

// Server scripts use db.actor and the engine uses Actor() and the level task
// list; while one player is served all three refer to that player.
static bool s_actor_bound = false;
static CActor* s_bound_previous_actor = NULL;
static CGameTaskManager* s_bound_previous_tasks = NULL;

static void bind_engine_actor(CActor* actor)
{
	if (!g_pGameLevel || !Level().Server)
		return;
	if (actor)
	{
		if (!s_actor_bound)
		{
			s_actor_bound = true;
			s_bound_previous_actor = g_actor;
			s_bound_previous_tasks = Level().GameTaskManagerPtr();
		}
		g_actor = actor;
		Level().SetGameTaskManager(server_task_manager(actor->ID()));
	}
	else if (s_actor_bound)
	{
		s_actor_bound = false;
		g_actor = s_bound_previous_actor;
		Level().SetGameTaskManager(s_bound_previous_tasks);
		s_bound_previous_actor = NULL;
		s_bound_previous_tasks = NULL;
	}
}

// GAMMA dialogue scripts use db.actor; point it at the player being served.
static CActor* s_bound_actor = NULL;

static void bind_script_actor(CActor* actor)
{
	s_bound_actor = actor;
	bind_engine_actor(actor);
	// Called for every server-side object script update; resolve the Lua function once.
	static ::luabind::functor<void> f;
	static bool resolved = false;
	if (!resolved)
		resolved = ai().script_engine().functor("netcoop_server_compat.bind_actor", f);
	if (!resolved)
		return;
	try
	{
		if (actor)
			f(actor->lua_game_object());
		else
			f();
	}
	catch (...)
	{
		Msg("! [Lost Zone] netcoop_server_compat.bind_actor failed");
	}
}

static void talk_say(TalkSession& session, CPhraseDialogManager* our, const shared_str& phrase_id)
{
	capture_line(false, session.current->GetPhraseText(phrase_id));
	our->SayPhrase(session.current, phrase_id);
	if (session.current && session.current->IsFinished())
		session.current = DIALOG_SHARED_PTR((CPhraseDialog*)NULL);
}

// Mirrors CUITalkWnd::UpdateQuestions for a server-side dialogue run.
static void talk_build_choices(TalkSession& session, CPhraseDialogManager* our, CPhraseDialogManager* other,
                               TalkState& state)
{
	for (u32 guard = 0; guard < 16; ++guard)
	{
		state.choices.clear();
		if (!session.current)
		{
			our->UpdateAvailableDialogs(other);
			const CPhraseDialogManager::DIALOG_VECTOR& dialogs = our->AvailableDialogs();
			for (u32 i = 0; i < dialogs.size() && state.choices.size() < talk_max_entries; ++i)
			{
				TalkChoice choice;
				choice.id = dialogs[i]->GetDialogID();
				choice.text = dialogs[i]->DialogCaption();
				choice.finalizer = dialogs[i]->GetPhrase("0")->IsFinalizer();
				state.choices.push_back(choice);
			}
			return;
		}

		if (!session.current->IsWeSpeaking(our))
			return;

		const PHRASE_VECTOR& phrases = session.current->PhraseList();
		if (!phrases.empty() && session.current->allIsDummy())
		{
			// Only placeholder phrases: say one and continue, as the UI does.
			CPhrase* phrase = phrases[Random.randI(phrases.size())];
			talk_say(session, our, phrase->GetID());
			continue;
		}

		for (u32 i = 0; i < phrases.size() && state.choices.size() < talk_max_entries; ++i)
		{
			TalkChoice choice;
			choice.id = phrases[i]->GetID();
			choice.text = session.current->GetPhraseText(choice.id);
			choice.finalizer = phrases[i]->IsFinalizer();
			state.choices.push_back(choice);
		}
		return;
	}
}

static void send_talk_state(xrServer* server, xrClientData* CL, const TalkState& state)
{
	// Keep the packet well inside the transport size limit.
	u32 budget = 12000;
	xr_vector<const TalkLine*> lines;
	for (u32 i = 0; i < state.lines.size(); ++i)
	{
		const u32 size = state.lines[i].text.size() + 8;
		if (state.lines[i].text.size() < talk_max_text && budget > size)
		{
			budget -= size;
			lines.push_back(&state.lines[i]);
		}
	}
	xr_vector<const TalkChoice*> choices;
	for (u32 i = 0; i < state.choices.size(); ++i)
	{
		const TalkChoice& c = state.choices[i];
		const u32 size = c.id.size() + c.text.size() + 8;
		if (c.id.size() < 256 && c.text.size() < talk_max_text && budget > size)
		{
			budget -= size;
			choices.push_back(&c);
		}
	}

	NET_Packet P;
	P.w_begin(M_NETCOOP_TALK_STATE);
	P.w_u16(state.npc);
	P.w_u8(u8((state.open ? talk_flag_open : 0) | (state.trade ? talk_flag_trade : 0)));
	P.w_u16((u16)lines.size());
	for (u32 i = 0; i < lines.size(); ++i)
	{
		P.w_u8(lines[i]->npc ? 1 : 0);
		P.w_stringZ(lines[i]->text.c_str());
	}
	P.w_u16((u16)choices.size());
	for (u32 i = 0; i < choices.size(); ++i)
	{
		P.w_stringZ(choices[i]->id.c_str());
		P.w_stringZ(choices[i]->text.c_str());
		P.w_u8(choices[i]->finalizer ? 1 : 0);
	}
	server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
}

static void talk_close(xrClientData* CL, CActor* actor, CInventoryOwner* npc)
{
	s_talk_sessions.erase(CL->ID.value());
	if (actor && actor->IsTalking())
		actor->StopTalk();
	if (npc && npc->IsTalking())
		npc->StopTalk();
}

void server_on_talk(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!enabled() || !CL || !CL->owner || !g_pGameLevel || P.r_elapsed() < 1)
		return;

	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	if (!actor)
		return;

	const u8 op = P.r_u8();
	TalkSessions::iterator found = s_talk_sessions.find(CL->ID.value());

	u16 npc_id = found != s_talk_sessions.end() ? found->second.npc : u16(0xffff);
	if (op == talk_start)
	{
		if (P.r_elapsed() < 2)
			return;
		npc_id = P.r_u16();
	}

	CObject* npc_object = npc_id != 0xffff ? Level().Objects.net_Find(npc_id) : NULL;
	CInventoryOwner* npc = smart_cast<CInventoryOwner*>(npc_object);
	CEntityAlive* npc_alive = smart_cast<CEntityAlive*>(npc_object);
	CPhraseDialogManager* our = smart_cast<CPhraseDialogManager*>(actor);
	CPhraseDialogManager* other = smart_cast<CPhraseDialogManager*>(npc_object);

	if (op == talk_stop)
	{
		talk_close(CL, actor, npc);
		return;
	}

	TalkState state;
	state.npc = npc_id;
	state.open = false;
	state.trade = false;

	const bool valid = npc && npc_alive && npc_alive->g_Alive() && actor->g_Alive() && our && other &&
		!smart_cast<CActor*>(npc_object) &&
		actor->Position().distance_to(npc_object->Position()) <= talk_max_distance;
	if (!valid || (op == talk_choose && found == s_talk_sessions.end()) || op > talk_stop)
	{
		Msg("! [Lost Zone] talk op %u with %u from '%s' rejected: npc=%d alive=%d distance=%.1f session=%d",
			op, npc_id, CL->netcoop_login.c_str(), npc ? 1 : 0, npc_alive && npc_alive->g_Alive() ? 1 : 0,
			npc_object ? actor->Position().distance_to(npc_object->Position()) : -1.f,
			found != s_talk_sessions.end() ? 1 : 0);
		talk_close(CL, actor, npc);
		send_talk_state(server, CL, state);
		return;
	}

	s_talk_capture = &state;
	bind_script_actor(actor);

	if (op == talk_start)
	{
		if (actor->IsTalking())
			actor->StopTalk();
		prepare_trade(npc_id);
		s_talk_sessions.erase(CL->ID.value());

		const bool offered = npc->OfferTalk(actor);
		Msg("[Lost Zone] talk '%s' -> %s: offer=%d talk_enabled=%d", CL->netcoop_login.c_str(),
			npc_object->cName().c_str(), offered ? 1 : 0, npc->IsTalkEnabled() ? 1 : 0);
		if (offered)
		{
			actor->StartTalk(npc);

			TalkSession& session = s_talk_sessions[CL->ID.value()];
			session.npc = npc_id;
			session.current = DIALOG_SHARED_PTR((CPhraseDialog*)NULL);

			// Mirrors CUITalkWnd::InitOthersStartDialog.
			other->UpdateAvailableDialogs(our);
			if (!other->AvailableDialogs().empty())
			{
				session.current = other->AvailableDialogs().front();
				other->InitDialog(our, session.current);
				capture_line(true, session.current->GetPhraseText("0"));
				other->SayPhrase(session.current, "0");
				if (!session.current || session.current->IsFinished())
					session.current = DIALOG_SHARED_PTR((CPhraseDialog*)NULL);
			}
			talk_build_choices(session, our, other, state);
		}
	}
	else
	{
		char id[256];
		TalkSession& session = found->second;
		bool accepted = false;
		if (read_string(P, id, sizeof(id)))
		{
			if (!session.current)
			{
				if (our->HaveAvailableDialog(id))
				{
					session.current = our->GetDialogByID(id);
					our->InitDialog(other, session.current);
					talk_say(session, our, "0");
					accepted = true;
				}
			}
			else if (session.current->IsWeSpeaking(our))
			{
				const shared_str wanted = id;
				const PHRASE_VECTOR& phrases = session.current->PhraseList();
				for (u32 i = 0; i < phrases.size(); ++i)
				{
					if (phrases[i]->GetID() == wanted)
					{
						const shared_str phrase_id = phrases[i]->GetID();
						talk_say(session, our, phrase_id);
						accepted = true;
						break;
					}
				}
			}
		}
		if (!accepted)
			Msg("! [Lost Zone] rejected dialogue choice from '%s'", CL->netcoop_login.c_str());
		talk_build_choices(session, our, other, state);
	}

	bind_script_actor(NULL);
	s_talk_capture = NULL;

	// A dialogue script may have ended the conversation (break_dialog).
	state.open = actor->IsTalking() && npc->IsTalking();
	state.trade = actor->IsTradeEnabled() && npc->IsTradeEnabled();
	if (!state.open)
		talk_close(CL, actor, npc);
	send_talk_state(server, CL, state);
}

// Drops sessions of connections that no longer exist (main thread).
void server_talk_prune(xrServer* server)
{
	for (TalkSessions::iterator it = s_talk_sessions.begin(); it != s_talk_sessions.end();)
	{
		ClientID id;
		id.set(it->first);
		if (!server->ID_to_client(id))
			it = s_talk_sessions.erase(it);
		else
			++it;
	}
}
} // namespace netcoop

namespace netcoop
{
bool client_owns_hud_item(const CObject* item)
{
	if (!item || !pure_client())
		return false;
	const CObject* parent = item->H_Parent();
	return parent && parent == Level().CurrentControlEntity();
}
} // namespace netcoop

namespace netcoop
{
static int s_nearest_bind_depth = 0;

bool server_bind_nearest_actor(CObject* npc)
{
	if (s_nearest_bind_depth > 0)
	{
		++s_nearest_bind_depth;
		return true;
	}
	if (!npc || !g_pGameLevel)
		return false;
	const u16 id = netcoop_nearest_player_actor(npc->Position());
	CActor* actor = id != 0xffff ? smart_cast<CActor*>(Level().Objects.net_Find(id)) : NULL;
	if (!actor || actor->getDestroy())
		return false;
	bind_script_actor(actor);
	s_nearest_bind_depth = 1;
	return true;
}

void server_unbind_actor()
{
	if (s_nearest_bind_depth <= 0)
		return;
	if (--s_nearest_bind_depth == 0)
		bind_script_actor(NULL);
}

ServerActorScope::ServerActorScope(CObject* object) : bound(false)
{
	if (enabled() && g_pGameLevel && Level().Server && object && !smart_cast<CActor*>(object))
		bound = server_bind_nearest_actor(object);
}

ServerActorScope::~ServerActorScope()
{
	if (bound)
		server_unbind_actor();
}

ServerVictimScope::ServerVictimScope(CActor* victim) : active(false), previous(NULL)
{
	if (!server_player_copy(victim))
		return;
	active = true;
	previous = s_bound_actor;
	bind_script_actor(victim);
}

ServerVictimScope::~ServerVictimScope()
{
	if (active)
		bind_script_actor(previous);
}

static void character_capture_progress(Character& character, CActor* actor)
{
	ServerVictimScope scope(actor);
	CMemoryWriter writer;
	vGameTasks& tasks = server_task_manager(actor->ID())->GetGameTasks();
	writer.w_u32(u32(tasks.size()));
	for (SGameTaskKey& task : tasks) task.save(writer);
	save_data(actor->m_known_info_registry->registry().objects(), writer);
	::luabind::functor<luabind::internal_string> capture;
	if (!ai().script_engine().functor("netcoop_server_compat.capture_character_state", capture)) return;
	luabind::internal_string state;
	try { state = capture(actor->lua_game_object()); }
	catch (...) { Msg("! [Lost Zone] cannot serialize character script state for %u", actor->ID()); return; }
	writer.w_u32(u32(state.size()));
	if (!state.empty()) writer.w(state.data(), state.size());
	if (writer.size() > 1048576) { Msg("! [Lost Zone] character progress exceeds save limit for %u", actor->ID()); return; }
	const u8* data = static_cast<const u8*>(writer.pointer());
	character.progress.assign(data, data + writer.size());
}

static void character_restore_progress(Character& character, CActor* actor)
{
	if (character.progress.empty()) return;
	ServerVictimScope scope(actor);
	IReader reader(character.progress.data(), character.progress.size());
	const u32 count = reader.r_u32();
	if (count > 512) return;
	CGameTaskManager* manager = server_task_manager(actor->ID());
	clear_tasks(manager);
	vGameTasks& tasks = manager->GetGameTasks();
	for (u32 i = 0; i < count; ++i) { SGameTaskKey task; task.load(reader); tasks.push_back(task); }
	load_data(actor->m_known_info_registry->registry().objects(), reader);
	const u32 size = reader.r_u32();
	if (size > reader.elapsed()) return;
	luabind::internal_string state(reinterpret_cast<const char*>(reader.pointer()), size);
	::luabind::functor<void> restore;
	if (ai().script_engine().functor("netcoop_server_compat.restore_character_state", restore))
		try { restore(actor->lua_game_object(), state); }
		catch (...) { Msg("! [Lost Zone] cannot restore character script state for %u", actor->ID()); }
	manager->MarkChanged();
}
// ---------------------------------------------------------------------------
// task list replication
// ---------------------------------------------------------------------------
static const u32 tasks_update_interval = 500; // ms
static const u32 tasks_packet_budget = 12000;
static xr_map<u32, u32> s_sent_tasks_crc; // client id -> crc of the last list sent

struct TaskPlayer
{
	ClientID client;
	u16 actor;
};

struct CollectTaskPlayers
{
	xr_vector<TaskPlayer>* players;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (!CL || CL->flags.bLocal || CL->netcoop_role == role_none || !CL->owner)
			return;
		if (!smart_cast<CSE_ALifeCreatureActor*>(CL->owner))
			return;
		TaskPlayer p;
		p.client = CL->ID;
		p.actor = CL->owner->ID;
		players->push_back(p);
	}
};

static void write_tasks(CGameTaskManager* manager, NET_Packet& P)
{
	P.w_begin(M_NETCOOP_TASKS);
	const u32 count_pos = P.w_tell();
	P.w_u16(0);
	u16 count = 0;
	vGameTasks& tasks = manager->GetGameTasks();
	// Tasks in progress first, then finished ones while they fit.
	for (int pass = 0; pass < 2; ++pass)
	{
		for (u32 i = 0; i < tasks.size(); ++i)
		{
			CGameTask* t = tasks[i].game_task;
			if (!t || (t->GetTaskState() == eTaskStateInProgress) != (pass == 0))
				continue;
			CMemoryWriter w;
			t->save_task(w);
			const u32 size = tasks[i].task_id.size() + 1 + 2 + w.size();
			if (w.size() > 0xffff || P.w_tell() + size > tasks_packet_budget)
				continue;
			P.w_stringZ(tasks[i].task_id.c_str());
			P.w_u16(u16(w.size()));
			P.w(w.pointer(), w.size());
			++count;
		}
	}
	P.w_seek(count_pos, &count, sizeof(count));
}

void server_tasks_update(xrServer* server)
{
	if (!enabled() || !g_pGameLevel || !Level().Server)
		return;
	static u32 next_update = 0;
	const u32 now = Device.dwTimeGlobal;
	if (now < next_update)
		return;
	next_update = now + tasks_update_interval;

	// Managers of Actors that no longer exist (death, disconnect).
	xr_vector<u16> gone;
	for (TaskManagers::iterator it = s_task_managers.begin(); it != s_task_managers.end(); ++it)
		if (!smart_cast<CActor*>(Level().Objects.net_Find(it->first)))
			gone.push_back(it->first);
	for (u32 i = 0; i < gone.size(); ++i)
		server_release_task_manager(gone[i]);

	xr_vector<TaskPlayer> players;
	CollectTaskPlayers collect;
	collect.players = &players;
	server->ForEachClientDo(collect);

	static ::luabind::functor<void> lua_update;
	static bool lua_resolved = false;
	if (!lua_resolved)
		lua_resolved = ai().script_engine().functor("netcoop_server_compat.update_player_tasks", lua_update);

	for (u32 i = 0; i < players.size(); ++i)
	{
		CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(players[i].actor));
		if (!actor || actor->getDestroy())
			continue;

		bind_script_actor(actor);
		CGameTaskManager* manager = Level().GameTaskManagerPtr();
		if (manager)
		{
			manager->UpdateTasks();
			if (lua_resolved)
			{
				try
				{
					lua_update();
				}
				catch (...)
				{
					Msg("! [Lost Zone] task update script failed for Actor %u", players[i].actor);
				}
			}
		}
		manager = Level().GameTaskManagerPtr();
		NET_Packet P;
		if (manager)
			write_tasks(manager, P);
		bind_script_actor(NULL);
		if (!manager)
			continue;

		const u32 crc = crc32(P.B.data, P.B.count);
		u32& sent = s_sent_tasks_crc[players[i].client.value()];
		if (sent == crc)
			continue;
		sent = crc;
		server->SendTo(players[i].client, P, net_flags(TRUE, TRUE));
	}
}

// ---------------------------------------------------------------------------
// client: task list from the server
// ---------------------------------------------------------------------------
static void notify_task(LPCSTR id, LPCSTR kind)
{
	::luabind::functor<void> f;
	if (!ai().script_engine().functor("netcoop_client_compat.on_task", f))
		return;
	try
	{
		f(id, kind);
	}
	catch (...)
	{
	}
}

void client_on_tasks(NET_Packet& P)
{
	if (!pure_client() || !Level().GameTaskManagerPtr())
		return;
	CGameTaskManager& manager = Level().GameTaskManager();

	xr_map<shared_str, ETaskState> previous;
	{
		vGameTasks& tasks = manager.GetGameTasks();
		for (u32 i = 0; i < tasks.size(); ++i)
			if (tasks[i].game_task)
				previous[tasks[i].task_id] = tasks[i].game_task->GetTaskState();
	}
	clear_tasks(&manager);

	if (P.r_elapsed() < sizeof(u16))
		return;
	const u16 count = P.r_u16();
	xr_vector<std::pair<shared_str, LPCSTR>> news;
	for (u16 i = 0; i < count; ++i)
	{
		string256 id;
		if (!read_string(P, id, sizeof(id)) || P.r_elapsed() < sizeof(u16))
			break;
		const u16 size = P.r_u16();
		if (P.r_elapsed() < size)
			break;
		IReader reader(P.B.data + P.r_tell(), size);
		P.r_advance(size);

		CGameTask* t = xr_new<CGameTask>();
		t->m_ID = id;
		t->load_task_remote(reader);
		vGameTasks& tasks = manager.GetGameTasks();
		tasks.push_back(SGameTaskKey(t->m_ID));
		tasks.back().game_task = t;

		xr_map<shared_str, ETaskState>::iterator old = previous.find(t->m_ID);
		const ETaskState state = t->GetTaskState();
		const bool was_active = old != previous.end() && old->second == eTaskStateInProgress;
		if (state == eTaskStateInProgress && !was_active)
			news.push_back(std::make_pair(t->m_ID, "new"));
		else if (was_active && state == eTaskStateCompleted)
			news.push_back(std::make_pair(t->m_ID, "complete"));
		else if (was_active && state == eTaskStateFail)
			news.push_back(std::make_pair(t->m_ID, "fail"));
	}

	if (!manager.ActiveTask())
	{
		CGameTask* first = manager.IterateGet(NULL, eTaskStateInProgress, true);
		if (first)
			manager.SetActiveTask(first);
	}
	manager.MarkChanged();
	if (CurrentGameUI())
		CurrentGameUI()->UpdatePda();

	for (u32 i = 0; i < news.size(); ++i)
		notify_task(news[i].first.c_str(), news[i].second);
}
// ---------------------------------------------------------------------------
// PDA news
// ---------------------------------------------------------------------------
struct FindActorOwner
{
	u16 actor_id;
	bool operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		return CL && !CL->flags.bLocal && CL->owner && CL->owner->ID == actor_id;
	}
};

void server_forward_news(u16 actor_id, const GAME_NEWS_DATA& news)
{
	if (!enabled() || !g_pGameLevel || !Level().Server)
		return;
	FindActorOwner find;
	find.actor_id = actor_id;
	xrClientData* CL = static_cast<xrClientData*>(Level().Server->FindClient(find));
	if (!CL)
		return;
	const u32 limit = 4000;
	if (news.news_caption.size() > limit || news.news_text.size() > limit || news.texture_name.size() > 256)
		return;
	NET_Packet P;
	P.w_begin(M_NETCOOP_NEWS);
	P.w_u8(u8(news.m_type));
	P.w_stringZ(news.news_caption.size() ? news.news_caption.c_str() : "");
	P.w_stringZ(news.news_text.size() ? news.news_text.c_str() : "");
	P.w_stringZ(news.texture_name.size() ? news.texture_name.c_str() : "");
	P.w_s32(news.show_time);
	Level().Server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
}

void client_on_news(NET_Packet& P)
{
	if (!pure_client() || P.r_elapsed() < 1)
		return;
	CActor* actor = smart_cast<CActor*>(Level().CurrentControlEntity());
	if (!actor)
		return;
	GAME_NEWS_DATA news;
	news.m_type = P.r_u8() == GAME_NEWS_DATA::eTalk ? GAME_NEWS_DATA::eTalk : GAME_NEWS_DATA::eNews;
	string4096 caption, text;
	string256 texture;
	if (!read_string(P, caption, sizeof(caption)) || !read_string(P, text, sizeof(text)) ||
		!read_string(P, texture, sizeof(texture)) || P.r_elapsed() < sizeof(s32))
		return;
	news.news_caption = caption;
	news.news_text = text;
	news.texture_name = texture;
	news.show_time = P.r_s32();
	clamp(news.show_time, 0, 60000);
	actor->AddGameNews(news);
}

// ---------------------------------------------------------------------------
// server Lua -> client Lua messages
// ---------------------------------------------------------------------------
struct CollectLoggedIn
{
	xr_vector<ClientID>* ids;
	void operator()(IClient* client) const
	{
		xrClientData* CL = static_cast<xrClientData*>(client);
		if (CL && !CL->flags.bLocal && CL->netcoop_role != role_none)
			ids->push_back(CL->ID);
	}
};

void script_broadcast(LPCSTR channel, LPCSTR data)
{
	if (!enabled() || !g_pGameLevel || !Level().Server || !channel || !channel[0])
		return;
	if (!data)
		data = "";
	if (xr_strlen(channel) >= 64 || xr_strlen(data) >= 8000)
	{
		Msg("! [Lost Zone] script message '%s' is too large", channel);
		return;
	}
	xr_vector<ClientID> ids;
	CollectLoggedIn collect;
	collect.ids = &ids;
	Level().Server->ForEachClientDo(collect);
	for (u32 i = 0; i < ids.size(); ++i)
	{
		NET_Packet P;
		P.w_begin(M_NETCOOP_SCRIPT);
		P.w_stringZ(channel);
		P.w_stringZ(data);
		Level().Server->SendTo(ids[i], P, net_flags(TRUE, TRUE));
	}
}

void client_on_script(NET_Packet& P)
{
	if (!pure_client())
		return;
	string64 channel;
	static char data[8192];
	if (!read_string(P, channel, sizeof(channel)) || !read_string(P, data, sizeof(data)))
		return;
	::luabind::functor<void> f;
	if (!ai().script_engine().functor("netcoop_client_compat.on_script_message", f))
		return;
	try
	{
		f((LPCSTR)channel, (LPCSTR)data);
	}
	catch (...)
	{
	}
}

bool script_send_to_actor(u16 actor_id, LPCSTR channel, LPCSTR data)
{
	if (!enabled() || !g_pGameLevel || !Level().Server || !channel || !channel[0])
		return false;
	if (!data)
		data = "";
	if (xr_strlen(channel) >= 64 || xr_strlen(data) >= 8000)
		return false;
	FindActorOwner find;
	find.actor_id = actor_id;
	xrClientData* CL = static_cast<xrClientData*>(Level().Server->FindClient(find));
	if (!CL)
		return false;
	NET_Packet P;
	P.w_begin(M_NETCOOP_SCRIPT);
	P.w_stringZ(channel);
	P.w_stringZ(data);
	Level().Server->SendTo(CL->ID, P, net_flags(TRUE, TRUE));
	return true;
}

bool server_open_ui(u16 actor_id, LPCSTR kind, u16 partner_id)
{
	prepare_trade(partner_id);
	string128 data;
	xr_sprintf(data, "%s %u", kind, partner_id);
	const bool sent = script_send_to_actor(actor_id, "open_ui", data);
	if (enabled() && g_pGameLevel && Level().Server)
		Msg("[Lost Zone] open %s with %u for Actor %u: %s", kind, partner_id, actor_id, sent ? "sent" : "no remote owner");
	return sent;
}

// Script hang watchdog. A mod script that never returns freezes the whole
// process (window, input, network). A watcher thread notices a frame that
// takes over 20 s and arms a Lua count hook: the hook logs the Lua stack of
// the running script and, after 60 s, aborts that script call with an error.
// No hook is installed while frames advance, so normal play costs nothing.
namespace
{
volatile LONG wd_armed = 0;
volatile u32 wd_frame = 0;
volatile u32 wd_since = 0;
volatile bool wd_logged = false;

void wd_disarm(lua_State* L)
{
	lua_sethook(L, 0, 0, 0);
	InterlockedExchange(&wd_armed, 0);
}

void wd_hook(lua_State* L, lua_Debug*)
{
	if (Device.dwFrame != wd_frame)
	{
		wd_disarm(L);
		return;
	}
	const u32 stuck = GetTickCount() - wd_since;
	if (!wd_logged)
	{
		wd_logged = true;
		Msg("! [Lost Zone] script hang: frame %u has run for %u s, Lua stack:", wd_frame, stuck / 1000);
		lua_Debug ar;
		for (int level = 0; level < 24 && lua_getstack(L, level, &ar); ++level)
		{
			if (!lua_getinfo(L, "nSl", &ar))
				break;
			Msg("! [Lost Zone]   %2d: %s:%d %s", level, ar.short_src, ar.currentline, ar.name ? ar.name : "?");
		}
		FlushLog();
	}
	if (stuck > 60000)
	{
		wd_disarm(L);
		wd_frame = 0; // re-arm if the script catches the error and goes on
		Msg("! [Lost Zone] script hang: aborting the script call");
		FlushLog();
		luaL_error(L, "netcoop: script hung for %u s", stuck / 1000);
	}
}

// Hitch sampling: a frame over 100 ms gets the main thread's native stack
// logged (at most once a second), so stutter can be attributed to a system
// or a script callback. The thread is suspended only while its stack is
// unwound, without allocations or locks.
HANDLE wd_main_thread = 0;

u32 sample_main_stack(DWORD64* pcs, u32 max_pcs)
{
	if (!wd_main_thread || SuspendThread(wd_main_thread) == DWORD(-1))
		return 0;
	u32 count = 0;
	CONTEXT ctx;
	ZeroMemory(&ctx, sizeof(ctx));
	ctx.ContextFlags = CONTEXT_FULL;
	if (GetThreadContext(wd_main_thread, &ctx))
	{
		while (count < max_pcs && ctx.Rip)
		{
			pcs[count++] = ctx.Rip;
			DWORD64 image_base = 0;
			PRUNTIME_FUNCTION fn = RtlLookupFunctionEntry(ctx.Rip, &image_base, 0);
			if (!fn)
				break; // generated code (LuaJIT traces) has no unwind data
			void* handler_data = 0;
			DWORD64 establisher = 0;
			RtlVirtualUnwind(UNW_FLAG_NHANDLER, image_base, ctx.Rip, fn, &ctx, &handler_data, &establisher, 0);
		}
	}
	ResumeThread(wd_main_thread);
	return count;
}

// Frames are written as module+offset (the game exe as a plain address at
// its fixed base); scratchpad symhitch.py resolves them with the PDB. No
// dbghelp in the process: its state is the crash handler's.
void log_hitch(u32 frame, u32 ms, const DWORD64* pcs, u32 count)
{
	string4096 line;
	xr_sprintf(line, "[Lost Zone][hitch] frame %u at %u ms:", frame, ms);
	const HMODULE exe = GetModuleHandle(0);
	for (u32 i = 0; i < count; ++i)
	{
		string128 part;
		HMODULE module = 0;
		GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
		                   (LPCSTR)pcs[i], &module);
		if (!module || module == exe)
			xr_sprintf(part, " < %llx", pcs[i]);
		else
		{
			string_path path;
			GetModuleFileNameA(module, path, sizeof(path));
			LPCSTR name = strrchr(path, '\\');
			xr_sprintf(part, " < %s+%llx", name ? name + 1 : path, pcs[i] - DWORD64(module));
		}
		xr_strcat(line, part);
	}
	Msg("%s", line);
}

DWORD WINAPI wd_thread(void*)
{
	u32 last_frame = Device.dwFrame;
	u32 since = GetTickCount();
	u32 sampled_frame = 0;
	u32 next_sample = 0;
	for (;;)
	{
		Sleep(10);
		const u32 frame = Device.dwFrame;
		const u32 now = GetTickCount();
		if (frame != last_frame)
		{
			last_frame = frame;
			since = now;
			continue;
		}
		if (g_netcoop_metrics && g_pGameLevel && now - since >= 100 && sampled_frame != frame && now >= next_sample)
		{
			sampled_frame = frame;
			next_sample = now + 1000;
			DWORD64 pcs[24];
			const u32 count = sample_main_stack(pcs, 24);
			if (count && Device.dwFrame == frame)
				log_hitch(frame, now - since, pcs, count);
		}
		if (now - since < 20000 || wd_armed || !g_pGameLevel || wd_frame == frame)
			continue;
		wd_frame = frame;
		wd_since = since;
		wd_logged = false;
		InterlockedExchange(&wd_armed, 1);
		Msg("! [Lost Zone] frame %u stuck for %u s, watching scripts", frame, (now - since) / 1000);
		lua_sethook(ai().script_engine().lua(), wd_hook, LUA_MASKCOUNT, 10000);
	}
}
} // namespace

void script_watchdog_start()
{
	static bool started = false;
	if (started || !enabled())
		return;
	started = true;
	DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &wd_main_thread,
	                THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, 0);
	HANDLE h = CreateThread(0, 0, wd_thread, 0, 0, 0);
	if (h)
		CloseHandle(h);
}

} // namespace netcoop

// ---------------------------------------------------------------------------
// Network smoothness and metrics (doc 38, stages 0 and 1)
// ---------------------------------------------------------------------------
#include "Weapon.h"
#include "ai/stalker/ai_stalker.h"
#include "memory_manager.h"
#include "enemy_manager.h"
#include "visual_memory_manager.h"

int g_netcoop_smooth = 1;
int g_netcoop_interp_ms = 100;
int g_netcoop_metrics = 1;
int g_netcoop_player_predict = 0;

namespace netcoop
{
void client_on_physics(NET_Packet& P)
{
	if (!pure_client() || P.r_elapsed() < 8) return;
	const u16 id = P.r_u16();
	CPhysicsShellHolder* holder = smart_cast<CPhysicsShellHolder*>(Level().Objects.net_Find(id));
	if (holder) holder->netcoop_physics_import(P);
}

void server_physics_update(xrServer* server)
{
	if (!g_pGameLevel || pure_client()) return;
	static u32 previous = 0;
	static u32 tick = 0;
	const u32 now = real_time_ms();
	if (previous && now - previous < 50) return;
	previous = now;
	++tick;
	struct FootContact { Fvector position, direction; };
	xr_vector<FootContact> feet;
	for (u32 n = 0; n < Level().Objects.o_count(); ++n)
	{
		CActor* actor = smart_cast<CActor*>(Level().Objects.o_get_by_iterator(n));
		if (!actor || actor->ID() == 0 || !actor->g_Alive() || actor->getDestroy()) continue;
		const u32 move = actor->MovingState();
		if (!(move & (mcFwd | mcBack | mcLStrafe | mcRStrafe)) || (move & (mcJump | mcClimb))) continue;
		FootContact contact; contact.position = actor->Position(); contact.direction.set(0.f, 0.f, 0.f);
		if (move & mcFwd) contact.direction.add(actor->XFORM().k);
		if (move & mcBack) contact.direction.sub(actor->XFORM().k);
		if (move & mcRStrafe) contact.direction.add(actor->XFORM().i);
		if (move & mcLStrafe) contact.direction.sub(actor->XFORM().i);
		contact.direction.y = 0.f;
		if (contact.direction.square_magnitude() < EPS_S) continue;
		contact.direction.normalize(); feet.push_back(contact);
	}
	for (u32 n = 0; n < Level().Objects.o_count(); ++n)
	{
		CObject* object = Level().Objects.o_get_by_iterator(n);
		CPhysicsShellHolder* holder = smart_cast<CPhysicsShellHolder*>(object);
		CEntityAlive* creature = smart_cast<CEntityAlive*>(object);
		if (!holder || holder->getDestroy() || holder->H_Parent() || !holder->PPhysicsShell()) continue;
		if (!smart_cast<CInventoryItem*>(object) && !(creature && !creature->g_Alive())) continue;
		const u16 count = holder->PHGetSyncItemsNumber();
		if (!count || count > 128) continue;
		// Client replica colliders are fixed; only the authority integrates
		// contact pushes. Walking against a body gives a small, mass-scaled
		// impulse, never a position correction or an unvalidated client force.
		for (const FootContact& foot : feet)
		{
			for (u16 i = 0; i < count; ++i)
			{
				SPHNetState body; holder->PHGetSyncItem(i)->get_State(body);
				Fvector gap; gap.sub(body.position, foot.position);
				if (gap.y < -0.2f || gap.y > 0.8f) continue;
				gap.y = 0.f;
				if (gap.square_magnitude() > 0.36f || gap.dotproduct(foot.direction) < -0.05f) continue;
				const float target = creature ? 0.16f : 0.5f;
				const float gain = _max(0.f, target - body.linear_vel.dotproduct(foot.direction));
				if (gain > 0.f)
				{
					holder->PPhysicsShell()->Enable();
					holder->PPhysicsShell()->applyImpulse(foot.direction,
						_min(holder->PPhysicsShell()->getMass(), 120.f) * _min(gain, target));
				}
				break;
			}
		}
		NET_Packet P;
		P.w_begin(M_NETCOOP_PHYSICS);
		P.w_u16(holder->ID());
		P.w_u32(Level().timeServer());
		P.w_u16(count);
		for (u16 i = 0; i < count; ++i)
		{
			SPHNetState state;
			holder->PHGetSyncItem(i)->get_State(state);
			P.w_u8(state.enabled ? 1 : 0);
			P.w_vec3(state.position);
			P.w_float(state.quaternion.x);
			P.w_float(state.quaternion.y);
			P.w_float(state.quaternion.z);
			P.w_float(state.quaternion.w);
			P.w_vec3(state.linear_vel);
		}
		struct SendPhysics
		{
			xrServer* server;
			CPhysicsShellHolder* holder;
			NET_Packet* packet;
			u32 tick;
			void operator()(IClient* client)
			{
				xrClientData* CL = static_cast<xrClientData*>(client);
				if (CL == server->GetServerClient() || !CL->flags.bConnected || !CL->gamma_snapshot_ready || !CL->owner) return;
				const float distance = CL->owner->o_Position.distance_to(holder->Position());
				const u32 every = distance < 50.f ? 1 : distance < 150.f ? 2 : distance < 300.f ? 5 : 20;
				if ((tick + holder->ID()) % every || !server->HasSendQueueRoom(CL, 64)) return;
				server->SendTo(CL->ID, *packet, net_flags(FALSE, TRUE));
			}
		} send = {server, holder, &P, tick};
		server->ForEachClientDo(send);
	}
}
} // namespace netcoop

namespace netcoop
{
bool smooth()
{
	return enabled() && g_netcoop_smooth != 0;
}

// Snapshot timing seen by this client (exponential averages, ms): the
// interpolation delay covers the usual interval plus three deviations so a
// late snapshot still arrives before it is needed.
static float s_snap_interval = 33.f;
static float s_snap_jitter = 5.f;
// Real-time length of this client's frames: snapshots are applied once a
// frame, so an object's newest snapshot can be a frame older than it is.
static float s_frame_ema = 33.f;
static u32 s_frame_last = 0;

namespace
{
CTimer& real_timer()
{
	static CTimer timer;
	static bool started = false;
	if (!started)
	{
		timer.Start();
		started = true;
	}
	return timer;
}

// Server time minus real time, from the freshest snapshots of the current
// and previous second (a window, so a wrong estimate lasts at most 2 s; the
// old maximum-with-decay held one stamp from the future for tens of seconds,
// s96). A jump ahead by more than 250 ms needs 5 confirming snapshots. The
// clock shown moves toward the estimate at most 10 % faster or slower than
// real time, so the timeline never jumps.
bool s_snapshot_clock_valid = false;
double s_clock_now_max = 0.0, s_clock_prev_max = 0.0;
bool s_clock_prev_valid = false;
u32 s_clock_bucket_time = 0;
double s_clock_candidate = 0.0;
u32 s_clock_candidates = 0;
double s_clock_applied = 0.0;
u32 s_clock_applied_time = 0;

double snapshot_clock_target()
{
	return s_clock_prev_valid ? _max(s_clock_now_max, s_clock_prev_max) : s_clock_now_max;
}

void snapshot_clock_advance(u32 now)
{
	const double target = snapshot_clock_target();
	const double elapsed = now > s_clock_applied_time ? double(now - s_clock_applied_time) : 0.0;
	s_clock_applied_time = now;
	const double diff = target - s_clock_applied;
	if (_abs(diff) > 500.0)
		s_clock_applied = target;
	else
	{
		const double step = 0.1 * elapsed;
		s_clock_applied += diff > 0.0 ? _min(diff, step) : _max(diff, -step);
	}
}
} // namespace

} // namespace netcoop
bool netcoop_is_player_actor(u16 id); // game_sv_single.cpp
namespace netcoop
{
bool server_player_copy(const CObject* object)
{
	return object && enabled() && !pure_client() && g_pGameLevel && Level().Server && object->ID() != 0 &&
		netcoop_is_player_actor(object->ID());
}

u32 real_time_ms()
{
	return real_timer().GetElapsed_ms();
}

void snapshot_sample(u32 server_stamp)
{
	if (!pure_client())
		return;
	const u32 now = real_time_ms();
	const double offset = double(server_stamp) - double(now);
	if (!s_snapshot_clock_valid)
	{
		s_clock_now_max = s_clock_applied = offset;
		s_clock_bucket_time = s_clock_applied_time = now;
		s_snapshot_clock_valid = true;
		return;
	}
	if (now - s_clock_bucket_time >= 1000)
	{
		s_clock_prev_max = s_clock_now_max;
		s_clock_prev_valid = true;
		s_clock_now_max = offset;
		s_clock_bucket_time = now;
		s_clock_candidates = 0;
	}
	if (offset > snapshot_clock_target() + 250.0)
	{
		// Far ahead of the others: wait for confirmation.
		s_clock_candidate = s_clock_candidates ? _min(s_clock_candidate, offset) : offset;
		if (++s_clock_candidates < 5)
			return;
		s_clock_now_max = s_clock_candidate;
		s_clock_prev_valid = false;
		s_clock_candidates = 0;
		return;
	}
	if (offset > s_clock_now_max)
		s_clock_now_max = offset;
}

u32 snapshot_now()
{
	if (!s_snapshot_clock_valid || !pure_client())
		return g_pGameLevel ? Level().timeServer() : 0;
	const u32 now = real_time_ms();
	snapshot_clock_advance(now);
	return u32(s64(now) + s64(s_clock_applied));
}

u32 remote_interp_delay()
{
	if (!(pure_client() && g_netcoop_smooth))
		return NET_Latency;
	const float adaptive = s_snap_interval + 3.f * s_snap_jitter;
	const float delay = _max(float(g_netcoop_interp_ms), _min(adaptive, 250.f));
	return u32(delay);
}

u32 remote_interp_delay(u32 last_interval)
{
	const u32 base = remote_interp_delay();
	if (!(pure_client() && g_netcoop_smooth))
		return base;
	// The object's own snapshot interval (far ones are sent less often) plus
	// two client frames and a margin: s93 extrapolated 14-22 % of frames
	// with 1.5 x interval at 40-60 ms client frames.
	const u32 frames = u32(2.f * _min(s_frame_ema, 100.f));
	return _max(base, _min(last_interval + frames + 30, 800u));
}

namespace
{
struct Metrics
{
	u32 frames, frame_ms_sum, frame_ms_max, frames_over_33, frames_over_100;
	u32 snaps, snap_ms_sum, snap_ms_max, snaps_over_100, dups;
	u32 puppet_frames, extrap_frames, jumps;
	float jump_max;
	s64 lead_sum;
	s32 lead_min, lead_max;
	u32 pl_frames, pl_extrap;
	s64 pl_lead_sum;
	s32 pl_lead_max;
	float pl_step_max;
	u32 acks, fixes;
	float err_sum, err_max;
	u32 owner_rejects;
	float owner_reject_max;
	u32 shots;
	u32 sv_bytes, sv_ticks, sv_objects;
	u32 sv_blocked;
};
Metrics m;
u32 next_print = 0;

struct PuppetTrack
{
	Fvector pos;
	u32 time;
};
xr_map<u16, PuppetTrack> puppets;
xr_map<u16, u32> shot_log_time;
} // namespace

void metric_snapshot(u32 interval_ms)
{
	if (interval_ms < 1000)
	{
		// Far objects are sent every 2-16 ticks on purpose; only near-rate
		// intervals measure network jitter.
		const float x = float(_min(interval_ms, 90u));
		s_snap_interval += (x - s_snap_interval) * 0.02f;
		s_snap_jitter += (_abs(x - s_snap_interval) - s_snap_jitter) * 0.02f;
	}
	++m.snaps;
	m.snap_ms_sum += interval_ms;
	m.snap_ms_max = _max(m.snap_ms_max, interval_ms);
	if (interval_ms > 100)
		++m.snaps_over_100;
}

void metric_snapshot_duplicate()
{
	++m.dups;
}

// A jump is a frame step longer than a running NPC can cover (10 m/s) plus
// 0.25 m: the object was teleported, not moved.
void metric_puppet_frame(u16 id, const Fvector& pos, bool extrapolating, s32 lead_ms)
{
	if (!m.puppet_frames || lead_ms < m.lead_min)
		m.lead_min = lead_ms;
	if (!m.puppet_frames || lead_ms > m.lead_max)
		m.lead_max = lead_ms;
	m.lead_sum += lead_ms;
	++m.puppet_frames;
	if (extrapolating)
		++m.extrap_frames;
	PuppetTrack& t = puppets[id];
	const u32 now = Device.dwTimeGlobal;
	if (t.time && now - t.time < 500)
	{
		const float step = t.pos.distance_to(pos);
		const float allowed = 0.25f + 10.f * float(now - t.time) / 1000.f;
		if (step > allowed)
		{
			++m.jumps;
			m.jump_max = _max(m.jump_max, step);
		}
	}
	t.pos = pos;
	t.time = now;
}

void metric_player_frame(bool extrapolating, s32 lead_ms, float step)
{
	++m.pl_frames;
	if (extrapolating)
		++m.pl_extrap;
	m.pl_lead_sum += lead_ms;
	m.pl_lead_max = _max(m.pl_lead_max, lead_ms);
	m.pl_step_max = _max(m.pl_step_max, step);
}

namespace
{
struct RemoteActorStat
{
	u32 frames;
	bool remote;
	bool alive;
	u32 net_size;
	s32 age;
};
xr_map<u16, RemoteActorStat> s_remote_actors;
u32 s_remote_actors_next = 0;
}

void metric_remote_actor(u16 id, bool remote, bool alive, u32 net_size, s32 age_ms)
{
	RemoteActorStat& s = s_remote_actors[id];
	++s.frames;
	s.remote = remote;
	s.alive = alive;
	s.net_size = net_size;
	s.age = age_ms;
	const u32 now = real_time_ms();
	if (now < s_remote_actors_next)
		return;
	s_remote_actors_next = now + 10000;
	for (auto& it : s_remote_actors)
	{
		if (it.second.frames)
			Msg("[Lost Zone][player] %u: %u frames, remote %d alive %d, %u snapshots, newest %d ms old", it.first,
			    it.second.frames, it.second.remote ? 1 : 0, it.second.alive ? 1 : 0, it.second.net_size, it.second.age);
		it.second.frames = 0;
	}
}

void metric_actor_error(float error, bool applied)
{
	++m.acks;
	m.err_sum += error;
	m.err_max = _max(m.err_max, error);
	if (applied)
		++m.fixes;
}

void metric_snapshot_blocked()
{
	++m.sv_blocked;
}

void metric_server_sent(u32 bytes, u32 objects)
{
	m.sv_bytes += bytes;
	++m.sv_ticks;
	m.sv_objects = objects;
}

void metric_owner_step_rejected(float step)
{
	++m.owner_rejects;
	m.owner_reject_max = _max(m.owner_reject_max, step);
}

// Server: who an NPC shoots at and whether it sees the target. Client: a
// puppet's weapon must never start firing on its own.
void metric_weapon_fire(CWeapon* weapon)
{
	if (!enabled() || !g_pGameLevel || !weapon || !weapon->H_Parent())
		return;
	CAI_Stalker* stalker = smart_cast<CAI_Stalker*>(weapon->H_Parent());
	if (!stalker)
	{
		// Server: a player's weapon fires; is the owner's aim there?
		CActor* player = smart_cast<CActor*>(weapon->H_Parent());
		if (player && server_player_copy(player))
		{
			const u32 now = Device.dwTimeGlobal;
			u32& last = shot_log_time[player->ID()];
			if (last && now - last < 1000)
				return;
			last = now;
			Fvector pos, dir;
			const bool aim = weapon->netcoop_aim(pos, dir);
			Msg("[Lost Zone][shot] player %s fires %s, owner aim %s", player->cName().c_str(),
			    weapon->cNameSect().c_str(), aim ? "fresh" : "missing");
		}
		return;
	}
	++m.shots;
	const u32 now = Device.dwTimeGlobal;
	u32& last = shot_log_time[stalker->ID()];
	if (last && now - last < 3000)
		return;
	last = now;
	if (pure_client())
	{
		Msg("[Lost Zone][shot] client puppet %s (%u) started firing %s", stalker->cName().c_str(), stalker->ID(),
		    weapon->cNameSect().c_str());
		return;
	}
	const CEntityAlive* enemy = stalker->g_Alive() ? stalker->memory().enemy().selected() : 0;
	Msg("[Lost Zone][shot] %s (%u) fires %s at %s (%u) dist %.1f visible %d", stalker->cName().c_str(), stalker->ID(),
	    weapon->cNameSect().c_str(), enemy ? enemy->cName().c_str() : "no enemy", enemy ? enemy->ID() : 0,
	    enemy ? enemy->Position().distance_to(stalker->Position()) : 0.f,
	    enemy ? int(stalker->memory().visual().visible_now(enemy)) : 0);
}

namespace
{
bool s_own_dead = false;
bool s_respawn_sent = false;
u32 s_death_time = 0;
u32 s_respawn_sent_time = 0;
const u32 respawn_delay_ms = 10000;
}

void client_on_own_death()
{
	s_own_dead = true;
	s_respawn_sent = false;
	s_death_time = real_time_ms();
	Msg("[Lost Zone] player died, respawn in %u s", respawn_delay_ms / 1000);
}

void client_death_frame()
{
	if (!s_own_dead || !pure_client() || !g_pGameLevel)
		return;
	CActor* own = smart_cast<CActor*>(Level().CurrentControlEntity());
	if (own && own->g_Alive())
	{
		s_own_dead = false; // the server gave a new Actor
		return;
	}
	const u32 now = real_time_ms();
	if (s_respawn_sent && now - s_respawn_sent_time > 5000)
		s_respawn_sent = false; // ask again if nothing came
	if ((now / 500) % 2)
		return; // blink
	CGameFont* font = UI().Font().pFontGraffiti22Russian;
	if (!font)
		return;
	const u32 elapsed = now - s_death_time;
	string256 text;
	if (elapsed < respawn_delay_ms)
		xr_sprintf(text, "%s %u", CStringTable().translate("st_netcoop_respawn_in").c_str(),
		           (respawn_delay_ms - elapsed + 999) / 1000);
	else
		xr_strcpy(text, CStringTable().translate("st_netcoop_respawn_press").c_str());
	font->SetAligment(CGameFont::alCenter);
	font->SetColor(0xffffffff);
	font->OutSetI(0.f, -0.25f);
	font->OutNext("%s", text);
}

bool client_death_key(int key)
{
	if (!s_own_dead || !pure_client())
		return false;
	if (real_time_ms() - s_death_time < respawn_delay_ms || s_respawn_sent)
		return true;
	if (get_binded_action(key) != kJUMP)
		return true;
	s_respawn_sent = true;
	s_respawn_sent_time = real_time_ms();
	client_send_command("respawn");
	return true;
}

void metrics_update()
{
	client_death_frame();
	if (!enabled())
		return;
	const u32 dt = Device.dwTimeDelta;
	const u32 real_now = real_time_ms();
	if (s_frame_last && real_now > s_frame_last)
		s_frame_ema += (float(_min(real_now - s_frame_last, 250u)) - s_frame_ema) * 0.05f;
	s_frame_last = real_now;
	++m.frames;
	m.frame_ms_sum += dt;
	m.frame_ms_max = _max(m.frame_ms_max, dt);
	if (dt > 33)
		++m.frames_over_33;
	if (dt > 100)
		++m.frames_over_100;

	const u32 now = GetTickCount();
	if (!next_print)
		next_print = now + 10000;
	if (now < next_print)
		return;
	next_print = now + 10000;
	if (g_netcoop_metrics)
	{
		const float day_sec = g_pGameLevel ? Level().GetGameDayTimeSec() : 0.f;
		Msg("[Lost Zone][clock] %s game %02u:%02u factor %.1f | net delta %d ms ping %u ms | snapshot lead avg %d min %d max %d ms"
		    " | players: frames %u extrap %.1f%% lead avg %d max %d ms, largest frame step %.2f m",
		    pure_client() ? "client" : "server", u32(day_sec / 3600.f) % 24, u32(day_sec / 60.f) % 60,
		    g_pGameLevel ? Level().GetGameTimeFactor() : 0.f, g_pGameLevel ? Level().timeServer_Delta() : 0,
		    g_pGameLevel ? Level().GetStatistic().getPing() : 0u,
		    m.puppet_frames ? s32(m.lead_sum / s64(m.puppet_frames)) : 0, m.lead_min, m.lead_max,
		    m.pl_frames, m.pl_frames ? 100.f * m.pl_extrap / m.pl_frames : 0.f,
		    m.pl_frames ? s32(m.pl_lead_sum / s64(m.pl_frames)) : 0, m.pl_lead_max, m.pl_step_max);
		Msg("[Lost Zone][metrics] %s smooth=%d delay=%u | frame avg %.1f max %u >33ms %u >100ms %u"
		    " | snaps %u avg %.0f max %u >100ms %u dup %u | puppets %u extrap %.1f%% jumps %u max %.2f"
		    " | actor acks %u fixes %u err avg %.2f max %.2f | owner rejects %u max %.1f | shots %u"
		    " | sent %.1f KB/s objects %u blocked %u",
		    pure_client() ? "client" : "server", g_netcoop_smooth, remote_interp_delay(),
		    m.frames ? float(m.frame_ms_sum) / m.frames : 0.f, m.frame_ms_max, m.frames_over_33, m.frames_over_100,
		    m.snaps, m.snaps ? float(m.snap_ms_sum) / m.snaps : 0.f, m.snap_ms_max, m.snaps_over_100, m.dups,
		    m.puppet_frames, m.puppet_frames ? 100.f * m.extrap_frames / m.puppet_frames : 0.f, m.jumps, m.jump_max,
		    m.acks, m.fixes, m.acks ? m.err_sum / m.acks : 0.f, m.err_max, m.owner_rejects, m.owner_reject_max,
		    m.shots, m.sv_bytes / 1024.f / 10.f, m.sv_objects, m.sv_blocked);
	}
	ZeroMemory(&m, sizeof(m));
	if (puppets.size() > 4096)
		puppets.clear();
	if (shot_log_time.size() > 4096)
		shot_log_time.clear();
}
} // namespace netcoop

void netcoop_respawn_spawn(ClientID id); // game_sv_single.cpp
namespace netcoop
{
bool script_respawn(u16 actor_id)
{
	if (!enabled() || !g_pGameLevel || !Level().Server)
		return false;
	xrServer* server = Level().Server;
	FindActorOwner find;
	find.actor_id = actor_id;
	xrClientData* CL = static_cast<xrClientData*>(server->FindClient(find));
	if (!CL || !CL->owner)
		return false;
	CActor* body = smart_cast<CActor*>(Level().Objects.net_Find(actor_id));
	if (!body || body->g_Alive())
		return false;
	// The body and what it carries stay in the world as a corpse, owned by
	// the server; the player gets a new Actor at the spawn point.
	server_character_save_actor(actor_id);
	s_actor_character.erase(actor_id);
	give_to_server(server, CL->owner, 0);
	CL->owner = NULL;
	netcoop_respawn_spawn(CL->ID);
	Msg("[Lost Zone] respawn for client 0x%08x (body %u stays)", CL->ID.value(), actor_id);
	return true;
}
} // namespace netcoop

// ---------------------------------------------------------------------------
// RP animations (player emotes), configs/netcoop/rp_anims.ltx.
// ---------------------------------------------------------------------------
namespace netcoop
{
static void rp_split(LPCSTR text, xr_vector<shared_str>& out)
{
	out.clear();
	if (!text)
		return;
	const u32 count = _GetItemCount(text);
	string256 item;
	for (u32 i = 0; i < count; ++i)
	{
		_GetItem(text, i, item);
		_Trim(item);
		if (item[0])
			out.push_back(item);
	}
}

const xr_vector<RpAnim>& rp_anims()
{
	static xr_vector<RpAnim> anims;
	static bool loaded = false;
	if (loaded)
		return anims;
	loaded = true;
	string_path path;
	if (!FS.exist(path, "$game_config$", "netcoop\\rp_anims.ltx"))
	{
		Msg("~ [Lost Zone] rp: configs\\netcoop\\rp_anims.ltx not found");
		return anims;
	}
	CInifile ini(path, TRUE, TRUE, FALSE);
	if (!ini.section_exist("rp_list"))
		return anims;
	CInifile::Sect& list = ini.r_section("rp_list");
	for (auto it = list.Data.begin(); it != list.Data.end() && anims.size() < 250; ++it)
	{
		string128 section;
		xr_sprintf(section, "rp_%s", it->first.c_str());
		if (!ini.section_exist(section))
			continue;
		RpAnim a;
		a.name = it->first;
		a.title = ini.line_exist(section, "title") ? ini.r_string(section, "title") : it->first.c_str();
		rp_split(ini.line_exist(section, "in") ? ini.r_string(section, "in") : NULL, a.in);
		rp_split(ini.line_exist(section, "mid") ? ini.r_string(section, "mid") : NULL, a.mid);
		rp_split(ini.line_exist(section, "out") ? ini.r_string(section, "out") : NULL, a.out);
		a.loop = ini.line_exist(section, "loop") ? !!ini.r_bool(section, "loop") : true;
		anims.push_back(a);
	}
	Msg("[Lost Zone] rp: %u animations", u32(anims.size()));
	return anims;
}

LPCSTR script_rp_list()
{
	static xr_string text;
	text.clear();
	for (const RpAnim& a : rp_anims())
	{
		text += a.name.c_str();
		text += "=";
		text += a.title.c_str();
		text += ";";
	}
	return text.c_str();
}

bool script_rp_play(LPCSTR name)
{
	CActor* actor = Actor();
	if (!actor || !actor->g_Alive() || !name)
		return false;
	const xr_vector<RpAnim>& anims = rp_anims();
	for (u32 i = 0; i < anims.size(); ++i)
	{
		if (!xr_strcmp(anims[i].name, name))
		{
			actor->rp_start(int(i), true);
			return true;
		}
	}
	return false;
}

void script_rp_stop()
{
	if (CActor* actor = Actor())
		actor->rp_request_stop(true);
}

LPCSTR script_rp_active()
{
	CActor* actor = Actor();
	if (!actor || actor->m_rp_index < 0 || actor->m_rp_index >= int(rp_anims().size()))
		return "";
	return rp_anims()[actor->m_rp_index].name.c_str();
}
} // namespace netcoop
