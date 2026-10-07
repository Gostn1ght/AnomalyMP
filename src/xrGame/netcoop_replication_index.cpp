// Exception-enabled implementation without engine/PCH headers. Invalid frames
// or failed allocations return a legacy fallback through the noexcept boundary.
//
// Built for the per-tick cost (chunk stage 1, doc 49): the first version
// rebuilt a hashed SpatialGrid and a std::map every tick and allocated per
// query; with ~1700 objects and 64 players in one spot that made the server
// frame 43-48 ms instead of 21-23 ms with the plain full scan (2026-10-06).
// Now: one sorted array of (cell, offset) per tick, a binary search per row
// of the 300 m window, and per-query marks instead of sets; buffers are kept.
#include "netcoop_replication_index.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <memory>
#include <vector>

namespace netcoop_world
{
namespace
{
const double cell_size = 100.0;
const double near_radius = 300.05; // small margin covers legacy float sqrt rounding at 300 m
const std::uint32_t no_offset = 0xffffffffu;

std::int64_t cell_of(double v) { return std::int64_t(std::floor(v / cell_size)); }
// Row-major key: cells of one x-row with increasing z are contiguous.
std::uint64_t cell_key(std::int64_t ix, std::int64_t iz)
{
    return (std::uint64_t(std::uint32_t(std::int32_t(ix)) ^ 0x80000000u) << 32) |
        std::uint64_t(std::uint32_t(std::int32_t(iz)) ^ 0x80000000u);
}
}

struct ReplicationIndex::State
{
    struct Cell { std::uint64_t key; std::uint32_t offset; };
    std::vector<Cell> cells;                      // sorted by key
    std::vector<float> xs, ys, zs;                // by offset
    std::array<std::vector<std::uint32_t>,16> buckets;
    std::vector<std::uint32_t> full_rate, selected, marks;
    std::vector<std::uint32_t> offsets;           // id -> offset (65536), no_offset if absent
    std::vector<std::uint16_t> used_ids;          // ids set in offsets this frame
    std::uint32_t stamp = 0;
    bool ready = false;
};

ReplicationIndex::~ReplicationIndex() {delete state_;}

bool ReplicationIndex::prepare(const ReplicationRecord* records,std::size_t count) noexcept
{
    if (state_) state_->ready=false;
    if (count>65536 || (count && !records)) return false;
    try
    {
        if (!state_) state_=std::make_unique<State>().release();
        auto& state=*state_;
        if (state.offsets.size()!=65536) state.offsets.assign(65536,no_offset);
        for (const auto id:state.used_ids) state.offsets[id]=no_offset;
        state.used_ids.clear();
        state.cells.clear();state.full_rate.clear();state.selected.clear();
        state.xs.resize(count);state.ys.resize(count);state.zs.resize(count);
        state.marks.assign(count,0);state.stamp=0;
        for (auto& bucket:state.buckets) bucket.clear();
        for (std::size_t i=0;i<count;++i)
        {
            const auto& record=records[i];
            const auto offset=std::uint32_t(i);
            if (!std::isfinite(record.x) || !std::isfinite(record.y) || !std::isfinite(record.z)) return false;
            if (state.offsets[record.id]!=no_offset) return false; // duplicate id in one frame
            state.offsets[record.id]=offset;
            state.used_ids.push_back(record.id);
            state.xs[i]=record.x;state.ys[i]=record.y;state.zs[i]=record.z;
            state.cells.push_back({cell_key(cell_of(record.x),cell_of(record.z)),offset});
            state.buckets[record.id%16].push_back(offset);
            if (record.full_rate) state.full_rate.push_back(offset);
        }
        std::sort(state.cells.begin(),state.cells.end(),
            [](const State::Cell& a,const State::Cell& b){return a.key<b.key;});
        state.ready=true;
        return true;
    }
    catch (...) {return false;}
}

ReplicationSelection ReplicationIndex::select(std::uint16_t observer,float x,float y,float z,std::uint32_t tick) noexcept
{
    if (!state_ || !state_->ready) return {};
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) return {};
    try
    {
        auto& state=*state_;
        if (++state.stamp==0) {std::fill(state.marks.begin(),state.marks.end(),0u);state.stamp=1;}
        const std::uint32_t stamp=state.stamp;
        state.selected.clear();
        auto take=[&](std::uint32_t offset)
        {
            if (state.marks[offset]==stamp) return;
            state.marks[offset]=stamp;
            state.selected.push_back(offset);
        };
        for (const auto offset:state.buckets[(16-tick%16)%16]) take(offset);
        for (const auto offset:state.full_rate) take(offset);
        const std::uint32_t own=state.offsets[observer];
        if (own!=no_offset) take(own);
        // The 300 m sphere (3D test), over the rows of the covering cells.
        std::uint64_t candidates=0;
        const double r2=near_radius*near_radius;
        const std::int64_t x0=cell_of(x-near_radius),x1=cell_of(x+near_radius);
        const std::int64_t z0=cell_of(z-near_radius),z1=cell_of(z+near_radius);
        const auto by_key=[](const State::Cell& c,std::uint64_t key){return c.key<key;};
        for (std::int64_t ix=x0;ix<=x1;++ix)
        {
            const std::uint64_t first=cell_key(ix,z0),last=cell_key(ix,z1);
            for (auto it=std::lower_bound(state.cells.begin(),state.cells.end(),first,by_key);
                 it!=state.cells.end() && it->key<=last;++it)
            {
                ++candidates;
                const double dx=double(state.xs[it->offset])-x,dy=double(state.ys[it->offset])-y,dz=double(state.zs[it->offset])-z;
                if (dx*dx+dy*dy+dz*dz<=r2) take(it->offset);
            }
        }
        std::sort(state.selected.begin(),state.selected.end());
        return {state.selected.data(),state.selected.size(),candidates,true};
    }
    catch (...) {return {};}
}
}
