// store.py: the single-host durable authority, its journal and idempotent
// commands. Schema 6, the same tables and migrations as the Python service.
#pragma once
#include "lzm_sqlite.h"

namespace lzm
{
class Store
{
public:
    explicit Store(const std::wstring& path);
    ~Store();
    void close();

    std::recursive_mutex lock;
    Db db;
    std::optional<int64_t> epoch;
    std::wstring path;

    template <class F>
    auto transaction(F&& body) -> decltype(body(db))
    {
        std::lock_guard<std::recursive_mutex> guard(lock);
        if (!db.is_open()) throw Unavailable("store is closed");
        db.exec("BEGIN IMMEDIATE");
        try
        {
            if constexpr (std::is_void_v<decltype(body(db))>)
            {
                body(db);
                db.exec("COMMIT");
            }
            else
            {
                auto result = body(db);
                db.exec("COMMIT");
                return result;
            }
        }
        catch (...)
        {
            if (db.in_transaction()) db.exec("ROLLBACK");
            throw;
        }
    }

    using Apply = std::function<json(Db&)>;
    using Check = std::function<void(Db&)>;
    using Replay = std::function<void(Db&, const json&)>;
    json command(const std::string& actor, const std::string& command_id, const json& payload, const Apply& apply,
                 const Check& authorize = nullptr, const Replay& validate_replay = nullptr);
    void require_epoch(Db& tx);
    int64_t event(Db& tx, const std::string& aggregate, const std::string& type, const json& payload, double world_ms,
                  const std::string& topic = "world", std::optional<double> committed_ms = std::nullopt);
    int64_t journal_floor(Db& tx);
    std::vector<json> events(int64_t after, int64_t limit);
    json snapshot(size_t byte_limit = size_t(128) * 1024 * 1024);

private:
    void* lock_file_ = nullptr;
};
} // namespace lzm
