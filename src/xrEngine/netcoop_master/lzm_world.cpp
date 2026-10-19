#include "lzm_world.h"
#include "lzm_timelines.h"

#include <charconv>
#include <cstring>

namespace lzm
{
static uint64_t parse_u64(const std::string& text)
{
    uint64_t v = 0;
    auto r = std::from_chars(text.data(), text.data() + text.size(), v);
    if (r.ec != std::errc() || r.ptr != text.data() + text.size()) throw Unavailable("world identity is corrupt");
    return v;
}

static uint64_t random_bits(int bits)
{
    std::string raw = random_bytes(8);
    uint64_t v = 0;
    memcpy(&v, raw.data(), 8);
    return bits >= 64 ? v : (v & ((uint64_t(1) << bits) - 1));
}

World::World(Store& s, std::optional<uint64_t> id, std::optional<uint64_t> world_seed, double initial_ms, double scale)
    : store(s)
{
    if (store.epoch) throw Conflict("world service already bootstrapped");
    finite(initial_ms);
    finite(scale, 0.001, 1000);
    if (id && *id == 0) throw Invalid("invalid WorldID");
    json row = store.transaction([&](Db& tx) -> json {
        json row = tx.one("SELECT * FROM world WHERE singleton=1");
        if (row.is_null())
        {
            uint64_t chosen = id ? *id : random_bits(63);
            if (!chosen) chosen = 1;
            tx.exec("INSERT INTO world VALUES(1,?,?,?,?,?,1,1,0)",
                    { std::to_string(chosen), std::to_string(world_seed ? *world_seed : random_bits(64)), 1, initial_ms, scale });
        }
        else
        {
            if (id && std::to_string(*id) != row["world_id"].get<std::string>()) throw Conflict("database belongs to a different world");
            if (world_seed && std::to_string(*world_seed) != row["seed"].get<std::string>()) throw Conflict("world seed cannot be changed on restart");
            positive(row["epoch"].get<int64_t>() + 1, "authority epoch");
            tx.exec("UPDATE world SET epoch=epoch+1,world_ms=MAX(world_ms,event_highwater),sequence=1,revision=revision+1 WHERE singleton=1");
        }
        row = tx.one("SELECT * FROM world WHERE singleton=1");
        // The ownership epoch changes, semantic state does not (world.py).
        tx.exec("UPDATE entity SET fence=? WHERE writer LIKE 'offline:%'", { row["epoch"] });
        return row;
    });
    store.epoch = row["epoch"].get<int64_t>();
    world_id = parse_u64(row["world_id"].get<std::string>());
    seed = parse_u64(row["seed"].get<std::string>());
    anchor_ms_ = row["world_ms"].get<double>();
    scale_ = row["scale"].get<double>();
    anchor_ns_ = last_ns_ = monotonic_ns();
    last_wall_ms_ = wall_ms();
}

double World::now()
{
    std::lock_guard<std::recursive_mutex> guard(store.lock);
    store.require_epoch(store.db);
    if (mutation_cut_) return *mutation_cut_;
    int64_t now = monotonic_ns();
    if (now < last_ns_) throw Unavailable("monotonic clock regressed");
    last_ns_ = now;
    return finite(anchor_ms_ + double(now - anchor_ns_) / 1000000.0 * scale_);
}

int64_t World::real_ms()
{
    std::lock_guard<std::recursive_mutex> guard(store.lock);
    int64_t value = wall_ms();
    if (value < last_wall_ms_) throw Unavailable("lease clock regressed");
    last_wall_ms_ = value;
    return value;
}

Store::Apply World::mutation(Store::Apply apply)
{
    return [this, apply](Db& tx) -> json {
        if (mutation_cut_) throw Unavailable("recursive world mutation during event resolution");
        double cutoff = now();
        mutation_cut_ = cutoff;
        struct Clear { std::optional<double>& cut; ~Clear() { cut.reset(); } } clear{ mutation_cut_ };
        if (mutation_drain) mutation_drain(tx, cutoff);
        return apply(tx);
    };
}

json World::sample()
{
    return store.transaction([&](Db& tx) { return sample_in(tx); });
}

json World::sample_in(Db& tx)
{
    double at = now();
    tx.exec("UPDATE world SET world_ms=?,sequence=sequence+1 WHERE singleton=1", { at });
    json row = tx.one("SELECT * FROM world WHERE singleton=1");
    return { { "schema", 1 }, { "world_id", parse_u64(row["world_id"].get<std::string>()) },
             { "seed", parse_u64(row["seed"].get<std::string>()) }, { "authority_epoch", row["epoch"] },
             { "sequence", row["sequence"] }, { "world_ms", at }, { "time_scale", scale_ }, { "revision", row["revision"] } };
}

json World::bootstrap_snapshot(bool engine)
{
    return store.transaction([&](Db& tx) -> json {
        json clock = sample_in(tx);
        auto rows = tx.all(engine ? "SELECT * FROM world_state WHERE name IN ('weather','emission','psi_storm') ORDER BY name"
                                  : "SELECT * FROM world_state ORDER BY name");
        int64_t watermark = tx.scalar("SELECT COALESCE(MAX(sequence),0) FROM world_event").get<int64_t>();
        json states = json::object();
        for (auto& row : rows)
        {
            json envelope = { { "version", row["version"] }, { "state", loads(row["state"].get<std::string>()) } };
            std::string name = row["name"].get<std::string>();
            states[name] = engine ? Timelines::public_state(name, envelope) : envelope;
        }
        return { { "schema", 1 }, { "clock", clock }, { "world_seed", seed }, { "state_revision", clock["revision"] },
                 { "event_watermark", watermark }, { "states", states } };
    });
}

json World::set_state(const std::string& actor, const std::string& command_id, const json& name_value, const json& version_value, const json& state)
{
    std::string name = identifier(name_value);
    if (name.size() > 64 || !version_value.is_number_integer() || as_int(version_value) < 0 || !state.is_object())
        throw Invalid("invalid world state command");
    int64_t version = as_int(version_value);
    std::string encoded = canonical(state);
    json payload = { { "type", "world_state" }, { "name", name }, { "version", version }, { "state", state } };
    return store.command(actor, command_id, payload, mutation([=](Db& tx) -> json {
        json row = tx.one("SELECT version FROM world_state WHERE name=?", { name });
        if ((row.is_null() ? 0 : row["version"].get<int64_t>()) != version) throw Conflict("world state version changed");
        tx.exec("INSERT INTO world_state VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET version=excluded.version,state=excluded.state",
                { name, version + 1, encoded });
        int64_t event = store.event(tx, "world:" + name, "WorldStateChanged", payload, now());
        return { { "name", name }, { "version", version + 1 }, { "event", event } };
    }));
}

json World::set_scale(const std::string& actor, const std::string& command_id, const json& value_json)
{
    double value = finite(value_json, 0.001, 1000);
    std::lock_guard<std::recursive_mutex> guard(store.lock);
    double at = now();
    int64_t anchor_ns = last_ns_;
    json payload = { { "type", "scale" }, { "value", value_json } };
    json result = store.command(actor, command_id, payload, mutation([&](Db& tx) -> json {
        at = now();
        anchor_ns = last_ns_;
        tx.exec("UPDATE world SET world_ms=?,scale=?,sequence=sequence+1 WHERE singleton=1", { at, value });
        int64_t event = store.event(tx, "world", "ScaleChanged", { { "scale", value_json } }, at);
        return { { "world_ms", at }, { "scale", value_json }, { "event", event } };
    }));
    double current = store.db.scalar("SELECT scale FROM world WHERE singleton=1").get<double>();
    if (current != scale_)
    {
        anchor_ms_ = at;
        anchor_ns_ = anchor_ns;
        scale_ = current;
    }
    return result;
}

json World::claim_location(const std::string& actor, const std::string& command_id, const json& location_value,
                           const json& capacity_value, const json& ttl_value)
{
    identifier(actor);
    std::string location = identifier(location_value);
    if (!capacity_value.is_number_integer() || as_int(capacity_value) < 1 || as_int(capacity_value) > 128)
        throw Invalid("invalid location capacity");
    if (!ttl_value.is_number_integer() || as_int(ttl_value) < 1000 || as_int(ttl_value) > 60000)
        throw Invalid("invalid lease duration");
    int64_t capacity = as_int(capacity_value), ttl = as_int(ttl_value);
    json payload = { { "type", "claim_location" }, { "location", location }, { "capacity", capacity }, { "ttl_ms", ttl } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        int64_t real = real_ms();
        double at = now();
        json row = tx.one("SELECT * FROM location_lease WHERE location=?", { location });
        int64_t fence;
        if (!row.is_null() && row["expires_ms"].get<int64_t>() > real)
        {
            if (row["owner"] != actor) throw Conflict("location already has an active owner");
            fence = row["fence"].get<int64_t>();
        }
        else
            fence = positive(row.is_null() ? 1 : row["fence"].get<int64_t>() + 1, "location fence");
        tx.exec("INSERT INTO location_lease VALUES(?,?,?,?,?) ON CONFLICT(location) DO UPDATE SET owner=excluded.owner,fence=excluded.fence,expires_ms=excluded.expires_ms,capacity=excluded.capacity",
                { location, actor, fence, real + ttl, capacity });
        int64_t event = store.event(tx, "location:" + location, "LocationClaimed",
                                    { { "owner", actor }, { "fence", fence }, { "expires_ms", real + ttl } }, at);
        return { { "location", location }, { "owner", actor }, { "fence", fence }, { "expires_ms", real + ttl }, { "event", event } };
    }, nullptr, [&](Db& tx, const json& result) { require_location(tx, actor, location, result["fence"].get<int64_t>()); });
}

json World::renew_location(const std::string& actor, const std::string& command_id, const json& location_value,
                           const json& fence_value, const json& ttl_value)
{
    int64_t fence = positive(fence_value, "location fence");
    std::string location = identifier(location_value);
    if (!ttl_value.is_number_integer() || as_int(ttl_value) < 1000 || as_int(ttl_value) > 60000)
        throw Invalid("invalid lease duration");
    int64_t ttl = as_int(ttl_value);
    json payload = { { "type", "renew" }, { "location", location }, { "fence", fence }, { "ttl_ms", ttl } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        require_location(tx, actor, location, fence);
        int64_t expiry = real_ms() + ttl;
        tx.exec("UPDATE location_lease SET expires_ms=? WHERE location=?", { expiry, location });
        for (auto& hook : lease_renew_hooks) hook.second(tx, actor, location, fence);
        return { { "location", location }, { "fence", fence }, { "expires_ms", expiry } };
    }, [&](Db& tx) { require_location(tx, actor, location, fence); });
}

json World::require_location(Db& tx, const std::string& actor, const std::string& location, int64_t fence)
{
    json row = tx.one("SELECT * FROM location_lease WHERE location=?", { location });
    if (row.is_null() || row["owner"] != actor || row["fence"].get<int64_t>() != fence || row["expires_ms"].get<int64_t>() <= real_ms())
        throw Conflict("location lease/fence is no longer active");
    return row;
}
} // namespace lzm
