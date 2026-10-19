// SQLite for the master: the same world.sqlite the Python service wrote. The
// library is sqlite3.dll beside the executable (loaded at start), rows come
// back as JSON objects with Python sqlite3's types: INTEGER int, REAL float,
// TEXT str, NULL None.
#pragma once
#include "lzm_common.h"

namespace lzm
{
class Db
{
public:
    static bool load_library(std::string& error);
    Db() = default;
    ~Db();
    Db(const Db&) = delete;
    Db& operator=(const Db&) = delete;

    void open(const std::wstring& path, bool read_only = false);
    void close();
    bool is_open() const { return handle_ != nullptr; }

    using Params = std::vector<json>;
    json one(const std::string& sql, const Params& params = {});
    std::vector<json> all(const std::string& sql, const Params& params = {});
    // A single scalar of the first row (null when no row).
    json scalar(const std::string& sql, const Params& params = {});
    int64_t exec(const std::string& sql, const Params& params = {});  // changed rows
    int64_t last_rowid();
    void script(const std::string& sql);
    bool in_transaction();

private:
    void* handle_ = nullptr;
    void run(const std::string& sql, const Params& params, const std::function<bool(void*)>& row);
};
} // namespace lzm
