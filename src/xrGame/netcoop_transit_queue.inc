// Durable local-host mailbox. One location/world-store owner consumes each
// map. No destructive read and no PID claim that strands records on restart.
// Completed records remain as idempotency tombstones: retrying a saved outbox
// cannot republish a previously acknowledged transfer.
static const size_t transit_max_bytes = 262144;

static bool transit_id_valid(LPCSTR id)
{
	if (!id || xr_strlen(id) != 32) return false;
	for (const char* c = id; *c; ++c)
		if (!(*c >= '0' && *c <= '9') && !(*c >= 'a' && *c <= 'f')) return false;
	return true;
}

static void cluster_transit_dir(string_path& path)
{
	string_path dir; cluster_dir(dir);
	xr_sprintf(path, "%stransit\\", dir);
	CreateDirectoryA(path, nullptr);
}

static void transit_path(LPCSTR level, LPCSTR id, LPCSTR suffix, string_path& path)
{
	string_path dir; cluster_transit_dir(dir);
	xr_sprintf(path, "%s%s_%s.%s", dir, level, id, suffix);
}

static bool transit_read(LPCSTR path, xr_string& content)
{
	content.clear();
	FILE* file = fopen(path, "rb");
	if (!file) return false;
	char buffer[4096]; size_t n;
	bool ok = true;
	while ((n = fread(buffer, 1, sizeof(buffer), file)) != 0)
	{
		if (n > transit_max_bytes - content.size()) { ok = false; break; }
		content.append(buffer, n);
	}
	ok = ok && !ferror(file) && !content.empty();
	if (fclose(file) != 0) ok = false;
	// Lua receives C strings. Reject embedded NUL, never truncate a payload.
	ok = ok && content.find('\0') == xr_string::npos;
	if (!ok) content.clear();
	return ok;
}

LPCSTR script_transit_id()
{
	static xr_string id;
	id.clear();
	u8 nonce[16];
	if (enabled() && random_bytes(nonce, sizeof(nonce))) id = to_hex(nonce, sizeof(nonce));
	return id.c_str();
}

bool script_transit_put(LPCSTR level, LPCSTR id, LPCSTR content)
{
	if (!enabled() || !cluster_name_valid(level) || !transit_id_valid(id) || !content || !content[0] ||
		xr_strlen(content) > transit_max_bytes) return false;
	string_path ready, done, temp;
	transit_path(level, id, "record", ready);
	transit_path(level, id, "done", done);
	xr_string previous;
	// Reusing an id with another payload is a conflict, including after ack.
	if (GetFileAttributesA(done) != INVALID_FILE_ATTRIBUTES) return transit_read(done, previous) && previous == content;
	if (GetFileAttributesA(ready) != INVALID_FILE_ATTRIBUTES) return transit_read(ready, previous) && previous == content;
	xr_sprintf(temp, "%s.%u.tmp", ready, GetCurrentProcessId());
	FILE* file = fopen(temp, "wb");
	if (!file) return false;
	const size_t size = xr_strlen(content);
	bool ok = fwrite(content, 1, size, file) == size && fflush(file) == 0 && _commit(_fileno(file)) == 0;
	if (fclose(file) != 0) ok = false;
	if (!ok || !MoveFileExA(temp, ready, MOVEFILE_WRITE_THROUGH))
	{
		DeleteFileA(temp);
		return transit_read(done, previous) ? previous == content : transit_read(ready, previous) && previous == content;
	}
	return true;
}

static LPCSTR transit_select(LPCSTR level, LPCSTR after_id, bool report_invalid)
{
	static xr_string result;
	result.clear();
	if (!enabled() || !cluster_name_valid(level) || !after_id ||
		(after_id[0] && !transit_id_valid(after_id))) return "";
	string_path dir, mask; cluster_transit_dir(dir);
	xr_sprintf(mask, "%s%s_*.record", dir, level);
	WIN32_FIND_DATAA found;
	HANDLE search = FindFirstFileA(mask, &found);
	if (search == INVALID_HANDLE_VALUE) return "";
	xr_string first, following;
	do
	{
		const xr_string name = found.cFileName;
		const size_t prefix = xr_strlen(level) + 1;
		if (name.size() != prefix + 32 + 7 || name.substr(0, prefix) != xr_string(level) + "_") continue;
		if (!transit_id_valid(name.substr(prefix, 32).c_str())) continue;
		if (first.empty() || name < first) first = name;
		if (name.substr(prefix, 32) > after_id && (following.empty() || name < following)) following = name;
	} while (FindNextFileA(search, &found));
	FindClose(search);
	if (first.empty()) return "";
	const xr_string& selected = following.empty() ? first : following;
	string_path path; xr_sprintf(path, "%s%s", dir, selected.c_str());
	xr_string content;
	if (!transit_read(path, content) && !report_invalid) return "";
	// A cursor-aware caller receives even a corrupt record's ID, with an
	// empty payload. Keep the file and let later records proceed on retry.
	result = selected.substr(xr_strlen(level) + 1, 32) + "\n" + content;
	return result.c_str();
}

LPCSTR script_transit_take(LPCSTR level)
{
	return transit_select(level, "", false);
}

LPCSTR script_transit_next(LPCSTR level, LPCSTR after_id)
{
	return transit_select(level, after_id, true);
}

bool script_transit_ack(LPCSTR level, LPCSTR id)
{
	if (!enabled() || !cluster_name_valid(level) || !transit_id_valid(id)) return false;
	string_path ready, done;
	transit_path(level, id, "record", ready);
	transit_path(level, id, "done", done);
	// Acknowledgment is an atomic durable rename, retaining the original
	// payload for collision checking. Never erase the last recovery copy.
	if (GetFileAttributesA(done) != INVALID_FILE_ATTRIBUTES) return true;
	return MoveFileExA(ready, done, MOVEFILE_WRITE_THROUGH) != 0;
}
