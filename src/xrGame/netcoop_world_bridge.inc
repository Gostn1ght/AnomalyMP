// Included only in netcoop.cpp. Worker owns plain captured data and WinHTTP;
// all engine accesses and logging happen on the game/server thread.

class EngineWorldShadowBridge
{
    netcoop_world::BridgeConfig config_;
    netcoop_world::BridgeObserver observer_;
    std::mutex lock_;
    std::condition_variable wake_;
    bool stop_=false, pending_=false, successful_=false;
    netcoop_world::WorldStateSnapshot incoming_{};
    u64 sent_=0, received_=0, last_log_=0;
    std::thread worker_;
    void run()
    {
        for (;;)
        {
            { std::lock_guard<std::mutex> guard(lock_);if (stop_) return; }
            netcoop_world::WorldStateSnapshot result{};
            const u64 sent=GetTickCount64();
            bool ok=false;
            try { ok=netcoop_world::bridge_fetch(config_,result); }
            catch (const std::exception&) {} // Fail closed; no secret payloads in logs.
            const u64 received=GetTickCount64();
            std::unique_lock<std::mutex> guard(lock_);
            incoming_=result;successful_=ok;sent_=sent;received_=received;pending_=true;
            if (wake_.wait_for(guard,std::chrono::seconds(5),[this]{return stop_;})) return;
        }
    }
public:
    EngineWorldShadowBridge(netcoop_world::BridgeConfig config, const netcoop_world::WorldStateSnapshot& local)
        : config_(std::move(config)),observer_(local.clock.world_id,local.world_seed),worker_([this]{run();}) {}
    ~EngineWorldShadowBridge()
    {
        { std::lock_guard<std::mutex> guard(lock_);stop_=true; }
        wake_.notify_all();
        if (worker_.joinable()) worker_.join();
    }
    void tick(const netcoop_world::WorldStateSnapshot& local)
    {
        netcoop_world::WorldStateSnapshot incoming{};
        bool available=false,ok=false;
        u64 sent=0,received=0;
        {
            std::lock_guard<std::mutex> guard(lock_);
            if (pending_) { incoming=incoming_;available=true;ok=successful_;sent=sent_;received=received_;pending_=false; }
        }
        const u64 now=GetTickCount64();
        auto outcome=netcoop_world::SyncResult::invalid;
        if (available && ok)
            try { outcome=observer_.receive(incoming,sent,received); }
            catch (const std::exception&) {} // Diagnostic input must never break gameplay.
        if (!last_log_ || now-last_log_>=10000)
        {
            last_log_=now;
            bool ready=observer_.ready(now);
            double drift=0;
            try { if (ready) drift=observer_.estimate(now)-local.clock.world_ms; }
            catch (const std::exception&) { ready=false; }
            Msg("[world-bridge-shadow] ready=%u fetched=%u accepted=%u rtt_ms=%llu drift_game_ms=%.3f (read only)",
                ready ? 1u:0u,available && ok ? 1u:0u,outcome==netcoop_world::SyncResult::applied ? 1u:0u,
                received>=sent ? received-sent : 0,drift);
        }
    }
};
static std::unique_ptr<EngineWorldShadowBridge> s_world_shadow_bridge;
static bool s_world_bridge_checked=false;
static u64 s_world_bridge_tick=0;

static void server_world_bridge_update()
{
    if (s_world_bridge_checked && !s_world_shadow_bridge) return;
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
        std::ifstream input(path,std::ios::binary);
        if (!input) return; // Optional private config; never shipped in client overlay.
        char bytes[4097]={};input.read(bytes,sizeof(bytes));
        try
        {
            const auto config=netcoop_world::BridgeConfig::parse(std::string(bytes,std::size_t(input.gcount())));
            s_world_shadow_bridge.reset(new EngineWorldShadowBridge(config,local));
            Msg("[world-bridge-shadow] private loopback observer configured; authority remains local");
        }
        catch (const std::exception&)
        { Msg("! [world-bridge-shadow] invalid private configuration; bridge disabled"); }
    }
    if (s_world_shadow_bridge) s_world_shadow_bridge->tick(local);
}

void server_world_bridge_stop()
{
    s_world_shadow_bridge.reset(); // Worker has bounded IO; no detached engine callback.
    s_world_bridge_checked=false;s_world_bridge_tick=0;
}
