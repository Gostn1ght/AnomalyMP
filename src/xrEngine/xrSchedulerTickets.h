#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <type_traits>
#include <vector>

namespace xr_scheduler
{
// Opaque tickets validate queue entries without hashing/dereferencing the object.
// Only the scheduler thread accesses this pool. Cancellation never allocates.
template<class Object, class Generation = std::uint32_t>
class TicketPool
{
    static_assert(std::is_integral<Generation>::value && std::is_unsigned<Generation>::value &&
        !std::is_same<Generation, bool>::value && sizeof(Generation) <= 4,
        "Ticket generation must be an unsigned integer of at most 32 bits");
    static constexpr std::uint32_t none = (std::numeric_limits<std::uint32_t>::max)();
    struct Slot
    {
        Object* object = nullptr;
        Generation generation = 0;
        bool realtime = false;
        std::uint32_t next_free = none;
    };
    std::vector<Slot> slots;
    std::uint32_t free_head = none;

    const Slot* lookup(std::uint64_t ticket) const noexcept
    {
        const auto index = static_cast<std::uint32_t>(ticket);
        if (index >= slots.size()) return nullptr;
        const Slot& slot = slots[index];
        return slot.object && (ticket >> 32) == slot.generation ? &slot : nullptr;
    }

public:
    // The owning scheduler is not transferable while queue entries exist.
    TicketPool() = default;
    TicketPool(const TicketPool&) = delete;
    TicketPool& operator=(const TicketPool&) = delete;

    std::uint64_t activate(Object* object, bool realtime)
    {
        if (!object) throw std::invalid_argument("Null scheduled object");
        std::uint32_t index = free_head;
        if (index == none)
        {
            if (slots.size() >= none) throw std::length_error("Scheduler ticket capacity");
            index = static_cast<std::uint32_t>(slots.size());
            slots.emplace_back();
        }
        else free_head = slots[index].next_free;
        Slot& slot = slots[index];
        ++slot.generation;
        slot.object = object;
        slot.realtime = realtime;
        slot.next_free = none;
        return (static_cast<std::uint64_t>(slot.generation) << 32) | index;
    }

    bool active(std::uint64_t ticket, const Object* object) const noexcept
    {
        const Slot* slot = lookup(ticket);
        return slot && slot->object == object;
    }

    bool realtime(std::uint64_t ticket) const noexcept
    {
        const Slot* slot = lookup(ticket);
        return slot && slot->realtime;
    }

    bool cancel(std::uint64_t ticket) noexcept
    {
        if (!lookup(ticket)) return false;
        const auto index = static_cast<std::uint32_t>(ticket);
        Slot& slot = slots[index];
        slot.object = nullptr;
        // Permanently retire an exhausted slot; generation wrap cannot revive
        // an old heap entry even if an object occupies the same address again.
        if (slot.generation != (std::numeric_limits<Generation>::max)())
        {
            slot.next_free = free_head;
            free_head = index;
        }
        return true;
    }

    void clear() noexcept { slots.clear(); free_head = none; }
    std::size_t slot_count() const noexcept { return slots.size(); }
};
}
