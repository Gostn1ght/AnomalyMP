#pragma once

// Scheduling policy only. LOD changes neither delete persistent entities nor
// grant ownership. Engine adapters must drive RepresentationGate with durable
// captures/ownership ACKs before altering AI, physics or replication.
#include "netcoop_spatial_grid.h"
#include <map>

namespace netcoop_world
{
enum class SimulationLod : unsigned { Dormant, Abstract, Reduced, Full };
inline bool stronger(SimulationLod a, SimulationLod b)
{ return unsigned(a) > unsigned(b); }
struct CellOrder
{
    bool operator()(const CellId& a, const CellId& b) const
    {
        if (a.location != b.location) return a.location < b.location;
        if (a.x != b.x) return a.x < b.x;
        return a.z < b.z;
    }
};
struct LodDemand { CellId cell; SimulationLod minimum = SimulationLod::Dormant; };
struct LodChange { CellId cell; SimulationLod before, after; };
struct LodConfig
{
    double full_radius = 300, reduced_radius = 700, prewarm_radius = 1400;
    double prediction_seconds = 3, max_speed = 30;
    std::uint64_t minimum_dwell_ms = 5000, exit_delay_ms = 2000;
    std::size_t maximum_cells = 1000000;
};

class SimulationLodPlanner
{
    struct State
    {
        SimulationLod current = SimulationLod::Dormant, pending = SimulationLod::Dormant;
        std::uint64_t changed = 0, pending_since = 0;
    };
    LodConfig config_;
    std::map<CellId, State, CellOrder> cells_;
    std::uint64_t last_ms_ = 0;
public:
    explicit SimulationLodPlanner(LodConfig config = {}) : config_(config)
    {
        // Use the same checked prediction policy as spatial replication, but
        // maintain separate simulation radii and a union of observer demands.
        InterestConfig check{config.full_radius,config.reduced_radius,config.prewarm_radius,
            config.prediction_seconds,config.max_speed};
        interest_sets(SpatialGrid(),{},check);
        if (!config_.maximum_cells || config_.minimum_dwell_ms > 3600000 || config_.exit_delay_ms > 3600000)
            throw std::invalid_argument("invalid LOD hysteresis/budget");
    }

    // For occupied cells: distance to cell bounds avoids holes at corners.
    // A swept conservative bound includes cells between diagonal positions.
    // PVS/zoom/critical-event hints can raise minimum via explicit demands.
    LodDemand observer_demand(const SpatialGrid& grid, CellId cell,
        const std::vector<PlayerInterest>& observers) const
    {
        SimulationLod wanted = SimulationLod::Dormant;
        for (const auto& observer : observers)
        {
            if (!observer.location || (!observer.player.high && !observer.player.low) ||
                !finite_point(observer.position) || !finite_point(observer.velocity))
                throw std::invalid_argument("invalid simulation observer");
            if (observer.location != cell.location) continue;
            const double distance = grid.distance_to_cell(cell.location,observer.position,cell);
            if (distance <= config_.full_radius) wanted = SimulationLod::Full;
            else if (distance <= config_.reduced_radius && stronger(SimulationLod::Reduced,wanted))
                wanted = SimulationLod::Reduced;
            const double speed = std::sqrt(point_distance_squared(observer.velocity,{}));
            const double predicted_length = (std::min)(speed,config_.max_speed)*config_.prediction_seconds;
            // Conservative swept-volume admission: never miss an intermediate
            // cell; overshoot candidates may cost work, never cause popping.
            if (distance <= config_.prewarm_radius + predicted_length && stronger(SimulationLod::Reduced,wanted))
                wanted = SimulationLod::Reduced;
        }
        return {cell,wanted};
    }

    std::vector<LodChange> update(const std::vector<LodDemand>& demands, std::uint64_t now_ms)
    {
        if (now_ms < last_ms_) throw std::invalid_argument("LOD monotonic time regressed");
        std::map<CellId,SimulationLod,CellOrder> wanted;
        for (const auto& demand : demands)
        {
            if (!demand.cell.location || unsigned(demand.minimum) > unsigned(SimulationLod::Full))
                throw std::invalid_argument("invalid cell demand");
            auto inserted = wanted.emplace(demand.cell,demand.minimum);
            if (!inserted.second && stronger(demand.minimum,inserted.first->second))
                inserted.first->second = demand.minimum;
        }
        std::size_t added = 0;
        for (const auto& pair : wanted) if (cells_.find(pair.first) == cells_.end()) ++added;
        if (added > config_.maximum_cells || cells_.size() > config_.maximum_cells-added)
            throw std::length_error("LOD cell budget exhausted");
        // Validate complete input before modifying policy state.
        last_ms_ = now_ms;
        for (const auto& pair : wanted) cells_.emplace(pair.first,State{});
        std::vector<LodChange> changes;
        for (auto& pair : cells_)
        {
            State& state = pair.second;
            const auto found = wanted.find(pair.first);
            const auto target = found == wanted.end() ? SimulationLod::Dormant : found->second;
            if (stronger(target,state.current))
            {
                changes.push_back({pair.first,state.current,target});
                state.current = state.pending = target;
                state.changed = state.pending_since = now_ms;
            }
            else if (target == state.current)
            { state.pending = target; state.pending_since = now_ms; }
            else
            {
                if (state.pending != target) { state.pending = target; state.pending_since = now_ms; }
                if (now_ms-state.pending_since >= config_.exit_delay_ms &&
                    now_ms-state.changed >= config_.minimum_dwell_ms)
                {
                    changes.push_back({pair.first,state.current,target});
                    state.current = target; state.changed = now_ms;
                }
            }
        }
        return changes;
    }
    SimulationLod level(CellId cell) const
    { const auto found=cells_.find(cell);return found == cells_.end() ? SimulationLod::Dormant : found->second.current; }
    // Only discard policy entries after they became dormant. Persistent
    // world state belongs to the registry and is never removed by this method.
    std::size_t prune_dormant()
    {
        std::size_t removed = 0;
        for (auto it=cells_.begin();it!=cells_.end();)
            if (it->second.current==SimulationLod::Dormant) { it=cells_.erase(it);++removed; }
            else ++it;
        return removed;
    }
    std::size_t size() const { return cells_.size(); }
};

enum class Representation { Abstract, Hydrating, Runtime, Dehydrating };
struct CaptureTicket
{
    std::uint64_t generation = 0, revision = 0;
    bool operator==(const CaptureTicket& other) const
    { return generation == other.generation && revision == other.revision; }
};
class RepresentationGate
{
    Representation state_ = Representation::Abstract;
    CaptureTicket ticket_;
    bool critical_ = false;
    std::uint64_t revision_;
    CaptureTicket begin(Representation expected, Representation next, std::uint64_t revision)
    {
        if (state_ != expected || revision != revision_ || !revision)
            throw std::logic_error("representation/version changed");
        if (ticket_.generation == (std::numeric_limits<std::uint64_t>::max)())
            throw std::overflow_error("representation generation exhausted");
        ticket_ = {ticket_.generation+1,revision};
        state_ = next;
        return ticket_;
    }
    void require(Representation expected, CaptureTicket ticket) const
    {
        if (state_ != expected || !(ticket == ticket_))
            throw std::logic_error("stale representation completion");
    }
public:
    explicit RepresentationGate(std::uint64_t revision = 1) : revision_(revision)
    { if (!revision) throw std::invalid_argument("zero capture revision"); }
    Representation state() const { return state_; }
    std::uint64_t revision() const { return revision_; }
    bool replication_ready() const { return state_ == Representation::Runtime; }
    // Dehydrating runtime is frozen; neither simulation may mutate until ACK.
    bool runtime_writable() const { return state_ == Representation::Runtime; }
    bool abstract_writable() const { return state_ == Representation::Abstract; }
    void critical(bool value) { critical_ = value; }
    CaptureTicket begin_hydration(std::uint64_t revision)
    { return begin(Representation::Abstract,Representation::Hydrating,revision); }
    void finish_hydration(CaptureTicket ticket, std::uint64_t next_revision,
        bool ownership_ack, bool complete_restore, bool safe_placement, bool reduced_ai_started)
    {
        require(Representation::Hydrating,ticket);
        if (next_revision <= revision_ || !ownership_ack || !complete_restore || !safe_placement || !reduced_ai_started)
            throw std::logic_error("hydration prerequisites incomplete");
        revision_ = next_revision;state_ = Representation::Runtime;
    }
    // Failed hydration stays hidden until the backend releases its claim.
    void cancel_hydration(CaptureTicket ticket, std::uint64_t next_revision, bool claim_released)
    {
        require(Representation::Hydrating,ticket);
        if (!claim_released || next_revision <= revision_) throw std::logic_error("hydration release incomplete");
        revision_ = next_revision;state_ = Representation::Abstract;
    }
    CaptureTicket begin_dehydration(std::uint64_t revision)
    {
        if (critical_) throw std::logic_error("critical runtime cannot dehydrate");
        return begin(Representation::Runtime,Representation::Dehydrating,revision);
    }
    void finish_dehydration(CaptureTicket ticket, std::uint64_t next_revision,
        bool full_capture_committed, bool runtime_removed)
    {
        require(Representation::Dehydrating,ticket);
        if (!full_capture_committed || !runtime_removed || next_revision <= revision_)
            throw std::logic_error("dehydration prerequisites incomplete");
        revision_ = next_revision;state_ = Representation::Abstract;
    }
    void cancel_dehydration(CaptureTicket ticket, bool backend_did_not_commit)
    {
        require(Representation::Dehydrating,ticket);
        if (!backend_did_not_commit) throw std::logic_error("committed dehydration cannot resume old runtime");
        state_ = Representation::Runtime;
    }
};
} // namespace netcoop_world
