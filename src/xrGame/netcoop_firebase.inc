// Included in netcoop.cpp after the local credential and device helpers.
// Network calls run on a worker; engine state and Lua are touched on the main thread.
using CloudJson = nlohmann::json;
static xr_string s_firebase_api, s_email_code_endpoint;
static bool s_firebase_config_loaded = false;
struct FirebaseSession
{
    std::string uid, email, username, refresh, id, pending_email;
    bool verified = false;
};
static FirebaseSession s_firebase_session;
static bool s_firebase_loaded = false;

static std::string cloud_string(const CloudJson& object, const char* key)
{
    const auto found = object.find(key);
    return found != object.end() && found->is_string() ? found->get<std::string>() : std::string();
}
static std::string cloud_convert(const std::string& value, UINT from, UINT to)
{
    if (value.empty()) return value;
    const int n = MultiByteToWideChar(from, 0, value.data(), int(value.size()), nullptr, 0);
    if (!n) return std::string();
    std::wstring wide(n, 0);
    MultiByteToWideChar(from, 0, value.data(), int(value.size()), &wide[0], n);
    const int bytes = WideCharToMultiByte(to, 0, wide.data(), n, nullptr, 0, nullptr, nullptr);
    std::string result(bytes, 0);
    if (bytes) WideCharToMultiByte(to, 0, wide.data(), n, &result[0], bytes, nullptr, nullptr);
    return result;
}
static bool firebase_enabled()
{
    if (!s_firebase_config_loaded)
    {
        s_firebase_config_loaded = true;
        string_path path;
        if (FS.exist(path, "$game_config$", "netcoop\\firebase.ltx"))
        {
            CInifile cfg(path, TRUE, TRUE, FALSE);
            if (cfg.line_exist("firebase", "api_key"))
            {
                LPCSTR value = cfg.r_string("firebase", "api_key");
                if (value) s_firebase_api = value;
            }
            // Legacy configurations can contain an empty code endpoint.
            // CInifile returns nullptr for an empty value; assigning it to a string crashes.
            if (cfg.line_exist("firebase", "code_endpoint"))
            {
                LPCSTR value = cfg.r_string("firebase", "code_endpoint");
                if (value) s_email_code_endpoint = value;
            }
        }
    }
    return s_firebase_api.size() > 20 && s_firebase_api.size() < 100;
}
static std::string cloud_form_encode(const std::string& value)
{
    static const char hex[] = "0123456789ABCDEF";
    std::string result;
    for (unsigned char c : value)
    {
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') result += char(c);
        else { result += '%'; result += hex[c >> 4]; result += hex[c & 15]; }
    }
    return result;
}
static bool cloud_http(LPCWSTR host, const std::wstring& path, const CloudJson& payload, CloudJson& result, std::string& error, bool form = false, bool contentRedirect = false, bool get = false)
{
    error = "NETWORK_ERROR";
    HINTERNET session = WinHttpOpen(L"LostZone/1.0", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
        WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) return false;
    WinHttpSetTimeouts(session, 8000, 8000, 15000, contentRedirect ? 45000 : 15000);
    HINTERNET connection = WinHttpConnect(session, host, INTERNET_DEFAULT_HTTPS_PORT, 0);
    HINTERNET request = connection ? WinHttpOpenRequest(connection, get ? L"GET" : L"POST", path.c_str(), nullptr,
        WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE) : nullptr;
    bool ok = false;
    if (request)
    {
        // Never follow an API redirect with a credential-bearing request.
        DWORD redirect = WINHTTP_OPTION_REDIRECT_POLICY_NEVER;
        WinHttpSetOption(request, WINHTTP_OPTION_REDIRECT_POLICY, &redirect, sizeof(redirect));
        std::string body = get ? std::string() : form ? "grant_type=refresh_token&refresh_token=" + cloud_form_encode(cloud_string(payload, "refresh_token")) : payload.dump();
        LPCWSTR headers = form ? L"Content-Type: application/x-www-form-urlencoded\r\n" : L"Content-Type: application/json\r\nX-Firebase-Locale: ru\r\n";
        if (WinHttpSendRequest(request, headers, DWORD(-1),
            body.empty() ? WINHTTP_NO_REQUEST_DATA : &body[0], DWORD(body.size()), DWORD(body.size()), 0) &&
            WinHttpReceiveResponse(request, nullptr))
        {
            DWORD status = 0, size = sizeof(status);
            WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX);
            if (contentRedirect && (status == 302 || status == 303))
            {
                // Apps Script redirects only the response. Never resend the
                // credential-bearing POST body or headers to its content host.
                wchar_t location[4096] = {}; DWORD bytes = sizeof(location);
                const std::wstring prefix = L"https://script.googleusercontent.com/";
                if (WinHttpQueryHeaders(request, WINHTTP_QUERY_LOCATION, WINHTTP_HEADER_NAME_BY_INDEX,
                    location, &bytes, WINHTTP_NO_HEADER_INDEX))
                {
                    const std::wstring url = location;
                    if (url.compare(0, prefix.size(), prefix) == 0 && url.find_first_of(L"\r\n") == std::wstring::npos)
                    {
                        if (!body.empty()) SecureZeroMemory(&body[0], body.size());
                        WinHttpCloseHandle(request); WinHttpCloseHandle(connection); WinHttpCloseHandle(session);
                        return cloud_http(L"script.googleusercontent.com", url.substr(prefix.size()-1),
                            CloudJson::object(), result, error, false, false, true);
                    }
                }
            }
            std::string response;
            char buffer[8192]; DWORD got = 0;
            bool complete = true;
            do
            {
                if (!WinHttpReadData(request, buffer, sizeof(buffer), &got)) { complete = false; break; }
                response.append(buffer, got);
                if (response.size() > 128 * 1024) { complete = false; break; }
            } while (got);
            if (complete)
            {
                result = CloudJson::parse(response, nullptr, false);
                if (result.is_object())
                {
                    ok = status == 200;
                    if (ok) error.clear();
                    if (!ok && result.contains("error") && result["error"].is_object())
                        error = cloud_string(result["error"], "message");
                    if (!ok && error.empty()) error = "INVALID_RESPONSE";
                }
            }
        }
        if (!body.empty()) SecureZeroMemory(&body[0], body.size());
        WinHttpCloseHandle(request);
    }
    if (connection) WinHttpCloseHandle(connection);
    WinHttpCloseHandle(session);
    return ok;
}
static bool email_code_path(const std::string& endpoint, std::wstring& path)
{
    const std::string prefix = "https://script.google.com/macros/s/", suffix = "/exec";
    if (endpoint.compare(0, prefix.size(), prefix) != 0 || endpoint.size() > 512 ||
        endpoint.size() <= prefix.size()+suffix.size() || endpoint.compare(endpoint.size()-suffix.size(), suffix.size(), suffix) != 0) return false;
    const auto deployment = endpoint.substr(prefix.size(), endpoint.size()-prefix.size()-suffix.size());
    for (unsigned char c : deployment)
        if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_')) return false;
    const std::string relative = "/macros/s/"+deployment+"/exec";
    path.assign(relative.begin(), relative.end()); return true;
}
static bool email_code_call(const std::string& endpoint, const std::string& action,
    const std::string& token, const std::string& code, std::string& error)
{
    std::wstring path;
    if (!email_code_path(endpoint, path)) { error = "CODE_SERVICE_NOT_CONFIGURED"; return false; }
    CloudJson payload = {{"action",action},{"idToken",token}}, response;
    if (action == "verify") payload["code"] = code;
    if (!cloud_http(L"script.google.com",path,payload,response,error,false,true)) return false;
    if (!response.contains("ok") || !response["ok"].is_boolean()) { error = "INVALID_RESPONSE"; return false; }
    if (!response["ok"].get<bool>()) { error = cloud_string(response,"error"); if(error.empty()) error = "SERVICE_ERROR"; return false; }
    error.clear(); return true;
}
static bool firebase_call(const char* action, const CloudJson& payload, CloudJson& result, std::string& error, const std::string& api)
{
    const std::string path = std::string("/v1/accounts:") + action + "?key=" + api;
    return cloud_http(L"identitytoolkit.googleapis.com", std::wstring(path.begin(), path.end()), payload, result, error);
}
static bool firebase_lookup(const std::string& token, const std::string& api, FirebaseSession& session, std::string& error)
{
    CloudJson response;
    if (!firebase_call("lookup", {{"idToken", token}}, response, error, api)) return false;
    if (!response.contains("users") || !response["users"].is_array() || response["users"].size() != 1) return false;
    const auto& user = response["users"][0];
    if (!user.is_object()) return false;
    session.uid = cloud_string(user, "localId"); session.email = cloud_string(user, "email");
    session.username = cloud_string(user, "displayName");
    session.verified = user.contains("emailVerified") && user["emailVerified"].is_boolean() && user["emailVerified"].get<bool>();
    session.id = token;
    return !session.uid.empty() && !session.email.empty();
}
static bool cloud_secret_file(const char* filename, CloudJson& value, bool write)
{
    string_path path; FS.update_path(path, "$app_data_root$", filename);
    if (write)
    {
        std::string plain = value.dump();
        DATA_BLOB input = {DWORD(plain.size()), (BYTE*)plain.data()}, encrypted = {};
        if (!CryptProtectData(&input, L"Lost Zone Firebase", nullptr, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &encrypted)) return false;
        string_path temporary; xr_sprintf(temporary, "%s.tmp", path);
        FILE* file = fopen(temporary, "wb");
        bool ok = file && fwrite(encrypted.pbData, 1, encrypted.cbData, file) == encrypted.cbData;
        if (file && fclose(file)) ok = false;
        LocalFree(encrypted.pbData); SecureZeroMemory(&plain[0], plain.size());
        return ok && MoveFileExA(temporary, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    }
    FILE* file = fopen(path, "rb"); if (!file) return false;
    fseek(file, 0, SEEK_END); const long size = ftell(file); rewind(file);
    if (size <= 0 || size > 64 * 1024) { fclose(file); return false; }
    std::string data(size, 0);
    const bool read = fread(&data[0], 1, size, file) == size; fclose(file); if (!read) return false;
    DATA_BLOB input = {DWORD(size), (BYTE*)data.data()}, plain = {};
    if (!CryptUnprotectData(&input, nullptr, nullptr, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &plain)) return false;
    value = CloudJson::parse(plain.pbData, plain.pbData + plain.cbData, nullptr, false);
    SecureZeroMemory(plain.pbData, plain.cbData); LocalFree(plain.pbData);
    return value.is_object();
}
static void firebase_load()
{
    if (s_firebase_loaded) return;
    s_firebase_loaded = true;
    if (!firebase_enabled()) return;
    CloudJson data;
    if (!cloud_secret_file("netcoop_firebase.bin", data, false)) return;
    if (cloud_string(data, "project") != "lostzoneapi") return;
    s_firebase_session.uid = cloud_string(data, "uid"); s_firebase_session.email = cloud_string(data, "email");
    s_firebase_session.username = cloud_string(data, "username"); s_firebase_session.refresh = cloud_string(data, "refresh");
    s_firebase_session.pending_email = cloud_string(data, "pending_email");
    s_firebase_session.verified = data.contains("verified") && data["verified"].is_boolean() && data["verified"].get<bool>();
    if (!s_firebase_session.pending_email.empty()) s_firebase_session.verified = false;
}
static bool firebase_email_valid(const std::string& email)
{
    if (email.size() > 254) return false;
    const auto at = email.find('@');
    if (at == std::string::npos || at == 0 || at > 64 || email.find('@', at + 1) != std::string::npos) return false;
    if (email.front() == '.' || email[at - 1] == '.' || email.substr(0, at).find("..") != std::string::npos) return false;
    for (size_t i = 0; i < at; ++i)
    {
        const unsigned char c = email[i];
        const bool alnum = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
        if (!alnum && std::string(".!#$%&'*+-/=?^_`{|}~").find(char(c)) == std::string::npos) return false;
    }
    const std::string domain = email.substr(at + 1);
    if (domain.empty() || domain.find('.') == std::string::npos) return false;
    size_t start = 0;
    while (start < domain.size())
    {
        auto end = domain.find('.', start); if (end == std::string::npos) end = domain.size();
        if (end == start || end - start > 63 || domain[start] == '-' || domain[end - 1] == '-') return false;
        for (size_t i = start; i < end; ++i)
        {
            const unsigned char c = domain[i];
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-')) return false;
        }
        if (end == domain.size()) return true;
        start = end + 1;
    }
    return false;
}
static bool firebase_email_domain(const std::string& email, std::string& error)
{
    if (!firebase_email_valid(email)) { error = "INVALID_EMAIL"; return false; }
    const auto domain = email.substr(email.find('@') + 1);
    const std::wstring name(domain.begin(), domain.end());
    PDNS_RECORDW records = nullptr;
    const DWORD options = DNS_QUERY_STANDARD | DNS_QUERY_TREAT_AS_FQDN;
    DNS_STATUS status = DnsQuery_W(name.c_str(), DNS_TYPE_MX, options, nullptr, &records, nullptr);
    bool mx = false, null_mx = false;
    for (auto record = records; record; record = record->pNext)
    {
        if (record->wType != DNS_TYPE_MX) continue;
        const auto exchange = record->Data.MX.pNameExchange;
        if (exchange && *exchange && wcscmp(exchange, L".") != 0) mx = true;
        else null_mx = true;
    }
    if (records) DnsRecordListFree(reinterpret_cast<PDNS_RECORD>(records), DnsFreeRecordList);
    if (status == ERROR_SUCCESS && mx) return true;
    if (status == DNS_ERROR_RCODE_NAME_ERROR || (status == ERROR_SUCCESS && null_mx))
    { error = "EMAIL_DOMAIN_NOT_FOUND"; return false; }
    if (status != ERROR_SUCCESS && status != DNS_INFO_NO_RECORDS) { error = "NETWORK_ERROR"; return false; }
    // RFC 5321 permits A/AAAA delivery when the domain has no MX records.
    bool temporary_failure = false;
    for (WORD type : {WORD(DNS_TYPE_A), WORD(DNS_TYPE_AAAA)})
    {
        records = nullptr;
        status = DnsQuery_W(name.c_str(), type, options, nullptr, &records, nullptr);
        bool address = false;
        for (auto record = records; record; record = record->pNext) if (record->wType == type) address = true;
        if (records) DnsRecordListFree(reinterpret_cast<PDNS_RECORD>(records), DnsFreeRecordList);
        if (status == ERROR_SUCCESS && address) return true;
        if (status != ERROR_SUCCESS && status != DNS_INFO_NO_RECORDS && status != DNS_ERROR_RCODE_NAME_ERROR) temporary_failure = true;
    }
    error = temporary_failure ? "NETWORK_ERROR" : "EMAIL_DOMAIN_NOT_FOUND";
    return false;
}
struct FirebaseTask
{
    std::string action, email, password, username, api, endpoint, error;
    FirebaseSession session;
    bool ok = false, session_ready = false;
    volatile LONG done = 0;
};
static FirebaseTask* s_firebase_task = nullptr;
static void firebase_worker(void* argument)
{
    FirebaseTask* task = static_cast<FirebaseTask*>(argument);
    CloudJson response; bool ok = false;
    if ((task->action == "register" || task->action == "change_email") && !firebase_email_domain(task->email, task->error))
    {
        if (!task->password.empty()) SecureZeroMemory(&task->password[0],task->password.size());
        task->password.clear(); InterlockedExchange(&task->done,1); return;
    }
    if (task->action == "register" || task->action == "login")
    {
        ok = firebase_call(task->action == "register" ? "signUp" : "signInWithPassword",
            {{"email",task->email},{"password",task->password},{"returnSecureToken",true}},response,task->error,task->api);
        if (ok)
        {
            task->session.id = cloud_string(response,"idToken"); task->session.refresh = cloud_string(response,"refreshToken");
            if (task->action == "register")
            {
                ok = firebase_call("update",{{"idToken",task->session.id},{"displayName",task->username},{"returnSecureToken",true}},response,task->error,task->api);
                if (ok)
                {
                    const auto id = cloud_string(response,"idToken"), refresh = cloud_string(response,"refreshToken");
                    if (!id.empty()) task->session.id = id;
                    if (!refresh.empty()) task->session.refresh = refresh;
                }
            }
        }
    }
    else if (task->action == "reset")
    {
        task->ok = firebase_call("sendOobCode",{{"requestType","PASSWORD_RESET"},{"email",task->email}},response,task->error,task->api);
        InterlockedExchange(&task->done,1); return;
    }
    else if (!task->session.refresh.empty())
    {
        const std::string path = "/v1/token?key="+task->api;
        ok = cloud_http(L"securetoken.googleapis.com",std::wstring(path.begin(),path.end()),
            {{"grant_type","refresh_token"},{"refresh_token",task->session.refresh}},response,task->error,true);
        if (ok)
        {
            task->session.id = cloud_string(response,"id_token");
            const auto refresh = cloud_string(response,"refresh_token"); if(!refresh.empty()) task->session.refresh = refresh;
        }
    }
    const auto previous_uid = task->session.uid;
    if (ok) ok = firebase_lookup(task->session.id,task->api,task->session,task->error);
    if (ok && (task->action == "register" || task->action == "login") && task->session.uid != previous_uid) task->session.pending_email.clear();
    if (ok && !task->session.pending_email.empty())
    {
        if (task->session.verified && _stricmp(task->session.email.c_str(),task->session.pending_email.c_str()) == 0) task->session.pending_email.clear();
        else task->session.verified = false;
    }
    if (ok && !login_valid(task->session.username.c_str())) { ok = false; task->error = "ACCOUNT_NAME_REQUIRED"; }
    task->session_ready = ok;
    if (ok && task->action == "change_email" && !task->session.verified)
    {
        // Verify the new address before changing it; supported with email
        // enumeration protection, unlike a direct accounts:update email.
        ok = firebase_call("sendOobCode", {{"requestType","VERIFY_AND_CHANGE_EMAIL"},
            {"idToken",task->session.id},{"newEmail",task->email}}, response,task->error,task->api);
        if (ok)
        {
            task->session.pending_email = task->email; task->session.verified = false;
        }
        task->ok = ok; InterlockedExchange(&task->done,1); return;
    }
    if (ok && !task->session.verified)
    {
        if (task->action == "verify")
        {
            // The link is applied by Firebase's hosted email action page.
            // Only the fresh lookup above can establish verified ownership.
            ok = false; task->error = "EMAIL_NOT_VERIFIED";
        }
        else if (task->action == "register" || task->action == "login" || task->action == "resend")
        {
            CloudJson mail = {{"requestType","VERIFY_EMAIL"},{"idToken",task->session.id}};
            if (!task->session.pending_email.empty())
            { mail["requestType"] = "VERIFY_AND_CHANGE_EMAIL"; mail["newEmail"] = task->session.pending_email; }
            const bool sent = firebase_call("sendOobCode",
                mail,
                response,task->error,task->api);
            // Account creation/login remains saved if delivery fails: users can resend.
            if (task->action == "resend") ok = sent;
        }
    }
    if (!task->password.empty()) SecureZeroMemory(&task->password[0],task->password.size());
    task->password.clear(); task->ok=ok; InterlockedExchange(&task->done,1);
}
bool script_firebase_request(LPCSTR action, LPCSTR email, LPCSTR password, LPCSTR username)
{
    firebase_load();
    if (!firebase_enabled() || s_firebase_task || !action || !email || !password || !username) return false;
    const std::string operation = action;
    if (operation != "register" && operation != "login" && operation != "refresh" && operation != "resend" && operation != "reset" && operation != "verify" && operation != "change_email") return false;
    if ((operation == "register" || operation == "login") && (xr_strlen(password) < 6 || xr_strlen(password) > 128)) return false;
    if (operation == "verify" && *password) return false;
    if (operation == "register" && !login_valid(username)) return false;
    if (xr_strlen(email) > 254) return false;
    if ((operation == "register" || operation == "login" || operation == "reset" || operation == "change_email") && !firebase_email_valid(email)) return false;
    if (operation == "change_email" && (s_firebase_session.refresh.empty() || *password)) return false;
    auto task = xr_new<FirebaseTask>();
    task->action = operation; task->email = email; task->password = cloud_convert(password, 1251, CP_UTF8); task->username = username;
    task->api = s_firebase_api.c_str(); task->endpoint = s_email_code_endpoint.c_str(); task->session = s_firebase_session;
    s_firebase_task = task;
    thread_spawn(firebase_worker, "firebase-account", 0, task);
    return true;
}
int script_firebase_state()
{
    firebase_load();
    return s_firebase_session.refresh.empty() ? 0 : s_firebase_session.verified ? 2 : 1;
}
LPCSTR script_firebase_identity()
{
    firebase_load(); static xr_string result; result.clear();
    const auto& uid=s_firebase_session.uid; u8 digest[16];
    if(!uid.empty() && pbkdf2(uid.data(),u32(uid.size()),"menu-cache",10,1,digest,sizeof(digest)))
        result=to_hex(digest,sizeof(digest));
    return result.c_str();
}
LPCSTR script_firebase_email() { firebase_load(); return s_firebase_session.pending_email.empty() ? s_firebase_session.email.c_str() : s_firebase_session.pending_email.c_str(); }
LPCSTR script_firebase_account() { firebase_load(); return s_firebase_session.username.c_str(); }
void firebase_frame()
{
    if (!s_firebase_task || !InterlockedCompareExchange(&s_firebase_task->done, 0, 0)) return;
    FirebaseTask* task = s_firebase_task; s_firebase_task = nullptr;
    if (task->session_ready && task->action != "reset")
    {
        if (s_firebase_session.uid != task->session.uid) s_client_role = role_none;
        s_firebase_session = task->session;
        CloudJson stored = {{"project", "lostzoneapi"}, {"uid", task->session.uid}, {"email", task->session.email},
            {"username", task->session.username}, {"refresh", task->session.refresh}, {"verified", task->session.verified}, {"pending_email",task->session.pending_email}};
        if (!cloud_secret_file("netcoop_firebase.bin", stored, true) && task->error.empty()) task->error = "REMEMBER_FAILED";
    }
    ::luabind::functor<void> callback;
    if (ai().script_engine().functor("netcoop_login_ui.on_cloud_result", callback))
        callback(task->ok, task->error.c_str(), s_firebase_session.username.c_str(), s_firebase_session.verified);
    xr_delete(task);
}
