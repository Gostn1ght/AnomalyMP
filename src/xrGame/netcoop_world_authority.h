#pragma once

// Single-process authority on one local save directory. This is not a
// distributed lease: do not put the directory on NFS/SMB or run 25 writers.
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <random>
#include <stdexcept>
#include <string>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

namespace netcoop_world
{
inline std::string world_option(const char* params)
{
    const std::string args(params ? params : "");
    const std::string key = "-netcoop_world=";
    const auto pos = args.find(key);
    if (pos == std::string::npos) return {};
    if (pos && args[pos - 1] != ' ' && args[pos - 1] != '\t')
        throw std::invalid_argument("world option must be a complete argument");
    const auto begin = pos + key.size();
    const auto end = args.find_first_of(" \t\r\n", begin);
    const auto name = args.substr(begin, end - begin);
    if (name.empty() || name.size() > 61 || name.find_first_not_of(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_") != std::string::npos)
        throw std::invalid_argument("invalid persistent world name");
    if (end != std::string::npos && args.find(key, end) != std::string::npos)
        throw std::invalid_argument("duplicate world option");
    return name;
}

struct WorldIdentity
{
    std::uint64_t world_id = 0;
    std::uint64_t seed = 0;
    std::uint64_t epoch = 0;
};

class WorldAuthorityStore
{
public:
    WorldAuthorityStore() = default;
    WorldAuthorityStore(const WorldAuthorityStore&) = delete;
    WorldAuthorityStore& operator=(const WorldAuthorityStore&) = delete;
    ~WorldAuthorityStore() { close(); }

    void open(const std::string& directory, const std::string& name)
    {
        if (active()) throw std::logic_error("world authority already acquired");
        // Reuse the same name contract for direct callers, including fixtures.
        if (world_option(("-netcoop_world=" + name).c_str()) != name)
            throw std::invalid_argument("invalid world name");
        base_ = (std::filesystem::path(directory) / name).string();
        const auto lock = base_ + ".authority.lock";
#ifdef _WIN32
        lock_ = CreateFileA(lock.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
            nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (lock_ == INVALID_HANDLE_VALUE) throw std::runtime_error("world is locked or lock file is inaccessible");
#else
        lock_ = ::open(lock.c_str(), O_CREAT | O_RDWR | O_CLOEXEC, 0600);
        if (lock_ < 0) throw std::runtime_error("cannot open world lock");
        if (flock(lock_, LOCK_EX | LOCK_NB) != 0)
        {
            ::close(lock_); lock_ = -1;
            throw std::runtime_error("world is already owned");
        }
#endif
        try
        {
            const auto path = base_ + ".authority";
            FILE* file = std::fopen(path.c_str(), "rb");
            if (file)
            {
                std::array<unsigned char, 40> bytes{};
                const auto count = std::fread(bytes.data(), 1, bytes.size(), file);
                const bool clean = std::fgetc(file) == EOF && !std::ferror(file);
                const bool closed = std::fclose(file) == 0;
                if (count != bytes.size() || !clean || !closed ||
                    read64(bytes, 0) != magic || read64(bytes, 32) != checksum(bytes))
                    throw std::runtime_error("corrupt world authority record; recovery required");
                identity_ = {read64(bytes, 8), read64(bytes, 16), read64(bytes, 24)};
                if (!identity_.world_id || !identity_.epoch)
                    throw std::runtime_error("invalid world authority record");
            }
            else
            {
                if (errno != ENOENT) throw std::runtime_error("world authority record is inaccessible");
                // A legacy W1 snapshot may be adopted once. Missing identity
                // on a clock-aware snapshot is rejected by the ALife adapter.
                identity_ = {random_id(), random_id(), 0};
            }
            if (identity_.epoch == UINT64_MAX) throw std::overflow_error("world epoch exhausted");
            ++identity_.epoch;
            std::array<unsigned char, 40> bytes{};
            write64(bytes, 0, magic);
            write64(bytes, 8, identity_.world_id);
            write64(bytes, 16, identity_.seed);
            write64(bytes, 24, identity_.epoch);
            write64(bytes, 32, checksum(bytes));
            // Persist fence before any clock or game event can be published.
            durable_replace(path, bytes);
        }
        catch (...) { close(); throw; }
    }

    bool active() const
    {
#ifdef _WIN32
        return lock_ != INVALID_HANDLE_VALUE;
#else
        return lock_ >= 0;
#endif
    }
    const WorldIdentity& identity() const
    {
        if (!active()) throw std::logic_error("world authority not acquired");
        return identity_;
    }
    void close()
    {
#ifdef _WIN32
        if (active()) CloseHandle(lock_);
        lock_ = INVALID_HANDLE_VALUE;
#else
        if (active()) ::close(lock_);
        lock_ = -1;
#endif
        identity_ = {};
    }

private:
    // Explicit little-endian fields; version is part of the magic.
    static constexpr std::uint64_t magic = 0x31545541445a4cULL;
    static std::uint64_t read64(const std::array<unsigned char, 40>& bytes, std::size_t at)
    {
        std::uint64_t value = 0;
        for (unsigned i = 0; i < 8; ++i) value |= std::uint64_t(bytes[at + i]) << (8 * i);
        return value;
    }
    static void write64(std::array<unsigned char, 40>& bytes, std::size_t at, std::uint64_t value)
    {
        for (unsigned i = 0; i < 8; ++i) bytes[at + i] = static_cast<unsigned char>(value >> (8 * i));
    }
    static std::uint64_t checksum(const std::array<unsigned char, 40>& bytes)
    {
        std::uint64_t hash = 14695981039346656037ULL;
        for (std::size_t i = 0; i < 32; ++i) { hash ^= bytes[i]; hash *= 1099511628211ULL; }
        return hash;
    }
    static std::uint64_t random_id()
    {
        std::random_device random;
        std::uint64_t value = (std::uint64_t(random()) << 32) ^ random();
        return value ? value : 1;
    }
    static void durable_replace(const std::string& path, const std::array<unsigned char, 40>& bytes)
    {
        const auto temp = path + ".tmp";
        FILE* file = std::fopen(temp.c_str(), "wb");
        if (!file) throw std::runtime_error("cannot write world authority record");
        bool written = std::fwrite(bytes.data(), 1, bytes.size(), file) == bytes.size() && std::fflush(file) == 0;
#ifdef _WIN32
        written = written && _commit(_fileno(file)) == 0;
#else
        written = written && fsync(fileno(file)) == 0;
#endif
        const bool closed = std::fclose(file) == 0;
        if (!written || !closed) throw std::runtime_error("world authority record flush failed");
#ifdef _WIN32
        if (!MoveFileExA(temp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
            throw std::runtime_error("world authority record commit failed");
#else
        if (std::rename(temp.c_str(), path.c_str()) != 0)
            throw std::runtime_error("world authority record commit failed");
        const auto parent = std::filesystem::path(path).parent_path().string();
        const int dir = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        if (dir < 0) throw std::runtime_error("cannot open authority directory for flush");
        const bool flushed = fsync(dir) == 0;
        ::close(dir);
        if (!flushed) throw std::runtime_error("authority directory flush failed");
#endif
    }
    std::string base_;
    WorldIdentity identity_;
#ifdef _WIN32
    HANDLE lock_ = INVALID_HANDLE_VALUE;
#else
    int lock_ = -1;
#endif
};

inline WorldAuthorityStore& local_world_authority()
{
    static WorldAuthorityStore authority;
    return authority;
}
} // namespace netcoop_world
