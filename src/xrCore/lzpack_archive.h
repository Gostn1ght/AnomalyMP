#pragma once
#include <windows.h>
#include <array>
#include <cstdint>
#include <memory>
#include "lzpack_format.h"

class LZPackArchive
{
    HANDLE mapping;
    const unsigned char* view = nullptr; // the whole volume, mapped once
    std::uint64_t id;                    // unique per opened volume (thread caches key by it)
    std::array<unsigned char, lzpack::header_size> header{};
    std::array<unsigned char, 32> key{};
    std::uint32_t size;
    LZPackArchive(HANDLE handle, const unsigned char* bytes, std::uint32_t physical);
public:
    ~LZPackArchive();
    LZPackArchive(const LZPackArchive&) = delete;
    LZPackArchive& operator=(const LZPackArchive&) = delete;
    static std::shared_ptr<LZPackArchive> open(HANDLE handle, std::uint32_t physical);
    std::uint32_t length() const { return size; }
    void read(std::uint32_t offset, void* buffer, std::uint32_t count) const;
};
