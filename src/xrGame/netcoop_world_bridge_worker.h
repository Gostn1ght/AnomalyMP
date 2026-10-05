#pragma once

#include "netcoop_world_clock.h"

namespace netcoop_world
{
struct BridgeDiagnostics
{
    bool ready=false, fetched=false, accepted=false;
    std::uint64_t rtt_ms=0;
    double drift_game_ms=0;
};

// Parsing, IO, follower errors and threads are isolated in an exception-enabled
// translation unit without engine headers. This boundary never throws.
class WorldBridgeWorker
{
    struct State;
    State* state_=nullptr;
public:
    WorldBridgeWorker() noexcept=default;
    ~WorldBridgeWorker();
    WorldBridgeWorker(const WorldBridgeWorker&)=delete;
    WorldBridgeWorker& operator=(const WorldBridgeWorker&)=delete;
    // 0: absent optional config; -1: invalid/unavailable; 1: started observer.
    int start(const char* config_path, const WorldStateSnapshot& local) noexcept;
    BridgeDiagnostics tick(const WorldStateSnapshot& local) noexcept;
    void stop() noexcept;
};
}
