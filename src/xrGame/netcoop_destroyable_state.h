#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <string_view>

namespace netcoop_destroyable_state
{
enum class Status { absent, valid, invalid };
inline constexpr std::string_view begin = "\n\n; lost-zone-damage-v1-begin\n[lz_ph_damage_v1]\nhealth_bits=";
inline constexpr std::string_view end = "\n; lost-zone-damage-v1-end\n";
inline constexpr std::size_t footer_size = begin.size() + 8 + end.size();
inline std::string_view view(const char* text) { return text ? std::string_view(text) : std::string_view(); }

inline bool contains_reserved(std::string_view text)
{
    // INI section names are case-insensitive. Never append a duplicate or
    // silently consume a pre-existing author's section/partial marker.
    for (std::string_view word : {std::string_view("lost-zone-damage-v1"), std::string_view("lz_ph_damage_v1")})
        for (std::size_t n = 0; n + word.size() <= text.size(); ++n)
        {
            std::size_t k = 0;
            for (; k < word.size(); ++k)
            {
                char c = text[n + k];
                if (c >= 'A' && c <= 'Z') c = static_cast<char>(c + ('a' - 'A'));
                if (c != word[k]) break;
            }
            if (k == word.size()) return true;
        }
    return false;
}

inline Status read(std::string_view text, float& health)
{
    static_assert(sizeof(float) == sizeof(std::uint32_t) && std::numeric_limits<float>::is_iec559,
        "Destroyable health requires IEEE binary32");
    if (text.find('\0') != std::string_view::npos) return Status::invalid;
    const auto offset = text.find(begin);
    if (offset == std::string_view::npos)
        return contains_reserved(text) ? Status::invalid : Status::absent;
    if (text.size() - offset != footer_size || contains_reserved(text.substr(0, offset)) ||
        text.substr(offset + begin.size() + 8) != end) return Status::invalid;
    std::uint32_t bits = 0;
    for (char c : text.substr(offset + begin.size(), 8))
    {
        if (c >= '0' && c <= '9') bits = (bits << 4) | static_cast<unsigned>(c - '0');
        else if (c >= 'a' && c <= 'f') bits = (bits << 4) | static_cast<unsigned>(c - 'a' + 10);
        else return Status::invalid;
    }
    float value;
    std::memcpy(&value, &bits, sizeof(value));
    if (!std::isfinite(value)) return Status::invalid;
    health = value;
    return Status::valid;
}

inline bool write(std::string_view text, float health, std::size_t max_bytes, std::string& output)
{
    float previous = 0.f;
    const auto status = read(text, previous);
    if (status == Status::invalid || !std::isfinite(health)) return false;
    const auto prefix = status == Status::valid ? text.substr(0, text.size() - footer_size) : text;
    if (max_bytes < footer_size || prefix.size() > max_bytes - footer_size) return false;
    std::uint32_t bits;
    std::memcpy(&bits, &health, sizeof(bits));
    std::string next(prefix);
    next.append(begin);
    constexpr char hex[] = "0123456789abcdef";
    for (unsigned n = 0; n < 8; ++n) next.push_back(hex[(bits >> (28 - 4 * n)) & 15]);
    next.append(end);
    output.swap(next);
    return true;
}
}
