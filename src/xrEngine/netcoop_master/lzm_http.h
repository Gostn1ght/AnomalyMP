// A small HTTP/1.1 server over WinSock for the master's private API (loopback,
// http.py) and the players' public entry (gateway.py). One request per
// connection, "Connection: close", bounded headers and bodies.
#pragma once
#include "lzm_common.h"

#include <atomic>
#include <thread>

namespace lzm
{
struct HttpRequest
{
    std::string method, target, path, query, address;
    std::vector<std::pair<std::string, std::string>> headers;  // names lower-case
    std::string body;
    bool body_read = false;
    std::vector<std::string> all(const std::string& name) const;
    std::optional<std::string> header(const std::string& name) const;
    std::string content_type() const;  // email.message get_content_type()
};

struct HttpResponse
{
    int status = 200;
    std::string body;
    std::string content_type = "application/json; charset=utf-8";
};

// The handler reads the body itself (http.py checks the headers first).
using HttpHandler = std::function<HttpResponse(HttpRequest&, const std::function<bool(size_t)>& read_body)>;

class HttpServer
{
public:
    // `workers`: concurrent requests; one more is answered 503 without work.
    HttpServer(const std::string& bind_address, int port, size_t workers, HttpHandler handler, bool http11 = true,
               const char* server_name = "LostZoneWorld/1");
    ~HttpServer();
    void stop();
    int port() const { return port_; }

private:
    uintptr_t socket_ = ~uintptr_t(0);
    int port_ = 0;
    size_t workers_;
    std::atomic<size_t> busy_{ 0 };
    std::atomic<bool> stopping_{ false };
    HttpHandler handler_;
    bool http11_;
    std::string server_name_;
    std::thread accept_;
    std::mutex threads_lock_;
    std::vector<std::thread> threads_;
    void loop();
    void serve(uintptr_t client, std::string address);
};

// urllib.parse.parse_qs(query, strict_parsing=True, keep_blank_values=...)
std::map<std::string, std::vector<std::string>> parse_qs(const std::string& query, bool keep_blank, int max_fields = -1);
const char* http_reason(int status);
} // namespace lzm
