#pragma once

#include <algorithm>

namespace netcoop
{
// A corpse is released only after every original child is independent.
// The adapter validates all children before detaching any. On a failed detach
// already-dropped items survive and the body retains the remaining inventory.
// No IDs, item quantities or item state are created or rewritten here.
template <class Children, class Validate, class Detach>
bool preserve_corpse_inventory(Children& children, Validate validate, Detach detach)
{
    if (children.size() > 4096) return false;
    const auto original = children;
    auto sorted = original;
    std::sort(sorted.begin(), sorted.end());
    if (std::adjacent_find(sorted.begin(), sorted.end()) != sorted.end()) return false;
    for (const auto id : original)
        if (!validate(id)) return false;
    for (const auto id : original)
    {
        if (!detach(id)) return false;
        if (std::find(children.begin(), children.end(), id) != children.end()) return false;
    }
    return children.empty();
}
}
