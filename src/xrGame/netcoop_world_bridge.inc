// Engine-only adapter; parsing and IO live across a noexcept worker boundary.
static netcoop_world::WorldBridgeWorker s_world_shadow_bridge;
static bool s_world_bridge_checked=false, s_world_bridge_active=false;
static u64 s_world_bridge_tick=0, s_world_bridge_log=0;

static void server_world_bridge_update()
{
    if (s_world_bridge_checked && !s_world_bridge_active) return;
    if (!ai().get_alife()) return;
    const u64 now=GetTickCount64();
    if (s_world_bridge_tick && now-s_world_bridge_tick<1000) return;
    s_world_bridge_tick=now;
    netcoop_world::WorldStateSnapshot local{};
    if (!const_cast<CALifeSimulator*>(ai().get_alife())->export_world_state(local)) return;
    if (!s_world_bridge_checked)
    {
        s_world_bridge_checked=true;
        string_path path;
        FS.update_path(path,"$app_data_root$","netcoop_world_bridge.json");
        const int result=s_world_shadow_bridge.start(path,local);
        s_world_bridge_active=result==1;
        if (result<0) Msg("! [world-bridge-shadow] invalid private configuration; bridge disabled");
        if (result==1) Msg("[world-bridge-shadow] private loopback observer configured; authority remains local");
    }
    if (!s_world_bridge_active) return;
    const auto diagnostic=s_world_shadow_bridge.tick(local);
    if (!s_world_bridge_log || now-s_world_bridge_log>=10000)
    {
        s_world_bridge_log=now;
        Msg("[world-bridge-shadow] ready=%u fetched=%u accepted=%u rtt_ms=%llu drift_game_ms=%.3f (read only)",
            diagnostic.ready ? 1u:0u,diagnostic.fetched ? 1u:0u,diagnostic.accepted ? 1u:0u,
            diagnostic.rtt_ms,diagnostic.drift_game_ms);
    }
}

void server_world_bridge_stop()
{
    s_world_shadow_bridge.stop(); // Bounded IO, joined thread, no engine callback.
    s_world_bridge_checked=false;s_world_bridge_active=false;s_world_bridge_tick=0;s_world_bridge_log=0;
}
