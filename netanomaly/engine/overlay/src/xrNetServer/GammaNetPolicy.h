#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

// 128 human players; the headless ALife host needs one internal client state.
namespace gamma_net
{
constexpr unsigned max_players = 128;
constexpr unsigned max_client_states = max_players + 1;
constexpr unsigned protocol_version = 2; // Corrected compressed-packet CRC range.

inline bool newer(std::uint32_t a, std::uint32_t b)
{
    const auto delta = a - b;
    return delta != 0 && delta < 0x80000000u;
}

// Parse one complete slash-delimited option, without atoi overflow or substring matches.
inline unsigned player_limit(const char* options)
{
    for (const char* p = options; p && *p;)
    {
        if (std::strncmp(p, "maxplayers=", 11) == 0)
        {
            p += 11;
            unsigned value = 0;
            bool digit = false;
            for (; *p && *p != '/'; ++p)
            {
                if (*p < '0' || *p > '9' || value > max_players)
                    return max_players;
                digit = true;
                value = value * 10 + unsigned(*p - '0');
            }
            return digit && value >= 1 && value <= max_players ? value : max_players;
        }
        p = std::strchr(p, '/');
        if (p) ++p;
    }
    return max_players;
}

// Validate the entire merged frame before delivering any contained message.
inline bool valid_frame(const unsigned char* data, std::size_t size, bool merged,
                        std::size_t packet_limit)
{
    if (!data || size < 2) return false;
    if (!merged) return size < packet_limit;
    std::size_t pos = 0;
    while (pos < size)
    {
        if (size - pos < 2) return false;
        const std::size_t n = data[pos] | (std::size_t(data[pos + 1]) << 8);
        pos += 2;
        if (n < 2 || n >= packet_limit || n > size - pos) return false;
        pos += n;
    }
    return true;
}
}
