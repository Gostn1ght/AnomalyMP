#pragma once
#include <vector>
#include <cstdint>

// Shared by the authoritative save transaction and the native host tests.
// Parent is a one-based index, zero means a root inventory item.
namespace hideout_storage
{
enum Result { ok, stale, equipped, unavailable, full, corrupt };
template<class Items, class Cost>
unsigned cells(const Items& items, Cost cost)
{
    unsigned total=0;
    for (const auto& item:items) if (!item.parent) total+=cost(item);
    return total;
}
template<class Items, class Cost, class Equipped>
Result transfer(Items& source, Items& target, unsigned index, unsigned capacity, Cost cost, Equipped equipped)
{
    if (index>=source.size() || source[index].parent) return unavailable;
    if (equipped(source[index])) return Result::equipped;
    if (cells(target,cost)+cost(source[index])>capacity) return full;
    std::vector<bool> moved(source.size(),false); moved[index]=true;
    for (unsigned i=0;i<source.size();++i)
    {
        if (source[i].parent>i) return corrupt;
        if (source[i].parent) moved[i]=moved[source[i].parent-1];
    }
    unsigned count=0;
    for (bool value:moved) if (value) ++count;
    if (target.size()+count>512) return full;
    std::vector<unsigned> source_map(source.size(),0),target_map(source.size(),0);
    Items remaining;
    for (unsigned i=0;i<source.size();++i)
    {
        auto item=source[i];
        if (moved[i])
        {
            target_map[i]=unsigned(target.size())+1;
            item.parent=item.parent ? target_map[item.parent-1] : 0;
            item.place=0; // withdrawn equipment always goes to the rucksack
            target.push_back(item);
        }
        else
        {
            source_map[i]=unsigned(remaining.size())+1;
            item.parent=item.parent ? source_map[item.parent-1] : 0;
            remaining.push_back(item);
        }
    }
    source.swap(remaining);
    return ok;
}
}
