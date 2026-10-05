#pragma once

// Logical simulation cells. Querying relevance never destroys an entity or
// assigns its simulation owner. Runtime adapters must supply their own IDs.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace netcoop_world
{
struct SpatialId
{
    std::uint64_t high = 0, low = 0;
    bool operator==(const SpatialId& other) const { return high == other.high && low == other.low; }
    bool operator<(const SpatialId& other) const { return high < other.high || (high == other.high && low < other.low); }
};
struct SpatialIdHash
{
    std::size_t operator()(const SpatialId& id) const
    { return std::size_t(id.high ^ (id.low + 0x9e3779b97f4a7c15ULL + (id.high << 6) + (id.high >> 2))); }
};
struct SpatialPoint { double x = 0, y = 0, z = 0; };
struct CellId
{
    std::uint32_t location = 0;
    std::int32_t x = 0, z = 0;
    bool operator==(const CellId& other) const { return location == other.location && x == other.x && z == other.z; }
};
struct CellIdHash
{
    std::size_t operator()(const CellId& cell) const
    {
        const auto x = std::uint32_t(cell.x), z = std::uint32_t(cell.z);
        return std::size_t((std::uint64_t(x) << 32) ^ z ^ (std::uint64_t(cell.location) * 0x9e3779b97f4a7c15ULL));
    }
};
struct SpatialQueryStats { std::uint64_t cells = 0, candidates = 0; };

inline bool finite_point(const SpatialPoint& p)
{
    return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z) &&
        std::abs(p.x) <= 1e7 && std::abs(p.y) <= 1e7 && std::abs(p.z) <= 1e7;
}
inline double point_distance_squared(const SpatialPoint& a, const SpatialPoint& b)
{
    const double x = a.x-b.x, y=a.y-b.y, z=a.z-b.z;
    return x*x + y*y + z*z;
}
inline double segment_distance_squared(const SpatialPoint& p, const SpatialPoint& a, const SpatialPoint& b)
{
    const double x=b.x-a.x, y=b.y-a.y, z=b.z-a.z;
    const double length=x*x+y*y+z*z;
    const double t=length > 0 ? (std::max)(0., (std::min)(1., ((p.x-a.x)*x+(p.y-a.y)*y+(p.z-a.z)*z)/length)) : 0;
    return point_distance_squared(p, {a.x+t*x,a.y+t*y,a.z+t*z});
}

class SpatialGrid
{
    struct Record { std::uint32_t location; SpatialPoint point; CellId cell; };
    using Members = std::unordered_set<SpatialId, SpatialIdHash>;
    double size_;
    std::uint64_t max_query_cells_;
    std::unordered_map<SpatialId, Record, SpatialIdHash> records_;
    std::unordered_map<CellId, Members, CellIdHash> cells_;
public:
    explicit SpatialGrid(double cell_size = 100, std::uint64_t max_query_cells = 65536)
        : size_(cell_size), max_query_cells_(max_query_cells)
    {
        if (!std::isfinite(size_) || size_ < 1 || size_ > 10000 || !max_query_cells_)
            throw std::invalid_argument("invalid spatial grid configuration");
    }
    CellId cell(std::uint32_t location, const SpatialPoint& point) const
    {
        if (!location || !finite_point(point)) throw std::invalid_argument("invalid spatial position");
        return {location, std::int32_t(std::floor(point.x / size_)), std::int32_t(std::floor(point.z / size_))};
    }
    std::size_t size() const { return records_.size(); }
    std::size_t cell_count() const { return cells_.size(); }
    void clear() { records_.clear(); cells_.clear(); }
    void upsert(SpatialId id, std::uint32_t location, SpatialPoint point)
    {
        if (!id.high && !id.low) throw std::invalid_argument("zero spatial entity ID");
        const auto target=cell(location,point); // validate before changing old membership
        auto found=records_.find(id);
        if (found != records_.end() && found->second.cell == target)
        { found->second.point=point; return; }
        cells_[target].insert(id);
        if (found != records_.end())
        {
            remove_member(found->second.cell,id);
            found->second={location,point,target};
        }
        else records_.emplace(id,Record{location,point,target});
    }
    bool erase(SpatialId id)
    {
        const auto found=records_.find(id);
        if (found == records_.end()) return false;
        remove_member(found->second.cell,id);
        records_.erase(found);
        return true;
    }
    // Sphere query: 2D cells are conservative; the final test includes height.
    std::vector<SpatialId> query(std::uint32_t location, SpatialPoint center,
        double radius, SpatialQueryStats* stats = nullptr) const
    { return swept(location,center,center,radius,stats); }

    // A swept sphere is a capsule, not two endpoint spheres. High-speed
    // movement cannot skip the cells lying between current/predicted positions.
    std::vector<SpatialId> swept(std::uint32_t location, SpatialPoint start,
        SpatialPoint end, double radius, SpatialQueryStats* stats = nullptr) const
    {
        if (!location || !finite_point(start) || !finite_point(end) ||
            !std::isfinite(radius) || radius < 0 || radius > 1e7)
            throw std::invalid_argument("invalid spatial query");
        const double min_x=(std::min)(start.x,end.x)-radius, max_x=(std::max)(start.x,end.x)+radius;
        const double min_z=(std::min)(start.z,end.z)-radius, max_z=(std::max)(start.z,end.z)+radius;
        const auto x0=std::int64_t(std::floor(min_x/size_)), x1=std::int64_t(std::floor(max_x/size_));
        const auto z0=std::int64_t(std::floor(min_z/size_)), z1=std::int64_t(std::floor(max_z/size_));
        const auto width=std::uint64_t(x1-x0+1), height=std::uint64_t(z1-z0+1);
        if (width > max_query_cells_ || height > max_query_cells_ / width)
            throw std::length_error("spatial query exceeds cell budget");
        std::vector<SpatialId> result;
        for (auto x=x0; x<=x1; ++x)
            for (auto z=z0; z<=z1; ++z)
            {
                if (stats) ++stats->cells;
                const auto found=cells_.find({location,std::int32_t(x),std::int32_t(z)});
                if (found == cells_.end()) continue;
                for (const auto id : found->second)
                {
                    if (stats) ++stats->candidates;
                    const auto record=records_.find(id);
                    if (record != records_.end() && segment_distance_squared(record->second.point,start,end) <= radius*radius)
                        result.push_back(id);
                }
            }
        std::sort(result.begin(),result.end()); // deterministic output, independent of hash-map order
        return result;
    }
    double distance_to_cell(std::uint32_t location, SpatialPoint point, CellId target) const
    {
        if (location != target.location || !finite_point(point)) throw std::invalid_argument("foreign cell bounds");
        const double dx=(std::max)(0.,(std::max)(target.x*size_-point.x,point.x-(target.x+1.)*size_));
        const double dz=(std::max)(0.,(std::max)(target.z*size_-point.z,point.z-(target.z+1.)*size_));
        return std::sqrt(dx*dx+dz*dz);
    }
private:
    void remove_member(CellId cell_id, SpatialId id)
    {
        auto found=cells_.find(cell_id);
        if (found == cells_.end()) return;
        found->second.erase(id);
        if (found->second.empty()) cells_.erase(found);
    }
};

struct PlayerInterest
{
    SpatialId player;
    std::uint32_t location = 0;
    SpatialPoint position, velocity;
};
struct InterestConfig
{
    double full_radius=300, observable_radius=1000, prewarm_radius=1400;
    double prediction_seconds=3, max_speed=30;
};
struct PlayerRelevantSet
{
    SpatialId player;
    std::vector<SpatialId> full, visible, prewarm;
};
inline std::vector<PlayerRelevantSet> interest_sets(const SpatialGrid& grid,
    const std::vector<PlayerInterest>& players, const InterestConfig& config = {})
{
    if (!std::isfinite(config.full_radius) || !std::isfinite(config.observable_radius) ||
        !std::isfinite(config.prewarm_radius) || !std::isfinite(config.prediction_seconds) ||
        !std::isfinite(config.max_speed) || config.full_radius < 0 ||
        config.observable_radius < config.full_radius || config.prewarm_radius <= config.observable_radius ||
        config.prediction_seconds < 0 || config.prediction_seconds > 60 || config.max_speed <= 0 || config.max_speed > 1000)
        throw std::invalid_argument("invalid interest configuration");
    std::vector<PlayerRelevantSet> result;
    for (const auto& player : players)
    {
        if ((!player.player.high && !player.player.low) || !finite_point(player.velocity))
            throw std::invalid_argument("invalid player interest");
        const auto speed=std::sqrt(point_distance_squared(player.velocity,{}));
        const auto ratio=speed > config.max_speed ? config.max_speed/speed : 1.;
        const auto t=config.prediction_seconds*ratio;
        const SpatialPoint predicted{player.position.x+player.velocity.x*t,
            player.position.y+player.velocity.y*t,player.position.z+player.velocity.z*t};
        result.push_back({player.player,
            grid.query(player.location,player.position,config.full_radius),
            grid.query(player.location,player.position,config.observable_radius),
            grid.swept(player.location,player.position,predicted,config.prewarm_radius)});
    }
    return result;
}
} // namespace netcoop_world
