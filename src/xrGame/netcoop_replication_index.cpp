// Exception-enabled implementation without engine/PCH headers. Invalid frames
// or failed allocations return a legacy fallback through the noexcept boundary.
#include "netcoop_replication_index.h"
#include "netcoop_spatial_grid.h"
#include <array>
#include <map>
#include <memory>

namespace netcoop_world
{
struct ReplicationIndex::State
{
    SpatialGrid grid{100};
    std::array<std::vector<std::uint32_t>,16> buckets;
    std::vector<std::uint32_t> players,selected;
    std::map<std::uint16_t,std::uint32_t> offsets;
    bool ready=false;
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
        state.grid.clear();state.players.clear();state.selected.clear();state.offsets.clear();
        for (auto& bucket:state.buckets) bucket.clear();
        for (std::size_t i=0;i<count;++i)
        {
            const auto& record=records[i];
            const auto offset=std::uint32_t(i);
            if (!state.offsets.emplace(record.id,offset).second) return false;
            state.grid.upsert({0,std::uint64_t(record.id)+1},1,{record.x,record.y,record.z});
            state.buckets[record.id%16].push_back(offset);
            if (record.player) state.players.push_back(offset);
        }
        state.ready=true;
        return true;
    }
    catch (...) {return false;}
}
ReplicationSelection ReplicationIndex::select(std::uint16_t observer,float x,float y,float z,std::uint32_t tick) noexcept
{
    if (!state_ || !state_->ready) return {};
    try
    {
        auto& state=*state_;
        SpatialQueryStats stats;
        // Small conservative margin covers legacy float sqrt rounding at 300m.
        const auto near=state.grid.query(1,{x,y,z},300.05,&stats);
        state.selected=state.buckets[(16-tick%16)%16];
        state.selected.insert(state.selected.end(),state.players.begin(),state.players.end());
        for (const auto id:near)
            state.selected.push_back(state.offsets.at(std::uint16_t(id.low-1)));
        const auto own=state.offsets.find(observer);
        if (own!=state.offsets.end()) state.selected.push_back(own->second);
        std::sort(state.selected.begin(),state.selected.end());
        state.selected.erase(std::unique(state.selected.begin(),state.selected.end()),state.selected.end());
        return {state.selected.data(),state.selected.size(),stats.candidates,true};
    }
    catch (...) {return {};}
}
}
