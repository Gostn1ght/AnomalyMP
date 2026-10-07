#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

// Character save checksums only. Global xrCore CRC is also used by existing
// archives and is deliberately unchanged. NCH8 pins raw CRC32C; NCH3..7 may
// contain either xrCore's SSE4.2 raw CRC32C or its IEEE CRC32 fallback.
namespace netcoop
{
namespace save_checksum
{
template<std::uint32_t Polynomial>
constexpr std::array<std::uint32_t, 256> table()
{
    std::array<std::uint32_t, 256> result{};
    for (std::uint32_t i = 0; i < result.size(); ++i)
    {
        auto value = i;
        for (unsigned bit = 0; bit < 8; ++bit)
            value = (value >> 1) ^ ((value & 1) ? Polynomial : 0);
        result[i] = value;
    }
    return result;
}

inline std::uint32_t crc32c(const void* data, std::size_t size)
{
    static constexpr auto lookup = table<0x82f63b78>();
    const auto* bytes = static_cast<const unsigned char*>(data);
    std::uint32_t value = 0xffffffff;
    for (std::size_t i = 0; i < size; ++i)
        value = (value >> 8) ^ lookup[(value ^ bytes[i]) & 0xff];
    return value; // raw SSE4.2 convention, including UINT32_MAX for no bytes
}

inline std::uint32_t legacy_ieee(const void* data, std::size_t size)
{
    static constexpr auto lookup = table<0xedb88320>();
    const auto* bytes = static_cast<const unsigned char*>(data);
    std::uint32_t value = 0xffffffff;
    for (std::size_t i = 0; i < size; ++i)
        value = (value >> 8) ^ lookup[(value ^ bytes[i]) & 0xff];
    return value ^ 0xffffffff;
}
}
}
