#pragma once

#include "netcoop_world_clock.h"
#include "netcoop_world_authority.h"
#include <chrono>
#include <mutex>

namespace netcoop_world
{
// ALife may read on its worker thread while the server exports on the main
// thread. Sample monotonic time inside the same lock as the clock operation.
class ALifeWorldClock
{
public:
    ALifeWorldClock(WorldIdentity identity, std::uint64_t game_ms, double scale,
        std::uint64_t revision = 1)
        : service_(WorldClock(identity.world_id, identity.epoch, double(game_ms), scale, mono_ms()),
            identity.seed, revision) {}

    static void validate_checkpoint(const WorldStateSnapshot& checkpoint, const WorldIdentity& owner)
    {
        if (checkpoint.schema != 1 || !checkpoint.state_revision || !valid(checkpoint.clock) ||
            checkpoint.clock.world_id != owner.world_id || checkpoint.world_seed != owner.seed ||
            checkpoint.clock.authority_epoch >= owner.epoch)
            throw std::invalid_argument("snapshot identity/fence mismatch; recovery required");
    }

    std::uint64_t now() const
    {
        std::lock_guard<std::mutex> guard(mutex_);
        return static_cast<std::uint64_t>(service_.now(mono_ms()));
    }
    float scale() const
    {
        std::lock_guard<std::mutex> guard(mutex_);
        return static_cast<float>(service_.scale());
    }
    void set_scale(float scale)
    {
        std::lock_guard<std::mutex> guard(mutex_);
        service_.set_scale(scale, mono_ms());
    }
    WorldStateSnapshot checkpoint()
    {
        std::lock_guard<std::mutex> guard(mutex_);
        return service_.snapshot(mono_ms());
    }
private:
    static std::uint64_t mono_ms()
    {
        return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
    }
    mutable std::mutex mutex_;
    LocalWorldService service_;
};
} // namespace netcoop_world
