#pragma once

#include <cstddef>
#include <cstdint>

namespace netcoop_world
{
struct ReplicationRecord
{
    std::uint16_t id;
    bool full_rate; // players, creatures and their displayed equipment
    float x,y,z;
};
struct ReplicationSelection
{
    const std::uint32_t* indices=nullptr;
    std::size_t count=0;
    std::uint64_t spatial_candidates=0;
    bool valid=false;
};
// Single simulation thread. Indices address the current serialized frame and
// expire on prepare/select. No durable identity, ownership or AOI admission.
// Selection includes every full_rate record globally and the observer's object.
// The remaining world records form a superset of the 1/2/4/16-tick cadence.
// Apply the native distance predicate after selection; full-rate characters
// remain included even beyond the near sphere under overload.
class ReplicationIndex
{
    struct State;
    State* state_=nullptr;
public:
    ReplicationIndex() noexcept=default;
    ~ReplicationIndex();
    ReplicationIndex(const ReplicationIndex&)=delete;
    ReplicationIndex& operator=(const ReplicationIndex&)=delete;
    bool prepare(const ReplicationRecord* records,std::size_t count) noexcept;
    ReplicationSelection select(std::uint16_t observer,float x,float y,float z,std::uint32_t tick) noexcept;
};
}
