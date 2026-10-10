#pragma once
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>

// LZPACK1 wraps a compressed X-Ray DB. No whole-archive plaintext cache.
// Every 64 KiB block has an independent AES-256-GCM tag. AAD is the entire
// 48-byte header followed by the little-endian block number.
namespace lzpack
{
constexpr std::uint32_t header_size = 48, block_size = 65536, tag_size = 16;
inline std::uint32_t read32(const unsigned char* p)
{
    return std::uint32_t(p[0]) | (std::uint32_t(p[1]) << 8) |
        (std::uint32_t(p[2]) << 16) | (std::uint32_t(p[3]) << 24);
}
inline void write32(unsigned char* p, std::uint32_t n)
{
    for (unsigned i = 0; i != 4; ++i) p[i] = static_cast<unsigned char>(n >> (8 * i));
}
inline bool magic(const unsigned char* p) { return std::memcmp(p, "LZPACK1\0", 8) == 0; }
inline std::uint32_t logical_size(const unsigned char* header, std::uint64_t physical)
{
    if (!magic(header) || read32(header + 8) != 1 || read32(header + 12) != block_size)
        throw std::runtime_error("Unsupported Lost Zone archive version");
    const std::uint64_t size = std::uint64_t(read32(header + 16)) | (std::uint64_t(read32(header + 20)) << 32);
    const std::uint64_t blocks = (size + block_size - 1) / block_size;
    if (!size || size > (std::numeric_limits<std::uint32_t>::max)() ||
        header_size + size + blocks * tag_size != physical)
        throw std::runtime_error("Truncated or invalid Lost Zone archive");
    return static_cast<std::uint32_t>(size);
}
inline void range(std::uint32_t size, std::uint32_t offset, std::uint32_t count)
{
    if (offset > size || count > size - offset) throw std::runtime_error("Lost Zone archive read outside file");
}
}
