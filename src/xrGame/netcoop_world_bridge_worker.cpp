// No pch_script/xrCore headers: this isolated module needs ordinary C++
// unwinding for JSON validation, mutexes, threads and WinHTTP RAII handles.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "netcoop_world_bridge_worker.h"
#include "netcoop_world_bridge.h"
#include <condition_variable>
#include <fstream>
#include <memory>
#include <mutex>
#include <thread>

namespace netcoop_world
{
static std::uint64_t bridge_mono_ms() noexcept
{
#ifdef _WIN32
    return GetTickCount64();
#else
    return std::uint64_t(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
#endif
}

struct WorldBridgeWorker::State
{
    BridgeConfig config;
    BridgeObserver observer;
    std::mutex lock;
    std::condition_variable wake;
    bool stopping=false, pending=false, successful=false;
    WorldStateSnapshot incoming{};
    std::uint64_t sent=0, received=0;
    std::thread worker;

    State(BridgeConfig connection, const WorldStateSnapshot& local)
        : config(std::move(connection)), observer(local.clock.world_id,local.world_seed), worker([this]{run();}) {}
    ~State()
    {
        { std::lock_guard<std::mutex> guard(lock);stopping=true; }
        wake.notify_all();
        if (worker.joinable()) worker.join();
    }
    void run() noexcept
    {
        for (;;)
        {
            { std::lock_guard<std::mutex> guard(lock);if (stopping) return; }
            WorldStateSnapshot result{};
            const auto started=bridge_mono_ms();
            bool ok=false;
            try
            {
#ifdef _WIN32
                ok=bridge_fetch(config,result);
#endif
            }
            catch (...) {} // Fail closed; no payloads or credentials in logs.
            const auto finished=bridge_mono_ms();
            std::unique_lock<std::mutex> guard(lock);
            incoming=result;successful=ok;sent=started;received=finished;pending=true;
            if (wake.wait_for(guard,std::chrono::seconds(5),[this]{return stopping;})) return;
        }
    }
    BridgeDiagnostics tick(const WorldStateSnapshot& local)
    {
        WorldStateSnapshot sample{};
        bool available=false,ok=false;
        std::uint64_t started=0,finished=0;
        {
            std::lock_guard<std::mutex> guard(lock);
            if (pending) {sample=incoming;available=true;ok=successful;started=sent;finished=received;pending=false;}
        }
        BridgeDiagnostics result;
        result.fetched=available && ok;
        result.rtt_ms=finished>=started ? finished-started : 0;
        if (result.fetched)
            result.accepted=observer.receive(sample,started,finished)==SyncResult::applied;
        const auto now=bridge_mono_ms();
        result.ready=observer.ready(now);
        if (result.ready) result.drift_game_ms=observer.estimate(now)-local.clock.world_ms;
        return result;
    }
};

WorldBridgeWorker::~WorldBridgeWorker() {stop();}
int WorldBridgeWorker::start(const char* path, const WorldStateSnapshot& local) noexcept
{
    stop();
    try
    {
        if (!path || !*path || !valid(local.clock) || local.schema!=1 || !local.state_revision) return -1;
        std::ifstream input(path,std::ios::binary);
        if (!input) return 0;
        char bytes[4097];input.read(bytes,sizeof(bytes));
        auto config=BridgeConfig::parse(std::string(bytes,std::size_t(input.gcount())));
        auto state=std::make_unique<State>(std::move(config),local);
        state_=state.release();
        return 1;
    }
    catch (...) {return -1;}
}
BridgeDiagnostics WorldBridgeWorker::tick(const WorldStateSnapshot& local) noexcept
{
    if (!state_) return {};
    try {return state_->tick(local);}
    catch (...) {return {};}
}
void WorldBridgeWorker::stop() noexcept
{
    delete state_;
    state_=nullptr;
}
}
