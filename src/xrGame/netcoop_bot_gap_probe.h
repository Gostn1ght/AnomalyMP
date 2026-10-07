#pragma once

#include <atomic>
#include <cstdint>

namespace netcoop
{
// One producer (a connection's delivery thread), one reporting consumer.
// Unsigned millisecond subtraction also covers the clock wrapping. The caller
// must keep consecutive observations less than one complete clock period apart.
class BotGapProbe
{
    std::uint32_t previous_ = 0;
    bool seen_ = false;
    std::atomic<std::uint32_t> maximum_{0};
public:
    void observe(std::uint32_t now) noexcept
    {
        if (seen_)
        {
            const auto gap = now - previous_;
            auto maximum = maximum_.load(std::memory_order_relaxed);
            while (maximum < gap && !maximum_.compare_exchange_weak(maximum, gap,
                std::memory_order_relaxed, std::memory_order_relaxed)) {}
        }
        previous_ = now;
        seen_ = true;
    }

    std::uint32_t take_maximum() noexcept
    {
        return maximum_.exchange(0, std::memory_order_relaxed);
    }
};
}
