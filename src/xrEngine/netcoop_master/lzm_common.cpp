#include "lzm_common.h"

#include <windows.h>
#include <bcrypt.h>

#include <charconv>
#include <cmath>
#include <cstdarg>
#include <regex>

#pragma comment(lib, "bcrypt.lib")

namespace lzm
{
// -- canonical JSON -------------------------------------------------------------
std::string python_float(double value)
{
    if (!std::isfinite(value))
        throw Invalid("invalid JSON state");
    if (value == 0)
        return std::signbit(value) ? "-0.0" : "0.0";
    char buffer[64];
    auto result = std::to_chars(buffer, buffer + sizeof(buffer), value, std::chars_format::scientific);
    std::string text(buffer, result.ptr);
    bool negative = text[0] == '-';
    if (negative)
        text.erase(0, 1);
    size_t e = text.find('e');
    std::string mantissa = text.substr(0, e);
    int exponent = std::atoi(text.c_str() + e + 1);
    std::string digits;
    for (char c : mantissa)
        if (c != '.')
            digits += c;
    while (digits.size() > 1 && digits.back() == '0')
        digits.pop_back();
    std::string out;
    // repr(): exponent notation below 1e-4 and from 1e16 (float_repr_style 'short').
    if (exponent < -4 || exponent >= 16)
    {
        out = digits.substr(0, 1);
        if (digits.size() > 1)
            out += "." + digits.substr(1);
        char exp[16];
        snprintf(exp, sizeof(exp), "e%c%02d", exponent < 0 ? '-' : '+', std::abs(exponent));
        out += exp;
    }
    else
    {
        int point = exponent + 1;  // digits before the decimal point
        if (point <= 0)
            out = "0." + std::string(size_t(-point), '0') + digits;
        else if (size_t(point) >= digits.size())
            out = digits + std::string(size_t(point) - digits.size(), '0') + ".0";
        else
            out = digits.substr(0, size_t(point)) + "." + digits.substr(size_t(point));
    }
    return negative ? "-" + out : out;
}

static void escape(std::string& out, const std::string& text)
{
    out += '"';
    for (unsigned char c : text)
    {
        switch (c)
        {
        case '"': out += "\\\""; break;
        case '\\': out += "\\\\"; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        case '\b': out += "\\b"; break;
        case '\f': out += "\\f"; break;
        default:
            if (c < 0x20)
            {
                char code[8];
                snprintf(code, sizeof(code), "\\u%04x", c);
                out += code;
            }
            else
                out += char(c);
        }
    }
    out += '"';
}

static void dump(std::string& out, const json& value, const char* item, const char* key, int indent, int depth, size_t limit)
{
    if (out.size() > limit)
        throw Invalid("state exceeds size limit");
    if (depth > 900)
        throw Invalid("invalid JSON state");
    auto newline = [&](int level) {
        if (indent >= 0)
        {
            out += '\n';
            out.append(size_t(indent * level), ' ');
        }
    };
    switch (value.type())
    {
    case json::value_t::null: out += "null"; break;
    case json::value_t::boolean: out += value.get<bool>() ? "true" : "false"; break;
    case json::value_t::number_integer: out += std::to_string(value.get<int64_t>()); break;
    case json::value_t::number_unsigned: out += std::to_string(value.get<uint64_t>()); break;
    case json::value_t::number_float: out += python_float(value.get<double>()); break;
    case json::value_t::string: escape(out, value.get_ref<const std::string&>()); break;
    case json::value_t::array:
    {
        if (value.empty()) { out += "[]"; break; }
        out += '[';
        bool first = true;
        for (const auto& element : value)
        {
            if (!first)
                out += indent >= 0 ? "," : item;
            first = false;
            newline(depth + 1);
            dump(out, element, item, key, indent, depth + 1, limit);
        }
        newline(depth);
        out += ']';
        break;
    }
    case json::value_t::object:
    {
        if (value.empty()) { out += "{}"; break; }
        out += '{';
        bool first = true;
        // nlohmann's object is a std::map: byte order of UTF-8 keys is the
        // code point order Python's sort_keys uses.
        for (auto it = value.begin(); it != value.end(); ++it)
        {
            if (!first)
                out += indent >= 0 ? "," : item;
            first = false;
            newline(depth + 1);
            escape(out, it.key());
            out += key;
            dump(out, it.value(), item, key, indent, depth + 1, limit);
        }
        newline(depth);
        out += '}';
        break;
    }
    default: throw Invalid("invalid JSON state");
    }
}

std::string canonical(const json& value, size_t limit)
{
    std::string out;
    dump(out, value, ",", ":", -1, 0, limit + 1);
    if (out.size() > limit)
        throw Invalid("state exceeds size limit");
    return out;
}

std::string python_dumps(const json& value, bool, int indent)
{
    std::string out;
    dump(out, value, ", ", ": ", indent, 0, size_t(64) * 1024 * 1024);
    return out;
}

// -- strict JSON parser ------------------------------------------------------------
namespace
{
struct Parser
{
    const std::string& s;
    size_t i = 0;
    bool strict;
    int depth = 0;

    [[noreturn]] void fail() { throw Invalid("invalid JSON body"); }
    void ws() { while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) ++i; }
    bool eat(char c) { if (i < s.size() && s[i] == c) { ++i; return true; } return false; }

    static void utf8(std::string& out, uint32_t cp)
    {
        if (cp < 0x80) out += char(cp);
        else if (cp < 0x800) { out += char(0xC0 | (cp >> 6)); out += char(0x80 | (cp & 0x3F)); }
        else if (cp < 0x10000) { out += char(0xE0 | (cp >> 12)); out += char(0x80 | ((cp >> 6) & 0x3F)); out += char(0x80 | (cp & 0x3F)); }
        else { out += char(0xF0 | (cp >> 18)); out += char(0x80 | ((cp >> 12) & 0x3F)); out += char(0x80 | ((cp >> 6) & 0x3F)); out += char(0x80 | (cp & 0x3F)); }
    }

    uint32_t hex4()
    {
        if (i + 4 > s.size()) fail();
        uint32_t v = 0;
        for (int k = 0; k < 4; ++k)
        {
            char c = s[i++];
            v <<= 4;
            if (c >= '0' && c <= '9') v |= uint32_t(c - '0');
            else if (c >= 'a' && c <= 'f') v |= uint32_t(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') v |= uint32_t(c - 'A' + 10);
            else fail();
        }
        return v;
    }

    std::string string()
    {
        if (!eat('"')) fail();
        std::string out;
        while (true)
        {
            if (i >= s.size()) fail();
            unsigned char c = (unsigned char)s[i++];
            if (c == '"') break;
            if (c < 0x20) fail();  // json.loads strict=True
            if (c != '\\') { out += char(c); continue; }
            if (i >= s.size()) fail();
            char e = s[i++];
            switch (e)
            {
            case '"': out += '"'; break;
            case '\\': out += '\\'; break;
            case '/': out += '/'; break;
            case 'b': out += '\b'; break;
            case 'f': out += '\f'; break;
            case 'n': out += '\n'; break;
            case 'r': out += '\r'; break;
            case 't': out += '\t'; break;
            case 'u':
            {
                uint32_t cp = hex4();
                if (cp >= 0xD800 && cp <= 0xDBFF && i + 1 < s.size() && s[i] == '\\' && s[i + 1] == 'u')
                {
                    size_t save = i;
                    i += 2;
                    uint32_t low = hex4();
                    if (low >= 0xDC00 && low <= 0xDFFF)
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                    else
                        i = save;
                }
                if (cp >= 0xD800 && cp <= 0xDFFF) fail();  // lone surrogate: not UTF-8
                utf8(out, cp);
                break;
            }
            default: fail();
            }
        }
        // The body must be valid UTF-8 (Python decodes it before parsing).
        int need = 0;
        for (unsigned char c : out)
        {
            if (need) { if ((c & 0xC0) != 0x80) fail(); --need; }
            else if (c >= 0xF0 && c <= 0xF4) need = 3;
            else if (c >= 0xE0) need = 2;
            else if (c >= 0xC2 && c < 0xE0) need = 1;
            else if (c >= 0x80) fail();
        }
        if (need) fail();
        return out;
    }

    json number()
    {
        size_t start = i;
        eat('-');
        if (eat('0')) {}
        else if (i < s.size() && s[i] >= '1' && s[i] <= '9') { while (i < s.size() && isdigit((unsigned char)s[i])) ++i; }
        else fail();
        bool real = false;
        if (i < s.size() && s[i] == '.')
        {
            ++i;
            if (!(i < s.size() && isdigit((unsigned char)s[i]))) fail();
            while (i < s.size() && isdigit((unsigned char)s[i])) ++i;
            real = true;
        }
        if (i < s.size() && (s[i] == 'e' || s[i] == 'E'))
        {
            ++i;
            if (i < s.size() && (s[i] == '+' || s[i] == '-')) ++i;
            if (!(i < s.size() && isdigit((unsigned char)s[i]))) fail();
            while (i < s.size() && isdigit((unsigned char)s[i])) ++i;
            real = true;
        }
        std::string text = s.substr(start, i - start);
        if (real)
        {
            double v = std::strtod(text.c_str(), nullptr);
            if (!std::isfinite(v)) fail();  // Python gives inf; refused later as non-finite anyway
            return json(v);
        }
        if (text[0] == '-')
        {
            int64_t v = 0;
            auto r = std::from_chars(text.data(), text.data() + text.size(), v);
            if (r.ec != std::errc()) throw Invalid("integer outside supported bounds");
            return json(v);
        }
        uint64_t v = 0;
        auto r = std::from_chars(text.data(), text.data() + text.size(), v);
        if (r.ec != std::errc()) throw Invalid("integer outside supported bounds");
        if (v <= uint64_t(INT64_MAX)) return json(int64_t(v));
        return json(v);
    }

    json value()
    {
        if (++depth > 900) fail();
        ws();
        if (i >= s.size()) fail();
        json result;
        char c = s[i];
        if (c == '{')
        {
            ++i;
            result = json::object();
            ws();
            if (!eat('}'))
            {
                while (true)
                {
                    ws();
                    std::string key = string();
                    ws();
                    if (!eat(':')) fail();
                    json item = value();
                    if (result.contains(key))
                    {
                        if (strict) throw Invalid("duplicate JSON key");
                    }
                    result[key] = std::move(item);
                    ws();
                    if (eat(',')) continue;
                    if (eat('}')) break;
                    fail();
                }
            }
        }
        else if (c == '[')
        {
            ++i;
            result = json::array();
            ws();
            if (!eat(']'))
            {
                while (true)
                {
                    result.push_back(value());
                    ws();
                    if (eat(',')) continue;
                    if (eat(']')) break;
                    fail();
                }
            }
        }
        else if (c == '"') result = string();
        else if (s.compare(i, 4, "true") == 0) { i += 4; result = true; }
        else if (s.compare(i, 5, "false") == 0) { i += 5; result = false; }
        else if (s.compare(i, 4, "null") == 0) { i += 4; result = nullptr; }
        else if (c == '-' || (c >= '0' && c <= '9')) result = number();
        else fail();  // NaN, Infinity: parse_constant refuses them
        --depth;
        return result;
    }
};
} // namespace

json strict_json(const std::string& text)
{
    Parser p{ text, 0, true };
    json result = p.value();
    p.ws();
    if (p.i != text.size()) throw Invalid("invalid JSON body");
    return result;
}

json loads(const std::string& text)
{
    Parser p{ text, 0, false };
    json result = p.value();
    p.ws();
    if (p.i != text.size()) throw Invalid("invalid JSON state");
    return result;
}

// -- validators ----------------------------------------------------------------------
bool regex_full(const std::string& text, const char* pattern)
{
    return std::regex_match(text, std::regex(pattern));
}

static bool identifier_ok(const std::string& v)
{
    if (v.empty() || v.size() > 128) return false;
    for (unsigned char c : v)
        if (!(isalnum(c) || c == '_' || c == '.' || c == ':' || c == '-') || c >= 0x80) return false;
    return true;
}

const std::string& identifier(const json& value)
{
    if (!value.is_string() || !identifier_ok(value.get_ref<const std::string&>()))
        throw Invalid("invalid identifier");
    return value.get_ref<const std::string&>();
}

std::string identifier(const std::string& value)
{
    if (!identifier_ok(value)) throw Invalid("invalid identifier");
    return value;
}

static bool persistent_ok(const std::string& v)
{
    if (v.size() != 32) return false;
    for (char c : v)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

const std::string& persistent_id(const json& value)
{
    if (!value.is_string() || !persistent_ok(value.get_ref<const std::string&>()))
        throw Invalid("expected a 128-bit lowercase persistent ID");
    return value.get_ref<const std::string&>();
}

std::string persistent_id(const std::string& value)
{
    if (!persistent_ok(value)) throw Invalid("expected a 128-bit lowercase persistent ID");
    return value;
}

bool is_int(const json& value) { return value.is_number_integer(); }
bool is_number(const json& value) { return value.is_number(); }

int64_t as_int(const json& value)
{
    if (value.is_number_unsigned())
    {
        uint64_t v = value.get<uint64_t>();
        if (v > uint64_t(INT64_MAX)) throw Invalid("integer outside supported bounds");
        return int64_t(v);
    }
    if (!value.is_number_integer()) throw Invalid("expected an integer");
    return value.get<int64_t>();
}

double as_number(const json& value)
{
    if (!value.is_number()) throw Invalid("expected a number");
    return value.get<double>();
}

const std::string& as_string(const json& value)
{
    if (!value.is_string()) throw Invalid("expected a string");
    return value.get_ref<const std::string&>();
}

int64_t positive(int64_t value, const char* name)
{
    if (value <= 0) throw Invalid(std::string("invalid ") + name);
    return value;
}

int64_t positive(const json& value, const char* name)
{
    if (!value.is_number_integer() || (value.is_number_unsigned() && value.get<uint64_t>() > uint64_t(INT64_MAX)))
        throw Invalid(std::string("invalid ") + name);
    int64_t v = value.get<int64_t>();
    if (v <= 0) throw Invalid(std::string("invalid ") + name);
    return v;
}

double finite(double value, double low, double high)
{
    if (!std::isfinite(value) || !(low <= value && value <= high))
        throw Invalid("number is outside supported bounds");
    return value;
}

double finite(const json& value, double low, double high)
{
    if (!value.is_number()) throw Invalid("number is outside supported bounds");
    if (value.is_number_unsigned())
    {
        // Python compares the exact integer with the bounds.
        uint64_t v = value.get<uint64_t>();
        if (double(v) > high) throw Invalid("number is outside supported bounds");
    }
    return finite(value.get<double>(), low, high);
}

// -- crypto ----------------------------------------------------------------------------------
static std::string cng_hash(LPCWSTR algorithm, const std::string& key, const std::string& data, bool hmac)
{
    BCRYPT_ALG_HANDLE handle = nullptr;
    if (BCryptOpenAlgorithmProvider(&handle, algorithm, nullptr, hmac ? BCRYPT_ALG_HANDLE_HMAC_FLAG : 0) != 0)
        throw Unavailable("hash provider is unavailable");
    DWORD size = 0, written = 0;
    BCryptGetProperty(handle, BCRYPT_HASH_LENGTH, (PUCHAR)&size, sizeof(size), &written, 0);
    std::string out(size, '\0');
    NTSTATUS status = BCryptHash(handle, hmac ? (PUCHAR)key.data() : nullptr, hmac ? ULONG(key.size()) : 0,
                                 (PUCHAR)data.data(), ULONG(data.size()), (PUCHAR)out.data(), size);
    BCryptCloseAlgorithmProvider(handle, 0);
    if (status != 0) throw Unavailable("hash failed");
    return out;
}

std::string sha256_raw(const std::string& data) { return cng_hash(BCRYPT_SHA256_ALGORITHM, "", data, false); }
std::string sha1_raw(const std::string& data) { return cng_hash(BCRYPT_SHA1_ALGORITHM, "", data, false); }
std::string sha512_raw(const std::string& data) { return cng_hash(BCRYPT_SHA512_ALGORITHM, "", data, false); }
std::string sha256_hex(const std::string& data) { return hex(sha256_raw(data)); }
std::string hmac_sha256_hex(const std::string& key, const std::string& data)
{
    return hex(cng_hash(BCRYPT_SHA256_ALGORITHM, key, data, true));
}

std::string random_bytes(size_t count)
{
    std::string out(count, '\0');
    if (count && BCryptGenRandom(nullptr, (PUCHAR)out.data(), ULONG(count), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0)
        throw Unavailable("random source is unavailable");
    return out;
}

std::string hex(const std::string& raw)
{
    static const char* digits = "0123456789abcdef";
    std::string out;
    out.reserve(raw.size() * 2);
    for (unsigned char c : raw)
    {
        out += digits[c >> 4];
        out += digits[c & 15];
    }
    return out;
}

static std::string b64(const std::string& raw, const char* alphabet, bool pad)
{
    std::string out;
    size_t i = 0;
    for (; i + 2 < raw.size(); i += 3)
    {
        uint32_t v = (uint8_t(raw[i]) << 16) | (uint8_t(raw[i + 1]) << 8) | uint8_t(raw[i + 2]);
        out += alphabet[v >> 18]; out += alphabet[(v >> 12) & 63]; out += alphabet[(v >> 6) & 63]; out += alphabet[v & 63];
    }
    if (i + 1 == raw.size())
    {
        uint32_t v = uint8_t(raw[i]) << 16;
        out += alphabet[v >> 18]; out += alphabet[(v >> 12) & 63];
        if (pad) out += "==";
    }
    else if (i + 2 == raw.size())
    {
        uint32_t v = (uint8_t(raw[i]) << 16) | (uint8_t(raw[i + 1]) << 8);
        out += alphabet[v >> 18]; out += alphabet[(v >> 12) & 63]; out += alphabet[(v >> 6) & 63];
        if (pad) out += '=';
    }
    return out;
}

std::string base64(const std::string& raw)
{
    return b64(raw, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", true);
}

std::string base64_urlsafe_nopad(const std::string& raw)
{
    return b64(raw, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_", false);
}

bool base64_decode(const std::string& input, std::string& out, bool urlsafe)
{
    std::string text = input;
    if (urlsafe)
        for (char& c : text)
        {
            if (c == '-') c = '+';
            else if (c == '_') c = '/';
        }
    size_t pads = 0;
    while (pads < text.size() && text[text.size() - 1 - pads] == '=') ++pads;
    if (pads > 2) return false;
    size_t data = text.size() - pads;
    auto value = [](char c) -> int {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '+') return 62;
        if (c == '/') return 63;
        return -1;
    };
    for (size_t k = 0; k < data; ++k)
        if (value(text[k]) < 0) return false;
    // binascii: data length cannot be 1 more than a multiple of 4; padding required.
    if (data % 4 == 1 || text.size() % 4 != 0) return false;
    if ((data % 4 == 2 && pads != 2) || (data % 4 == 3 && pads != 1) || (data % 4 == 0 && pads != 0)) return false;
    out.clear();
    uint32_t buffer = 0;
    int bits = 0;
    for (size_t k = 0; k < data; ++k)
    {
        buffer = (buffer << 6) | uint32_t(value(text[k]));
        bits += 6;
        if (bits >= 8)
        {
            bits -= 8;
            out += char((buffer >> bits) & 0xFF);
        }
    }
    return true;
}

std::string token_urlsafe(size_t bytes) { return base64_urlsafe_nopad(random_bytes(bytes)); }
std::string token_hex(size_t bytes) { return hex(random_bytes(bytes)); }

std::string uuid4_hex()
{
    std::string raw = random_bytes(16);
    raw[6] = char((uint8_t(raw[6]) & 0x0F) | 0x40);
    raw[8] = char((uint8_t(raw[8]) & 0x3F) | 0x80);
    return hex(raw);
}

std::string uuid5_url_hex(const std::string& name)
{
    static const unsigned char ns[16] = { 0x6b, 0xa7, 0xb8, 0x11, 0x9d, 0xad, 0x11, 0xd1,
                                          0x80, 0xb4, 0x00, 0xc0, 0x4f, 0xd4, 0x30, 0xc8 };
    std::string raw = sha1_raw(std::string((const char*)ns, 16) + name).substr(0, 16);
    raw[6] = char((uint8_t(raw[6]) & 0x0F) | 0x50);
    raw[8] = char((uint8_t(raw[8]) & 0x3F) | 0x80);
    return hex(raw);
}

bool constant_time_equal(const std::string& a, const std::string& b)
{
    if (a.size() != b.size()) return false;
    unsigned char diff = 0;
    for (size_t i = 0; i < a.size(); ++i) diff |= (unsigned char)(a[i] ^ b[i]);
    return diff == 0;
}

// -- clocks ----------------------------------------------------------------------------------
int64_t monotonic_ns()
{
    static LARGE_INTEGER frequency = [] { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return f; }();
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return int64_t(double(now.QuadPart) * 1e9 / double(frequency.QuadPart));
}

int64_t wall_ms()
{
    FILETIME ft;
    GetSystemTimePreciseAsFileTime(&ft);
    ULARGE_INTEGER v;
    v.LowPart = ft.dwLowDateTime;
    v.HighPart = ft.dwHighDateTime;
    return int64_t((v.QuadPart - 116444736000000000ULL) / 10000ULL);
}

// -- text ------------------------------------------------------------------------------------------
std::string lower(std::string text)
{
    for (char& c : text)
        if (c >= 'A' && c <= 'Z') c = char(c - 'A' + 'a');
    return text;
}

std::string trim(const std::string& text)
{
    size_t a = 0, b = text.size();
    while (a < b && isspace((unsigned char)text[a])) ++a;
    while (b > a && isspace((unsigned char)text[b - 1])) --b;
    return text.substr(a, b - a);
}

std::vector<std::string> split(const std::string& text, char separator)
{
    std::vector<std::string> parts;
    size_t start = 0;
    while (true)
    {
        size_t at = text.find(separator, start);
        parts.push_back(text.substr(start, at == std::string::npos ? std::string::npos : at - start));
        if (at == std::string::npos) break;
        start = at + 1;
    }
    return parts;
}

int64_t parse_int(const std::string& input)
{
    std::string text = trim(input);
    std::string digits;
    size_t i = 0;
    bool negative = false;
    if (i < text.size() && (text[i] == '+' || text[i] == '-')) negative = text[i++] == '-';
    for (; i < text.size(); ++i)
    {
        char c = text[i];
        if (c >= '0' && c <= '9') digits += c;
        else if (c == '_' && !digits.empty() && i + 1 < text.size() && text[i + 1] >= '0' && text[i + 1] <= '9') continue;
        else throw Invalid("invalid literal for int()");
    }
    if (digits.empty()) throw Invalid("invalid literal for int()");
    uint64_t v = 0;
    auto r = std::from_chars(digits.data(), digits.data() + digits.size(), v);
    if (r.ec != std::errc() || v > uint64_t(INT64_MAX)) throw Invalid("integer outside supported bounds");
    return negative ? -int64_t(v) : int64_t(v);
}

std::string format(const char* fmt, ...)
{
    char buffer[4096];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    return buffer;
}

std::wstring widen(const std::string& text)
{
    if (text.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, 0, text.data(), int(text.size()), nullptr, 0);
    std::wstring out(size_t(n), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.data(), int(text.size()), out.data(), n);
    return out;
}

std::string narrow(const std::wstring& text)
{
    if (text.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, text.data(), int(text.size()), nullptr, 0, nullptr, nullptr);
    std::string out(size_t(n), '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.data(), int(text.size()), out.data(), n, nullptr, nullptr);
    return out;
}

static std::mutex s_log_lock;
static std::function<void(const std::string&)> s_log_sink;

void set_log_sink(std::function<void(const std::string&)> sink)
{
    std::lock_guard<std::mutex> guard(s_log_lock);
    s_log_sink = std::move(sink);
}

void log_line(const std::string& line)
{
    std::function<void(const std::string&)> sink;
    {
        std::lock_guard<std::mutex> guard(s_log_lock);
        sink = s_log_sink;
    }
    if (sink) sink(line);
    else OutputDebugStringW((widen(line) + L"\n").c_str());
}
} // namespace lzm
