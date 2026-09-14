#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <string>

// 128 human players; the headless ALife host needs one internal client state.
namespace gamma_net
{
constexpr unsigned max_players = 128;
constexpr unsigned max_client_states = max_players + 1;
constexpr unsigned protocol_version = 3; // Corrected CRC plus account ticket/content metadata.

inline bool read_chat_body(const unsigned char* data, std::size_t size, std::string& body)
{
    if (!data || size < 6 || size > 582) return false;
    const auto* name_end = static_cast<const unsigned char*>(std::memchr(data + 2, 0, size - 2));
    if (!name_end || name_end - (data + 2) > 64) return false;
    const auto* message = name_end + 1;
    const auto remaining = size - static_cast<std::size_t>(message - data);
    const auto* message_end = static_cast<const unsigned char*>(std::memchr(message, 0, remaining));
    if (!message_end || message_end - message > 512 || data + size - message_end != 3) return false;
    body.assign(reinterpret_cast<const char*>(message), message_end - message);
    return true;
}

// Pinned EGameActions weapon input IDs, followed by flags and two prediction seeds.
// The native adapter asserts these IDs against the engine enum before using this decoder.
inline bool valid_inventory_input(const unsigned char* data, std::size_t size)
{
    if (!data || size != 14) return false;
    std::uint16_t command;
    std::uint32_t flags;
    std::memcpy(&command, data, sizeof(command));
    std::memcpy(&flags, data + 2, sizeof(flags));
    return (flags == 1 || flags == 2) &&
        ((command >= 22 && command <= 27) || (command >= 29 && command <= 37));
}

struct movement_limiter
{
    float position[3] = {};
    float credit = 3.0f;
    std::uint32_t checked_at = 0;
    std::uint32_t accepted_at = 0;
    bool initialized = false;

    void reset(const float* authoritative_position, std::uint32_t now)
    {
        std::memcpy(position, authoritative_position, sizeof(position));
        credit = 3.0f;
        checked_at = accepted_at = now;
        initialized = true;
    }

    bool accept(const float* candidate, std::uint32_t now)
    {
        if (!initialized || !candidate) return false;
        const auto elapsed = now - checked_at;
        if (elapsed >= 0x80000000u) return false;
        credit = std::fmin(3.0f, credit + float(elapsed) * 0.015f);
        checked_at = now;
        if (now - accepted_at < 16) return false; // At most 60 movement updates per second.
        float distance_squared = 0;
        for (unsigned axis = 0; axis < 3; ++axis)
        {
            if (!std::isfinite(candidate[axis])) return false;
            const float delta = candidate[axis] - position[axis];
            distance_squared += delta * delta;
        }
        const float distance = std::sqrt(distance_squared);
        if (!std::isfinite(distance) || distance > credit) return false;
        credit -= distance;
        std::memcpy(position, candidate, sizeof(position));
        accepted_at = now;
        return true;
    }
};

inline bool newer(std::uint32_t a, std::uint32_t b)
{
    const auto delta = a - b;
    return delta != 0 && delta < 0x80000000u;
}

// CActor::net_Export sends 61 base bytes, optionally followed by one 77-byte physics state.
// Validate before the host imports floats into movement/physics state.
inline bool valid_coop_actor(const unsigned char* data, std::size_t size)
{
    if (!data || size < 61 || data[60] != 0 || data[59] > 1) return false;
    if (size != (data[59] ? 138u : 61u)) return false;
    const unsigned offsets[] = {0, 9, 13, 17, 21, 25, 29, 33, 44, 50, 54};
    for (auto offset : offsets)
    {
        float value;
        std::memcpy(&value, data + offset, sizeof(value));
        if (!std::isfinite(value) || std::fabs(value) > 100000.0f) return false;
    }
    if (data[59])
    {
        if (data[61] > 1) return false;
        for (unsigned offset = 62; offset < 138; offset += 4)
        {
            float value;
            std::memcpy(&value, data + offset, sizeof(value));
            if (!std::isfinite(value) || std::fabs(value) > 1000000.0f) return false;
        }
        float velocity_squared = 0, position_delta_squared = 0;
        for (unsigned axis = 0; axis < 3; ++axis)
        {
            float velocity, physics_position, actor_position;
            std::memcpy(&velocity, data + 74 + axis * 4, 4);
            std::memcpy(&physics_position, data + 110 + axis * 4, 4);
            std::memcpy(&actor_position, data + 9 + axis * 4, 4);
            velocity_squared += velocity * velocity;
            const float delta = physics_position - actor_position;
            position_delta_squared += delta * delta;
        }
        if (velocity_squared > 625.0f || position_delta_squared > 1.0f) return false;
    }
    return true;
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
