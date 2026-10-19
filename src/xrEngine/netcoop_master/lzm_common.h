// Lost Zone world master in the engine (owner 2026-10-19: "the master must be
// part of the game engine, in C++"). A port of backend/lostzone (the Python
// World Service) that keeps its database, its HTTP contract and its
// configuration files, so the location servers and an existing world move to
// it unchanged. This header: errors, JSON exactly as Python's json module
// writes it (canonical form, hashes stay comparable), validators, crypto.
#pragma once

#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "../../3rd party/nlohmann/json.hpp"

namespace lzm
{
using json = nlohmann::json;

// Python's exception classes of the backend, mapped by the HTTP layer:
// Invalid/ValueError/TypeError 400, Forbidden (PermissionError) 403,
// Conflict 409 (message shown), Unavailable 503.
struct Invalid : std::runtime_error { using std::runtime_error::runtime_error; };
struct Conflict : std::runtime_error { using std::runtime_error::runtime_error; };
struct Unavailable : std::runtime_error { using std::runtime_error::runtime_error; };
struct Forbidden : std::runtime_error { using std::runtime_error::runtime_error; };
// A scheduled event whose type has no handler (Python UnavailableHandler).
struct UnavailableHandler : std::runtime_error { using std::runtime_error::runtime_error; };

// -- JSON ------------------------------------------------------------------
// json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False,
// allow_nan=False); Invalid above `limit` bytes.
std::string canonical(const json& value, size_t limit = 1024 * 1024);
// json.dumps(value) with Python's default separators ", " and ": ".
std::string python_dumps(const json& value, bool sort_keys = false, int indent = -1);
// json.loads with duplicate keys and NaN/Infinity refused (strict_json).
json strict_json(const std::string& text);
// json.loads of a value this service wrote itself.
json loads(const std::string& text);
std::string python_float(double value);

// -- validators (store.py) ---------------------------------------------------
const std::string& identifier(const json& value);
std::string identifier(const std::string& value);
const std::string& persistent_id(const json& value);
std::string persistent_id(const std::string& value);
int64_t positive(const json& value, const char* name = "version");
int64_t positive(int64_t value, const char* name = "version");
double finite(const json& value, double low = 0, double high = 9007199254740991.0);
double finite(double value, double low = 0, double high = 9007199254740991.0);
bool is_int(const json& value);       // Python type(value) is int
bool is_number(const json& value);    // type(value) in (int, float)
int64_t as_int(const json& value);
double as_number(const json& value);
const std::string& as_string(const json& value);
bool regex_full(const std::string& text, const char* pattern);

// -- crypto and encodings (Windows CNG) -----------------------------------------
std::string sha256_hex(const std::string& data);
std::string sha256_raw(const std::string& data);
std::string sha1_raw(const std::string& data);
std::string sha512_raw(const std::string& data);
std::string hmac_sha256_hex(const std::string& key, const std::string& data);
std::string random_bytes(size_t count);
std::string hex(const std::string& raw);
std::string base64(const std::string& raw);
std::string base64_urlsafe_nopad(const std::string& raw);
// base64.b64decode(validate=True); altchars "-_" for the URL-safe variant.
bool base64_decode(const std::string& text, std::string& out, bool urlsafe = false);
std::string token_urlsafe(size_t bytes);   // secrets.token_urlsafe
std::string token_hex(size_t bytes);       // secrets.token_hex
std::string uuid4_hex();
std::string uuid5_url_hex(const std::string& name);  // uuid5(NAMESPACE_URL, name).hex
bool constant_time_equal(const std::string& a, const std::string& b);

// -- clocks --------------------------------------------------------------------
int64_t monotonic_ns();
int64_t wall_ms();

std::string lower(std::string text);
std::string trim(const std::string& text);
std::vector<std::string> split(const std::string& text, char separator);
// Python int(text) for decimal text: optional surrounding whitespace and sign.
int64_t parse_int(const std::string& text);
std::string format(const char* fmt, ...);

// UTF-8 <-> UTF-16 for the Windows APIs.
std::wstring widen(const std::string& text);
std::string narrow(const std::wstring& text);

// Journal of the master (window, log file); never receives secrets.
void log_line(const std::string& line);
void set_log_sink(std::function<void(const std::string&)> sink);
} // namespace lzm
