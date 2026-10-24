// world.py: the world calendar (frozen while the service is down), location
// leases and their fences, world state rows, the clock bootstrap.
#pragma once
#include "lzm_store.h"

namespace lzm
{
class World
{
public:
    World(Store& store, std::optional<uint64_t> world_id, std::optional<uint64_t> seed, double initial_ms, double scale);

    Store& store;
    uint64_t world_id = 0, seed = 0;

    double now();
    int64_t real_ms();
    json sample();
    json sample_in(Db& tx);
    json bootstrap_snapshot(bool engine);
    json set_state(const std::string& actor, const std::string& command_id, const json& name, const json& version, const json& state);
    json set_scale(const std::string& actor, const std::string& command_id, const json& value);
    // An administrator moves the calendar forward: every location takes the
    // new time at once; never backwards (calendar schedules would replay).
    json advance(const std::string& actor, const std::string& command_id, const json& game_ms);
    json claim_location(const std::string& actor, const std::string& command_id, const json& location, const json& capacity, const json& ttl_ms);
    json renew_location(const std::string& actor, const std::string& command_id, const json& location, const json& fence, const json& ttl_ms);
    json require_location(Db& tx, const std::string& actor, const std::string& location, int64_t fence);
    double scale() const { return scale_; }

    // world.mutation(): one world instant, due events settled first.
    Store::Apply mutation(Store::Apply apply);

    using Handler = std::function<std::pair<json, bool>(Db&, const json& event)>;
    std::map<std::string, Handler> scheduler_handlers;
    std::function<void(Db&, double cutoff)> mutation_drain;
    using RenewHook = std::function<void(Db&, const std::string& actor, const std::string& location, int64_t fence)>;
    std::map<std::string, RenewHook> lease_renew_hooks;

private:
    double anchor_ms_ = 0, scale_ = 10;
    int64_t anchor_ns_ = 0, last_ns_ = 0, last_wall_ms_ = 0;
    std::optional<double> mutation_cut_;
};
} // namespace lzm
