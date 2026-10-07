#pragma once
#include <cstdio>
#include <cstring>

namespace netcoop {
struct BotTarget {
    char address[256] = {};
    char level[64] = {};
};

// Server target payload: host|port|level. Auth adds the redirect| prefix.
// Preserve the pending target on malformed input; never disconnect under the
// receive-queue lock. The caller reconnects from bots_frame instead.
inline bool parse_bot_target(const char* text, BotTarget& output)
{
    if (!text) return false;
    const char* separator = std::strchr(text, '|');
    if (!separator) return false;
    const auto host_size = separator - text;
    if (host_size < 1 || host_size > 127) return false;
    for (const char* p = text; p != separator; ++p) {
        const unsigned char c = static_cast<unsigned char>(*p);
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '.' || c == '-' || c == '_')) return false;
    }
    const char* port_start = separator + 1;
    const char* level_start = std::strchr(port_start, '|');
    if (!level_start || level_start - port_start < 1 || level_start - port_start > 5) return false;
    unsigned port = 0;
    for (const char* p = port_start; p != level_start; ++p) {
        if (*p < '0' || *p > '9') return false;
        port = port * 10 + unsigned(*p - '0');
    }
    if (!port || port > 65535) return false;
    ++level_start;
    const auto level_size = std::strlen(level_start);
    if (!level_size || level_size > 63) return false;
    for (const char* p = level_start; *p; ++p) {
        const unsigned char c = static_cast<unsigned char>(*p);
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_')) return false;
    }
    BotTarget target;
    char host[128] = {};
    std::memcpy(host, text, static_cast<std::size_t>(host_size));
    std::snprintf(target.address, sizeof(target.address), "%s/port=%u", host, port);
    std::memcpy(target.level, level_start, level_size + 1);
    output = target;
    return true;
}
} // namespace netcoop
