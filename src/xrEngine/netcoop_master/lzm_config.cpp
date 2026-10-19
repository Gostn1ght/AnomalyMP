// __main__.py: the master's private configuration and the key files it hands
// to the maps (bridge for every map, one writer per map).
#include "lzm_config.h"
#include "lzm_service.h"

#include <windows.h>

#include <fstream>
#include <set>
#include <sstream>

namespace lzm
{
static std::string read_file(const std::wstring& path)
{
    std::ifstream in(path, std::ios::binary);
    if (!in) throw Invalid("configuration cannot be read");
    std::ostringstream text;
    text << in.rdbuf();
    return text.str();
}

static bool exists(const std::wstring& path) { return GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES; }

static void make_parent(const std::wstring& path)
{
    std::wstring folder = path.substr(0, path.find_last_of(L"\\/"));
    if (folder.empty() || exists(folder)) return;
    make_parent(folder);
    CreateDirectoryW(folder.c_str(), nullptr);
}

// O_CREAT|O_EXCL + fsync, or a temporary file moved over the old one.
static void write_new(const std::wstring& path, const std::string& data, bool replace)
{
    make_parent(path);
    std::wstring temporary = path + L"." + widen(token_hex(16)) + L".tmp";
    HANDLE file = CreateFileW(replace ? temporary.c_str() : path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
    {
        if (GetLastError() == ERROR_FILE_EXISTS) throw Invalid("configuration already exists; credentials were not replaced");
        throw Unavailable("configuration file cannot be created");
    }
    DWORD written = 0;
    bool ok = WriteFile(file, data.data(), DWORD(data.size()), &written, nullptr) && written == data.size() && FlushFileBuffers(file);
    CloseHandle(file);
    if (!ok)
    {
        DeleteFileW(replace ? temporary.c_str() : path.c_str());
        throw Unavailable("configuration file cannot be written");
    }
    if (replace && !MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
    {
        DeleteFileW(temporary.c_str());
        throw Unavailable("configuration file cannot be replaced");
    }
}

static json load_config(const std::wstring& path)
{
    json config = loads(read_file(path));
    if (!config.is_object() || !config.contains("schema") || config["schema"] != 1) throw Invalid("unsupported service configuration");
    return config;
}

static std::pair<uint64_t, uint64_t> world_identity(const json& world_id, const json& seed)
{
    if (!world_id.is_number_integer() || (!world_id.is_number_unsigned() && world_id.get<int64_t>() <= 0)) throw Invalid("invalid WorldID");
    if (!seed.is_number_integer() || (!seed.is_number_unsigned() && seed.get<int64_t>() < 0)) throw Invalid("invalid world seed");
    return { world_id.get<uint64_t>(), seed.get<uint64_t>() };
}

static bool engine_location_ok(const std::string& name)
{
    if (name.empty() || name.size() > 64) return false;
    for (unsigned char c : name)
        if (!(isalnum(c) || c == '_') || c >= 0x80) return false;
    return true;
}

void create_config(const std::wstring& path, std::vector<std::string> locations, std::optional<uint64_t> world_id,
                   std::optional<uint64_t> seed, std::optional<double> initial_ms, std::optional<double> scale)
{
    if (exists(path)) throw Invalid("configuration already exists; credentials were not replaced");
    if (world_id.has_value() != seed.has_value()) throw Invalid("explicit world identity requires both WorldID and seed");
    if (locations.empty()) locations.push_back("hidden_base");
    std::set<std::string> sorted(locations.begin(), locations.end());
    json credentials = { { "admin", { { "role", "admin" }, { "token", token_urlsafe(48) } } } };
    for (auto& location : sorted)
    {
        identifier(location);
        credentials["location:" + location] = { { "role", "location" }, { "locations", { location } }, { "token", token_urlsafe(48) } };
    }
    credentials["observer:engine"] = { { "role", "observer" }, { "locations", json::array() }, { "token", token_urlsafe(48) } };
    json config = { { "schema", 1 }, { "database", "world.sqlite" }, { "port", 38477 }, { "signing_key", token_hex(32) }, { "credentials", credentials } };
    if (world_id)
    {
        if (*world_id == 0) throw Invalid("invalid WorldID");
        config["world_id"] = *world_id;
        config["seed"] = *seed;
    }
    if (initial_ms) config["initial_ms"] = finite(*initial_ms);
    if (scale) config["scale"] = finite(*scale, 0.001, 1000);
    write_new(path, python_dumps(config, false, 2), false);
}

bool add_location_credential(const std::wstring& path, const std::string& location)
{
    if (!engine_location_ok(location)) throw Invalid("invalid engine location name");
    json config = load_config(path);
    json& credentials = config["credentials"];
    Credentials check(credentials);
    std::string actor = "location:" + location;
    if (credentials.contains(actor)) return false;
    for (auto& entry : credentials)
        if (entry.contains("locations"))
            for (auto& l : entry["locations"])
                if (l == location) throw Invalid("another credential already covers this location");
    credentials[actor] = { { "role", "location" }, { "locations", { location } }, { "token", token_urlsafe(48) } };
    Credentials recheck(credentials);
    write_new(path, python_dumps(config, false, 2), true);
    return true;
}

void create_writer_config(const std::wstring& config_path, const std::wstring& destination, const std::string& location, bool replace)
{
    if (!engine_location_ok(location)) throw Invalid("invalid engine location name");
    std::wstring name = destination.substr(destination.find_last_of(L"\\/") + 1);
    if (name != widen("netcoop_world_writer_" + location + ".json")) throw Invalid("writer config filename must match its location");
    json config = load_config(config_path);
    Credentials check(config["credentials"]);
    std::string actor = "location:" + location;
    json credential = config["credentials"].contains(actor) ? config["credentials"][actor] : json();
    if (!credential.is_object() || credential.value("role", "") != "location" || credential.value("locations", json()) != json::array({ location }))
        throw Invalid("one dedicated location credential is required");
    auto [world_id, seed] = world_identity(config.contains("world_id") ? config["world_id"] : json(), config.contains("seed") ? config["seed"] : json());
    int64_t port = config.contains("port") ? as_int(config["port"]) : 38477;
    if (port < 1 || port > 65535) throw Invalid("writer requires a fixed loopback port");
    json body = { { "schema", 1 }, { "mode", "writer" }, { "host", "127.0.0.1" }, { "port", port }, { "token", credential["token"] },
                  { "actor", actor }, { "location", location }, { "master_world_id", world_id }, { "master_world_seed", seed } };
    std::string encoded = canonical(body);
    if (exists(destination) && read_file(destination) == encoded) return;
    if (exists(destination) && !replace) throw Invalid("writer config exists; explicit replacement required");
    write_new(destination, encoded, true);
}

void create_bridge_config(const std::wstring& config_path, const std::wstring& destination, bool authority, bool replace)
{
    json config = load_config(config_path);
    Credentials check(config["credentials"]);
    json entry = config["credentials"].contains("observer:engine") ? config["credentials"]["observer:engine"] : json();
    if (!entry.is_object() || entry.value("role", "") != "observer") throw Invalid("a dedicated read-only engine observer is required");
    int64_t port = config.contains("port") ? as_int(config["port"]) : 38477;
    if (port < 1 || port > 65535) throw Invalid("shadow bridge requires a fixed loopback port");
    std::wstring name = destination.substr(destination.find_last_of(L"\\/") + 1);
    if (name != L"netcoop_world_bridge.json") throw Invalid("engine bridge file must be netcoop_world_bridge.json");
    json body = { { "schema", 1 }, { "mode", "shadow" }, { "host", "127.0.0.1" }, { "port", port }, { "token", entry["token"] } };
    if (authority)
    {
        auto [world_id, seed] = world_identity(config.contains("world_id") ? config["world_id"] : json(), config.contains("seed") ? config["seed"] : json());
        body = { { "schema", 3 }, { "mode", "authority" }, { "host", "127.0.0.1" }, { "port", port }, { "token", entry["token"] },
                 { "master_world_id", world_id }, { "master_world_seed", seed } };
    }
    if (replace && authority && exists(destination)) DeleteFileW(destination.c_str());
    write_new(destination, python_dumps(body), false);
}
} // namespace lzm
