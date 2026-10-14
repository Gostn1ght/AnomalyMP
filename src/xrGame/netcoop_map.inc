// Client map presentation: self and mutual PDA contacts on this location.
// Object pointers bind permissions to one spawn, not a recycled network ID.
static xr_map<u16, CActor*> s_map_friends;

void map_players_reset() { s_map_friends.clear(); }
void map_player_forget(u16 id) { s_map_friends.erase(id); }

bool script_map_friend(int actor_id, LPCSTR name)
{
    if (!pure_client() || actor_id <= 0 || actor_id >= 65535 || !name || !name[0]) return false;
    CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(u16(actor_id)));
    if (!actor || xr_strcmp(actor->Name(), name)) return false;
    s_map_friends[u16(actor_id)] = actor;
    return true;
}

bool map_player_visible(u16 id, bool actor_spot)
{
    if (!pure_client()) return true;
    CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(id));
    if (!actor) return !actor_spot; // Unknown actor markers fail closed before spawn.
    if (id == 0) return false; // Invisible ALife authority anchor.
    if (actor == Actor()) return true;
    const auto allowed = s_map_friends.find(id);
    return allowed != s_map_friends.end() && allowed->second == actor;
}
