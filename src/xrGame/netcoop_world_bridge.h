#pragma once

// Read-only transport. This does not adopt a remote clock or ownership. Keep
// this header private to the adapter .cpp, never in shared engine headers.
#include "netcoop_world_clock.h"
#include "../3rd party/nlohmann/json.hpp"
#include <string>
#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#pragma comment(lib,"winhttp.lib")
#endif

namespace netcoop_world
{
using BridgeJson = nlohmann::json;
inline BridgeJson bridge_json(const std::string& encoded, std::size_t limit)
{
    if (encoded.empty() || encoded.size()>limit) throw std::invalid_argument("bridge JSON budget");
    unsigned depth=0;
    bool string=false,escape=false;
    for (const char c : encoded)
    {
        if (string)
        {
            if (escape) escape=false;
            else if (c=='\\') escape=true;
            else if (c=='"') string=false;
        }
        else if (c=='"') string=true;
        else if (c=='{' || c=='[')
        { if (++depth>64) throw std::invalid_argument("bridge JSON nesting budget"); }
        else if (c=='}' || c==']')
        { if (!depth) throw std::invalid_argument("bridge JSON brackets");--depth; }
    }
    if (depth || string) throw std::invalid_argument("incomplete bridge JSON");
    return BridgeJson::parse(encoded,nullptr,false);
}
inline std::uint64_t bridge_unsigned(const BridgeJson& object, const char* key)
{
    if (!object.is_object()) throw std::invalid_argument("invalid bridge object");
    const auto found=object.find(key);
    if (found==object.end() || !found->is_number_integer()) throw std::invalid_argument("invalid bridge integer");
    if (found->is_number_unsigned()) return found->get<std::uint64_t>();
    const auto value=found->get<std::int64_t>();
    if (value<0) throw std::invalid_argument("negative bridge integer");
    return std::uint64_t(value);
}
inline double bridge_number(const BridgeJson& object, const char* key)
{
    if (!object.is_object()) throw std::invalid_argument("invalid bridge object");
    const auto found=object.find(key);
    if (found==object.end() || !found->is_number()) throw std::invalid_argument("invalid bridge number");
    return found->get<double>();
}
inline WorldStateSnapshot parse_bridge_bootstrap(const std::string& encoded)
{
    const auto body=bridge_json(encoded,65536);
    if (!body.is_object() || !body.contains("result") || !body["result"].is_object())
        throw std::invalid_argument("invalid bridge response");
    const auto& state=body["result"];
    if (bridge_unsigned(state,"schema")!=1 || !state.contains("clock") || !state["clock"].is_object() ||
        !state.contains("states") || !state["states"].is_object()) throw std::invalid_argument("invalid world bootstrap");
    const auto& clock=state["clock"];
    if (bridge_unsigned(clock,"schema")!=clock_schema) throw std::invalid_argument("unsupported clock schema");
    WorldStateSnapshot result;
    result.world_seed=bridge_unsigned(state,"world_seed");
    result.state_revision=bridge_unsigned(state,"state_revision");
    result.clock={clock_schema,bridge_unsigned(clock,"world_id"),bridge_unsigned(clock,"authority_epoch"),
        bridge_unsigned(clock,"sequence"),bridge_number(clock,"world_ms"),bridge_number(clock,"time_scale")};
    if (!valid(result.clock) || !result.state_revision || bridge_unsigned(clock,"seed")!=result.world_seed ||
        bridge_unsigned(clock,"revision")!=result.state_revision)
        throw std::invalid_argument("inconsistent clock/world bootstrap");
    return result;
}

struct BridgeConfig
{
    unsigned port=0;
    std::string token;
    static BridgeConfig parse(const std::string& encoded)
    {
        const auto body=bridge_json(encoded,4096);
        if (!body.is_object() || body.size()!=5 || bridge_unsigned(body,"schema")!=1 ||
            !body.contains("mode") || body["mode"]!="shadow" || !body.contains("host") || body["host"]!="127.0.0.1" ||
            !body.contains("token") || !body["token"].is_string()) throw std::invalid_argument("invalid read-only bridge config");
        const auto port=bridge_unsigned(body,"port");
        const auto token=body["token"].get<std::string>();
        if (!port || port>65535 || token.size()<32 || token.size()>256 ||
            token.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)
            throw std::invalid_argument("invalid bridge credential/port");
        return {unsigned(port),token};
    }
};

class BridgeObserver
{
    std::uint64_t world_,seed_;
    LocationClock follower_;
    bool bootstrapped_=false;
public:
    BridgeObserver(std::uint64_t world, std::uint64_t seed) : world_(world),seed_(seed),follower_(world) {}
    SyncResult receive(const WorldStateSnapshot& state, std::uint64_t sent, std::uint64_t received)
    {
        if (state.schema!=1 || !state.state_revision || state.clock.world_id!=world_ || state.world_seed!=seed_)
            return SyncResult::invalid;
        if (!bootstrapped_)
        {
            const auto result=follower_.bootstrap(state.clock,sent,received);
            bootstrapped_=result==SyncResult::applied;
            return result;
        }
        const auto result=follower_.observe(state.clock,sent,received);
        // Full bootstrap was fetched, so a shadow follower may immediately
        // reset its estimate after fencing. Production authority adoption must
        // still pause mutations/catch up and is deliberately not done here.
        if (result==SyncResult::epoch_changed || result==SyncResult::resync_required)
            return follower_.bootstrap(state.clock,sent,received);
        return result;
    }
    bool ready(std::uint64_t now) const { return follower_.ready(now); }
    double estimate(std::uint64_t now) { return follower_.estimate(now); }
};

#ifdef _WIN32
class BridgeHttpHandle
{
    HINTERNET handle_;
public:
    explicit BridgeHttpHandle(HINTERNET handle) : handle_(handle) {}
    ~BridgeHttpHandle() { if (handle_) WinHttpCloseHandle(handle_); }
    BridgeHttpHandle(const BridgeHttpHandle&)=delete;
    BridgeHttpHandle& operator=(const BridgeHttpHandle&)=delete;
    HINTERNET get() const { return handle_; }
};
inline bool bridge_fetch(const BridgeConfig& config, WorldStateSnapshot& result)
{
    const auto deadline=GetTickCount64()+2000;
    // No proxy, redirects, remote host, credential-bearing URLs, request body,
    // or mutations. IO runs exclusively on the adapter worker thread.
    if (!config.port || config.port>65535 || config.token.size()<32 || config.token.size()>256 ||
        config.token.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)
        return false;
    BridgeHttpHandle session(WinHttpOpen(L"LostZoneWorldShadow/1",WINHTTP_ACCESS_TYPE_NO_PROXY,
        WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0));
    if (!session.get() || !WinHttpSetTimeouts(session.get(),500,500,500,500)) return false;
    BridgeHttpHandle connection(WinHttpConnect(session.get(),L"127.0.0.1",INTERNET_PORT(config.port),0));
    BridgeHttpHandle request(connection.get() ? WinHttpOpenRequest(connection.get(),L"GET",L"/v1/bootstrap",nullptr,
        WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,0) : nullptr);
    if (!request.get()) return false;
    DWORD redirect=WINHTTP_OPTION_REDIRECT_POLICY_NEVER;
    if (!WinHttpSetOption(request.get(),WINHTTP_OPTION_REDIRECT_POLICY,&redirect,sizeof(redirect))) return false;
    std::wstring header=L"Authorization: Bearer ";
    header.append(config.token.begin(),config.token.end());header+=L"\r\n";
    if (!WinHttpSendRequest(request.get(),header.c_str(),DWORD(header.size()),WINHTTP_NO_REQUEST_DATA,0,0,0) ||
        !WinHttpReceiveResponse(request.get(),nullptr)) return false;
    DWORD status=0,bytes=sizeof(status);
    if (!WinHttpQueryHeaders(request.get(),WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,
        WINHTTP_HEADER_NAME_BY_INDEX,&status,&bytes,WINHTTP_NO_HEADER_INDEX) || status!=200) return false;
    std::string response;
    char buffer[4096];DWORD got=0;
    do
    {
        if (GetTickCount64()>deadline) return false;
        if (!WinHttpReadData(request.get(),buffer,sizeof(buffer),&got)) return false;
        response.append(buffer,got);
        if (response.size()>65536) return false;
    } while (got);
    try { result=parse_bridge_bootstrap(response);return true; }
    catch (const std::exception&) { return false; }
}
#endif
} // namespace netcoop_world
