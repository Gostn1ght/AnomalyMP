// Included inside namespace netcoop in netcoop.cpp, after netcoop_voice_record.inc
// (uses its base64). PDA photos (owner 2026-10-10, after New Way; doc 89 P4):
// the photo mode takes a frame, the gallery keeps it in this PDA and a chat
// can carry it to other players.
//
// A photo is a small DDS (BC1, 640x360, opaque) under $game_saves$\netcoop_photos\.
// The texture loader also looks in $game_saves$ (as for save thumbnails), and
// FS.w_close registers a new file at once, so the UI shows it by the name
// "netcoop_photos\<name>" right after it is written - no rescan.
// The frame itself is taken by the renderer right before Present
// (IRender_interface::NetcoopPhotoRequest): with a flip-model swap chain the
// back buffer is undefined once presented, so Lua cannot read it directly.

static const u32 photo_max_bytes = 512u << 10;
static const u32 photo_max_side = 1024;
float g_netcoop_photo_zoom = 1.f;

// Only [A-Za-z0-9_], up to 64 characters: names come from Lua and other players.
static bool photo_name_ok(LPCSTR name)
{
	if (!name || !*name) return false;
	u32 n = 0;
	for (LPCSTR c = name; *c; ++c, ++n)
		if (n >= 64 || !(isalnum(u8(*c)) || *c == '_')) return false;
	return true;
}

static void photo_file(LPCSTR name, string_path& out)
{
	string_path rel;
	xr_sprintf(rel, "netcoop_photos\\%s.dds", name);
	FS.update_path(out, "$game_saves$", rel);
}

// A DDS this code would make: magic, header size 124, sane sides, BC1/BC3 or
// 32-bit, data enough for the top level.
static bool photo_dds_ok(const xr_vector<u8>& b)
{
	if (b.size() < 128 || b.size() > photo_max_bytes) return false;
	if (memcmp(&b[0], "DDS ", 4)) return false;
	u32 size, height, width, fourcc, pf_flags, bits;
	memcpy(&size, &b[4], 4);
	memcpy(&height, &b[12], 4);
	memcpy(&width, &b[16], 4);
	memcpy(&pf_flags, &b[80], 4);
	memcpy(&fourcc, &b[84], 4);
	memcpy(&bits, &b[88], 4);
	if (size != 124 || !width || !height || width > photo_max_side || height > photo_max_side) return false;
	u32 need;
	if (pf_flags & 4) // DDPF_FOURCC
	{
		if (fourcc == MAKEFOURCC('D', 'X', 'T', '1')) need = ((width + 3) / 4) * ((height + 3) / 4) * 8;
		else if (fourcc == MAKEFOURCC('D', 'X', 'T', '5')) need = ((width + 3) / 4) * ((height + 3) / 4) * 16;
		else return false;
	}
	else if (bits == 32) need = width * height * 4;
	else return false;
	return b.size() >= 128 + need;
}

// photo mode: take the next presented frame into netcoop_photos\<name>.dds
bool script_photo_take(LPCSTR name)
{
	if (g_dedicated_server || !::Render || !photo_name_ok(name)) return false;
	string_path path;
	photo_file(name, path);
	return ::Render->NetcoopPhotoRequest(path, 640, 360);
}

bool script_photo_exists(LPCSTR name)
{
	if (!photo_name_ok(name)) return false;
	string_path rel;
	xr_sprintf(rel, "netcoop_photos\\%s.dds", name);
	return !!FS.exist("$game_saves$", rel);
}

// size in bytes (0: none)
int script_photo_size(LPCSTR name)
{
	if (!script_photo_exists(name)) return 0;
	string_path path;
	photo_file(name, path);
	IReader* r = FS.r_open(path);
	if (!r) return 0;
	const int n = r->length();
	FS.r_close(r);
	return n;
}

// The file as base64 for a chat ("" if missing or not a photo).
LPCSTR script_photo_read(LPCSTR name)
{
	static xr_string out;
	out.clear();
	if (!script_photo_exists(name)) return "";
	string_path path;
	photo_file(name, path);
	IReader* r = FS.r_open(path);
	if (!r) return "";
	xr_vector<u8> bytes;
	if (u32(r->length()) <= photo_max_bytes)
		bytes.assign((const u8*)r->pointer(), (const u8*)r->pointer() + r->length());
	FS.r_close(r);
	if (!photo_dds_ok(bytes)) return "";
	rec_encode(bytes, out);
	return out.c_str();
}

// A photo from a chat into this PDA's cache; checked to be a plain DDS image.
bool script_photo_write(LPCSTR name, LPCSTR base64)
{
	if (g_dedicated_server || !photo_name_ok(name) || !base64 || xr_strlen(base64) > photo_max_bytes * 4 / 3 + 8) return false;
	xr_vector<u8> bytes;
	if (!rec_decode(base64, bytes) || !photo_dds_ok(bytes)) return false;
	string_path path;
	photo_file(name, path);
	IWriter* w = FS.w_open(path);
	if (!w) return false;
	w->w(&bytes[0], u32(bytes.size()));
	FS.w_close(w); // registers the file: the texture loader finds it now
	return true;
}

bool script_photo_delete(LPCSTR name)
{
	if (!script_photo_exists(name)) return false;
	string_path rel;
	xr_sprintf(rel, "netcoop_photos\\%s.dds", name);
	FS.file_delete("$game_saves$", rel);
	return true;
}

// Photo mode zoom (1 = off); the saved "fov" setting is not touched.
void script_photo_zoom(float zoom)
{
	clamp(zoom, 1.f, 8.f);
	g_netcoop_photo_zoom = zoom;
}
