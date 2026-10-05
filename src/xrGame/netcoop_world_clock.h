#pragma once

// W2 foundation. Transport, durable epoch allocation and ALife adoption belong
// to adapters. All methods are confined to one simulation thread. Neither a
// sender's monotonic timestamp nor wall time is used by a receiving location.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace netcoop_world
{
constexpr std::uint32_t clock_schema = 1;
constexpr double max_world_ms = 9007199254740991.0;
constexpr double max_time_scale = 1000.0;

struct ClockSample
{
    std::uint32_t schema = clock_schema;
    std::uint64_t world_id = 0;
    std::uint64_t authority_epoch = 0; // durable fencing generation, not uptime
    std::uint64_t sequence = 0; // strictly increasing within that generation
    double world_ms = 0;
    double time_scale = 1;
};

inline bool valid(const ClockSample& sample)
{
    return sample.schema == clock_schema && sample.world_id != 0 &&
        sample.authority_epoch != 0 && sample.sequence != 0 &&
        std::isfinite(sample.world_ms) && sample.world_ms >= 0 &&
        sample.world_ms <= max_world_ms && std::isfinite(sample.time_scale) &&
        sample.time_scale >= 0 && sample.time_scale <= max_time_scale;
}

// A checkpoint deliberately contains no process-local monotonic timestamp.
// Restore defaults to frozen offline time; advancing downtime is an explicit
// storage-adapter policy requiring a validated UTC interval and event catch-up.
class WorldClock
{
public:
    WorldClock(std::uint64_t world, std::uint64_t epoch, double world_ms,
        double scale, std::uint64_t mono_ms)
        : state_{clock_schema, world, epoch, 1, world_ms, scale}, mono_(mono_ms), last_read_(mono_ms)
    {
        if (!valid(state_)) throw std::invalid_argument("invalid world clock");
    }

    static WorldClock restore(const ClockSample& checkpoint,
        std::uint64_t new_epoch, std::uint64_t mono_ms)
    {
        if (!valid(checkpoint) || new_epoch <= checkpoint.authority_epoch)
            throw std::invalid_argument("clock restore requires a newer durable epoch");
        return WorldClock(checkpoint.world_id, new_epoch, checkpoint.world_ms,
            checkpoint.time_scale, mono_ms);
    }

    double now(std::uint64_t mono_ms) const
    {
        if (mono_ms < last_read_) throw std::invalid_argument("monotonic clock went backwards");
        const double result = state_.world_ms + double(mono_ms - mono_) * state_.time_scale;
        if (!std::isfinite(result) || result > max_world_ms)
            throw std::overflow_error("world clock exhausted");
        last_read_ = mono_ms;
        return result;
    }

    void set_scale(double scale, std::uint64_t mono_ms)
    {
        if (!std::isfinite(scale) || scale < 0 || scale > max_time_scale)
            throw std::invalid_argument("invalid time scale");
        rebase(mono_ms); // continuity at the exact scale-change boundary
        state_.time_scale = scale;
    }

    ClockSample publish(std::uint64_t mono_ms)
    {
        if (state_.sequence == UINT64_MAX) throw std::overflow_error("clock sequence exhausted");
        rebase(mono_ms);
        ++state_.sequence;
        return state_;
    }

    double scale() const { return state_.time_scale; }

private:
    void rebase(std::uint64_t mono_ms)
    {
        state_.world_ms = now(mono_ms);
        mono_ = mono_ms;
    }
    ClockSample state_;
    std::uint64_t mono_;
    mutable std::uint64_t last_read_;
};

enum class SyncResult { applied, stale, invalid, epoch_changed, resync_required };

struct FollowerConfig
{
    std::uint64_t max_rtt_ms = 1000;
    std::uint64_t max_holdover_ms = 30000;
    double max_error_ms = 2000; // game milliseconds, not real milliseconds
    double slew_fraction = 0.05; // correction bounded to +/-5% of game rate
};

class LocationClock
{
public:
    explicit LocationClock(std::uint64_t world, FollowerConfig config = {})
        : world_(world), config_(config)
    {
        if (!world || !config.max_rtt_ms || !config.max_holdover_ms ||
            !std::isfinite(config.max_error_ms) || config.max_error_ms <= 0 ||
            !std::isfinite(config.slew_fraction) || config.slew_fraction <= 0 ||
            config.slew_fraction >= 1)
            throw std::invalid_argument("invalid follower configuration");
    }

    // Bootstrap is allowed only behind the adapter's world-recovery barrier:
    // stop mutations, load WorldState, catch up events, then resume simulation.
    SyncResult bootstrap(const ClockSample& sample, std::uint64_t sent_ms,
        std::uint64_t received_ms)
    {
        double target = 0;
        if (!target_time(sample, sent_ms, received_ms, target)) return SyncResult::invalid;
        if (sample.authority_epoch < epoch_ || (sample.authority_epoch == epoch_ &&
            sample.sequence < sequence_)) return SyncResult::stale;
        epoch_ = sample.authority_epoch;
        sequence_ = sample.sequence;
        world_ms_ = target;
        scale_ = sample.time_scale;
        remaining_ = 0;
        last_mono_ = last_sync_ = received_ms;
        initialized_ = true;
        recovery_ = false;
        return SyncResult::applied;
    }

    SyncResult observe(const ClockSample& sample, std::uint64_t sent_ms,
        std::uint64_t received_ms)
    {
        double target = 0;
        if (!target_time(sample, sent_ms, received_ms, target)) return SyncResult::invalid;
        if (!initialized_) return SyncResult::resync_required;
        if (received_ms < last_mono_) return SyncResult::invalid;
        if (sample.authority_epoch < epoch_ || (sample.authority_epoch == epoch_ &&
            sample.sequence <= sequence_)) return SyncResult::stale;
        if (sample.authority_epoch > epoch_)
        {
            epoch_ = sample.authority_epoch;
            sequence_ = sample.sequence;
            recovery_ = true; // fence the old authority immediately
            return SyncResult::epoch_changed;
        }
        if (recovery_) return SyncResult::resync_required;
        advance(received_ms);
        sequence_ = sample.sequence;
        const double error = target - world_ms_;
        // A stopped world must remain stopped. A differing paused snapshot is
        // adopted through recovery, never by running a hidden correction tick.
        if (std::abs(error) > config_.max_error_ms ||
            (sample.time_scale == 0 && std::abs(error) > 0.001))
        {
            recovery_ = true;
            return SyncResult::resync_required;
        }
        remaining_ = error;
        scale_ = sample.time_scale;
        last_sync_ = received_ms;
        return SyncResult::applied;
    }

    bool ready(std::uint64_t mono_ms) const
    {
        return initialized_ && !recovery_ && mono_ms >= last_mono_ &&
            mono_ms - last_sync_ <= config_.max_holdover_ms;
    }

    // Presentation may inspect the estimate in holdover. Gameplay mutations
    // must additionally test ready(); losing the service does not grant authority.
    double estimate(std::uint64_t mono_ms)
    {
        if (!initialized_) throw std::logic_error("clock not bootstrapped");
        advance(mono_ms);
        return world_ms_;
    }

private:
    bool target_time(const ClockSample& sample, std::uint64_t sent_ms,
        std::uint64_t received_ms, double& target) const
    {
        if (!valid(sample) || sample.world_id != world_ || received_ms < sent_ms ||
            received_ms - sent_ms > config_.max_rtt_ms) return false;
        // Approximation: response was sampled just before sending. No comparison
        // of clocks on different hosts; asymmetric delay remains measurement error.
        target = sample.world_ms + double(received_ms - sent_ms) * 0.5 * sample.time_scale;
        return std::isfinite(target) && target <= max_world_ms;
    }

    void advance(std::uint64_t mono_ms)
    {
        if (mono_ms < last_mono_) throw std::invalid_argument("monotonic clock went backwards");
        const double dt = double(mono_ms - last_mono_);
        const double bound = dt * scale_ * config_.slew_fraction;
        const double correction = (std::max)(-bound, (std::min)(bound, remaining_));
        const double next = world_ms_ + dt * scale_ + correction;
        if (!std::isfinite(next) || next > max_world_ms)
            throw std::overflow_error("location clock exhausted");
        world_ms_ = next;
        remaining_ -= correction;
        last_mono_ = mono_ms;
    }
    std::uint64_t world_;
    FollowerConfig config_;
    std::uint64_t epoch_ = 0, sequence_ = 0, last_mono_ = 0, last_sync_ = 0;
    double world_ms_ = 0, scale_ = 1, remaining_ = 0;
    bool initialized_ = false, recovery_ = false;
};

struct WorldStateSnapshot
{
    std::uint32_t schema = 1;
    std::uint64_t world_seed;
    std::uint64_t state_revision;
    ClockSample clock;
    // Weather/emission/territory are added by versioned W3+ contracts.
};

class IWorldService
{
public:
    virtual ~IWorldService() = default;
    virtual WorldStateSnapshot snapshot(std::uint64_t local_mono_ms) = 0;
};

// In-process implementation for the first adapter. Does not pretend to own an
// ALife world or a database. Admission requires a durable world id/seed/epoch.
class LocalWorldService final : public IWorldService
{
public:
    LocalWorldService(WorldClock clock, std::uint64_t seed, std::uint64_t revision)
        : clock_(clock), seed_(seed), revision_(revision)
    {
        if (!revision) throw std::invalid_argument("world revision must be nonzero");
    }
    WorldStateSnapshot snapshot(std::uint64_t mono_ms) override
    {
        return {1, seed_, revision_, clock_.publish(mono_ms)};
    }
    double now(std::uint64_t mono_ms) const { return clock_.now(mono_ms); }
    double scale() const { return clock_.scale(); }
    void set_scale(double scale, std::uint64_t mono_ms)
    {
        if (revision_ == UINT64_MAX) throw std::overflow_error("world revision exhausted");
        clock_.set_scale(scale, mono_ms);
        ++revision_;
    }
private:
    WorldClock clock_;
    std::uint64_t seed_, revision_;
};
} // namespace netcoop_world
