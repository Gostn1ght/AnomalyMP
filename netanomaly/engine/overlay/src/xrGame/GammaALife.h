#pragma once
#include "level.h"
#include "xrServer.h"
#include "xrserver_objects.h"
#include "Actor.h"
#include "../xrNetServer/GammaNetPolicy.h"

// Preserve the story actor registry, but activate the world around every authenticated player.
inline float gamma_alife_distance(const Fvector& point, const Fvector& story_actor)
{
    if (!strstr(Core.Params, "-netcoop") || !g_pGameLevel || !Level().Server)
        return story_actor.distance_to(point);
    float positions[gamma_net::max_players * 3];
    unsigned count = 0;
    auto collect = [&](IClient* client)
    {
        xrClientData* peer = static_cast<xrClientData*>(client);
        if (peer->flags.bLocal || !peer->flags.bConnected || !peer->gamma_authenticated ||
            !peer->owner || count >= gamma_net::max_players) return;
        CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(peer->owner->ID));
        const Fvector& location = actor ? actor->Position() : peer->owner->o_Position;
        positions[count * 3] = location.x;
        positions[count * 3 + 1] = location.y;
        positions[count * 3 + 2] = location.z;
        ++count;
    };
    Level().Server->ForEachClientDo(collect);
    const float candidate[] = {point.x, point.y, point.z};
    return gamma_net::distance_to_players(candidate, positions, count);
}
