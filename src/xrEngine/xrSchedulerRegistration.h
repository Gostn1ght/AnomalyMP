#pragma once

#include <cstddef>
#include <unordered_map>
#include <vector>

namespace xr_scheduler
{
// Preserve IX-Ray's earliest-register/earliest-future-unregister pairing,
// without repeatedly searching/erasing the rest of the registration vector.
// Never dereference Object: a paired object may already have been destroyed.
template <class Records>
std::vector<unsigned char> registration_pairs(const Records& records)
{
    struct Future
    {
        std::vector<std::size_t> indices;
        std::size_t next = 0;
    };
    std::unordered_map<const void*, Future> removals;
    for (std::size_t i = 0; i < records.size(); ++i)
        if (!records[i].OP)
            removals[records[i].Object].indices.push_back(i);
    std::vector<unsigned char> skipped(records.size(), 0);
    for (std::size_t i = 0; i < records.size(); ++i)
    {
        if (!records[i].OP)
            continue;
        auto found = removals.find(records[i].Object);
        if (found == removals.end())
            continue;
        Future& future = found->second;
        while (future.next < future.indices.size() && future.indices[future.next] <= i)
            ++future.next;
        if (future.next < future.indices.size())
        {
            skipped[i] = skipped[future.indices[future.next++]] = 1;
        }
    }
    return skipped;
}
}
