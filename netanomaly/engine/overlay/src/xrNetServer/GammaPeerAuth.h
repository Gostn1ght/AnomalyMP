#pragma once
#include <ctime>
#include <filesystem>
#include <fstream>
#include <string>

namespace gamma_net
{
inline bool account_is_admin(const std::filesystem::path& directory, const std::string& account);
inline bool hex_identity(const std::string& value, std::size_t size)
{
    if (value.size() != size) return false;
    for (char c : value)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

inline std::string read_client_ticket(const std::filesystem::path& file)
{
    std::error_code error;
    if (std::filesystem::file_size(file, error) > 66 || error) return {};
    std::ifstream input(file);
    std::string token, extra;
    std::getline(input, token);
    if (!token.empty() && token.back() == '\r') token.pop_back();
    if (!hex_identity(token, 64) || std::getline(input, extra)) return {};
    return token;
}

struct peer_ticket
{
    std::string account;
    std::filesystem::path issued;
    std::filesystem::path consumed;
};

inline bool inspect_ticket(const std::filesystem::path& directory,
                           const std::string& token, const std::string& client_content,
                           const std::string& server_content, std::time_t now, peer_ticket& result)
{
    if (!hex_identity(token, 64) || !hex_identity(server_content, 64) || client_content != server_content)
        return false;
    const auto file = directory / (token + ".ticket");
    std::error_code error;
    if (std::filesystem::file_size(file, error) > 256 || error) return false;
    std::ifstream input(file);
    std::string magic, account, content, expires, extra;
    if (!std::getline(input, magic) || !std::getline(input, account) ||
        !std::getline(input, content) || !std::getline(input, expires)) return false;
    for (auto* line : {&magic, &account, &content, &expires})
        if (!line->empty() && line->back() == '\r') line->pop_back();
    if (magic != "GAMMA_AUTH_V3" || !hex_identity(account, 32) || content != server_content ||
        expires.empty() || expires.size() > 12 || std::getline(input, extra)) return false;
    unsigned long long expiry = 0;
    for (char c : expires)
    {
        if (c < '0' || c > '9') return false;
        expiry = expiry * 10 + unsigned(c - '0');
    }
    if (now < 0 || expiry <= static_cast<unsigned long long>(now) ||
        expiry > static_cast<unsigned long long>(now) + 300) return false;
    result.account = account;
    result.issued = file;
    result.consumed = directory / (token + ".used");
    return true;
}

inline bool consume_ticket(const peer_ticket& ticket)
{
    std::error_code error;
    if (std::filesystem::exists(ticket.consumed, error) || error) return false;
    std::filesystem::rename(ticket.issued, ticket.consumed, error);
    return !error;
}

inline bool account_is_admin(const std::filesystem::path& directory, const std::string& account)
{
    if (!hex_identity(account, 32)) return false;
    const auto file = directory / (account + ".role");
    std::error_code error;
    if (std::filesystem::file_size(file, error) > 128 || error) return false;
    std::ifstream input(file);
    std::string magic, identity, role, extra;
    if (!std::getline(input, magic) || !std::getline(input, identity) || !std::getline(input, role)) return false;
    for (auto* line : {&magic, &identity, &role})
        if (!line->empty() && line->back() == '\r') line->pop_back();
    return magic == "GAMMA_ROLE_V3" && identity == account && role == "admin" && !std::getline(input, extra);
}
}
