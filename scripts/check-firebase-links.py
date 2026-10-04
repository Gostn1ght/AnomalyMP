"""Compile the actual Firebase worker/request code with fake HTTPS on GitHub only."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
source = (root/'src/xrGame/netcoop_firebase.inc').read_text()
def section(start, end):
    return source[source.index(start):source.index(end, source.index(start))]

fixture = r'''
#include <cassert>
#include <cstring>
#include <cwchar>
#include <strings.h>
#include <string>
#include <vector>
#include <json.hpp>
using CloudJson = nlohmann::json;
using LPCSTR = const char*;
using LONG = long;
using DWORD = unsigned long;
using WORD = unsigned short;
using DNS_STATUS = long;
#define _stricmp strcasecmp
const DNS_STATUS ERROR_SUCCESS=0, DNS_INFO_NO_RECORDS=9501, DNS_ERROR_RCODE_NAME_ERROR=9003;
const WORD DNS_TYPE_A=1, DNS_TYPE_MX=15, DNS_TYPE_AAAA=28;
const DWORD DNS_QUERY_STANDARD=0, DNS_QUERY_TREAT_AS_FQDN=4096;
const int DnsFreeRecordList=1;
struct DNS_RECORDW { DNS_RECORDW* pNext=nullptr; WORD wType=0; struct { struct { const wchar_t* pNameExchange=nullptr; } MX; } Data; };
using PDNS_RECORDW=DNS_RECORDW*;
using PDNS_RECORD=DNS_RECORDW*;
DNS_STATUS mx_status=ERROR_SUCCESS, a_status=DNS_INFO_NO_RECORDS, aaaa_status=DNS_INFO_NO_RECORDS;
bool null_mx=false;
std::vector<WORD> dns_calls;
DNS_STATUS DnsQuery_W(const wchar_t* name, WORD type, DWORD options, void*, PDNS_RECORDW* records, void*) {
    assert(std::wstring(name).find(L'@')==std::wstring::npos && options==DNS_QUERY_TREAT_AS_FQDN);
    dns_calls.push_back(type);
    auto status=type==DNS_TYPE_MX?mx_status:type==DNS_TYPE_A?a_status:aaaa_status;
    *records=nullptr;
    if(status==ERROR_SUCCESS) { *records=new DNS_RECORDW; (*records)->wType=type; (*records)->Data.MX.pNameExchange=null_mx?L".":L"mx.example.invalid"; }
    return status;
}
void DnsRecordListFree(PDNS_RECORD records, int) { delete records; }
const unsigned CP_UTF8 = 65001;
long InterlockedExchange(volatile long* value, long next) { long old=*value; *value=next; return old; }
void SecureZeroMemory(void* value, size_t count) { std::memset(value, 0, count); }
bool login_valid(LPCSTR value) { size_t n=std::strlen(value); return n>=3 && n<=20; }
struct Call { std::string action; CloudJson payload; };
std::vector<Call> calls;
bool fresh_verified=false, send_ok=true, refresh_ok=true, lookup_ok=true;
std::string send_error="TOO_MANY_ATTEMPTS_TRY_LATER";
std::string fresh_email="registered@example.invalid";
bool firebase_call(const char* action, const CloudJson& payload, CloudJson& response, std::string& error, const std::string&) {
    calls.push_back({action,payload}); error.clear();
    response={{"idToken","fresh-id"},{"refreshToken","fresh-refresh"}};
    if (std::string(action)=="sendOobCode") {
        if (payload["requestType"]=="VERIFY_EMAIL" || payload["requestType"]=="VERIFY_AND_CHANGE_EMAIL") {
            assert(payload["idToken"]=="fresh-id" && !payload.contains("email"));
            if(payload["requestType"]=="VERIFY_AND_CHANGE_EMAIL") assert(payload["newEmail"].is_string());
            if (!send_ok) { error=send_error; return false; }
        } else assert(payload["requestType"]=="PASSWORD_RESET");
    }
    return true;
}
bool cloud_http(const wchar_t* host, const std::wstring&, const CloudJson& payload, CloudJson& response, std::string& error, bool form) {
    assert(std::wstring(host)==L"securetoken.googleapis.com" && form);
    calls.push_back({"refresh-token",payload});
    if (!refresh_ok) { error="INVALID_REFRESH_TOKEN"; return false; }
    response={{"id_token","fresh-id"},{"refresh_token","fresh-refresh"}}; error.clear(); return true;
}
'''
fixture += section('struct FirebaseSession', 'static FirebaseSession')
fixture += section('static std::string cloud_string', 'static std::string cloud_convert')
fixture += r'''
bool firebase_lookup(const std::string& token, const std::string&, FirebaseSession& session, std::string& error) {
    calls.push_back({"lookup",{{"idToken",token}}}); assert(token=="fresh-id");
    if (!lookup_ok) { error="NETWORK_ERROR"; return false; }
    session.uid="uid-one"; session.email=fresh_email; session.username="account-one";
    session.verified=fresh_verified; error.clear(); return true;
}
void firebase_load() {}
bool firebase_enabled() { return true; }
std::string s_firebase_api="test-public-api", s_email_code_endpoint;
FirebaseSession s_firebase_session;
std::string cloud_convert(const std::string& value, unsigned, unsigned) { return value; }
size_t xr_strlen(LPCSTR value) { return std::strlen(value); }
template<typename T> T* xr_new() { return new T; }
int spawned=0;
void thread_spawn(void(*)(void*), LPCSTR, int, void*) { ++spawned; }
'''
fixture += section('static bool firebase_email_valid', 'int script_firebase_state()')
fixture += r'''
void reset() { calls.clear(); dns_calls.clear(); fresh_email="registered@example.invalid"; fresh_verified=false; send_ok=refresh_ok=lookup_ok=true; mx_status=ERROR_SUCCESS; a_status=aaaa_status=DNS_INFO_NO_RECORDS; null_mx=false; }
FirebaseTask task(const char* action) {
    FirebaseTask t; t.action=action; t.api="test-public-api"; t.email="registered@example.invalid";
    t.username="account-one"; t.session.refresh="cached-refresh"; t.session.id="cached-id";
    return t;
}
int count(const char* action) { int n=0; for (auto& call:calls) if(call.action==action) ++n; return n; }
int main() {
    // Registration works with no Apps Script endpoint and sends a token-bound Firebase link.
    auto t=task("register"); t.password="test-password"; firebase_worker(&t);
    assert(t.ok && t.session_ready && !t.session.verified && t.done==1 && t.password.empty());
    assert(count("signUp")==1 && count("update")==1 && count("sendOobCode")==1);
    // Clicking Continue cannot turn an unverified cached account into a verified one.
    reset(); t=task("verify"); t.session.verified=true; firebase_worker(&t);
    assert(!t.ok && t.session_ready && !t.session.verified && t.error=="EMAIL_NOT_VERIFIED");
    assert(count("refresh-token")==1 && count("lookup")==1 && count("sendOobCode")==0);
    // Confirmation must come from a fresh Google lookup, without sending another email.
    reset(); fresh_verified=true; t=task("verify"); firebase_worker(&t);
    assert(t.ok && t.session.verified && t.error.empty() && count("sendOobCode")==0);
    reset(); fresh_verified=true; t=task("login"); t.password="test-password"; firebase_worker(&t);
    assert(t.ok && t.session.verified && count("sendOobCode")==0 && count("signUp")==0);
    // Failed delivery retains the account session so a user can retry without registering twice.
    reset(); send_ok=false; t=task("register"); t.password="test-password"; firebase_worker(&t);
    assert(t.ok && t.session_ready && t.error==send_error && t.password.empty());
    reset(); send_ok=false; t=task("resend"); firebase_worker(&t);
    assert(!t.ok && t.session_ready && t.error==send_error && count("signUp")==0);
    reset(); t=task("resend"); firebase_worker(&t);
    assert(t.ok && !t.session.verified && count("sendOobCode")==1);
    // Expired tokens and unreachable lookup must not accept the cached verified flag.
    reset(); refresh_ok=false; t=task("verify"); t.session.verified=true; firebase_worker(&t);
    assert(!t.ok && !t.session_ready && t.error=="INVALID_REFRESH_TOKEN" && count("sendOobCode")==0);
    reset(); lookup_ok=false; t=task("verify"); t.session.verified=true; firebase_worker(&t);
    assert(!t.ok && !t.session_ready && t.error=="NETWORK_ERROR");
    reset(); t=task("reset"); firebase_worker(&t);
    assert(t.ok && !t.session_ready && count("sendOobCode")==1 && count("lookup")==0);
    // Bad domains, Null MX, DNS outages and invalid syntax never create accounts.
    reset(); mx_status=DNS_ERROR_RCODE_NAME_ERROR; t=task("register");t.password="test-password";firebase_worker(&t);
    assert(!t.ok && t.error=="EMAIL_DOMAIN_NOT_FOUND" && calls.empty() && t.password.empty());
    reset(); null_mx=true; a_status=ERROR_SUCCESS; t=task("register");firebase_worker(&t);
    assert(!t.ok && t.error=="EMAIL_DOMAIN_NOT_FOUND" && calls.empty() && dns_calls.size()==1);
    reset(); mx_status=1234;t=task("register");firebase_worker(&t);
    assert(!t.ok && t.error=="NETWORK_ERROR" && calls.empty());
    reset();mx_status=DNS_INFO_NO_RECORDS;aaaa_status=ERROR_SUCCESS;t=task("register");firebase_worker(&t);
    assert(t.ok && dns_calls.size()==3 && count("signUp")==1);
    reset();mx_status=DNS_INFO_NO_RECORDS;t=task("register");firebase_worker(&t);
    assert(!t.ok && t.error=="EMAIL_DOMAIN_NOT_FOUND" && calls.empty());
    for(auto invalid:{"no-at","a@@example.com","a..b@example.com",".a@example.com","a@-example.com","a@example..com","a@example.com.","a@localhost","a b@example.com"}) {
        assert(!firebase_email_valid(invalid));reset();t=task("register");t.email=invalid;firebase_worker(&t);assert(!t.ok && t.error=="INVALID_EMAIL" && calls.empty() && dns_calls.empty());
    }
    assert(firebase_email_valid("name+zone@sub.example.com") && firebase_email_valid("a@xn--e1afmkfd.xn--p1ai"));
    assert(!firebase_email_valid(std::string(65,'a')+"@example.com"));
    // Correcting a typo retains the identity and verifies before changing the address.
    reset();t=task("change_email");t.email="correct@example.invalid";firebase_worker(&t);
    assert(t.ok && t.session_ready && t.session.pending_email==t.email && t.session.email==fresh_email && !t.session.verified);
    assert(count("signUp")==0 && count("update")==0 && count("sendOobCode")==1 && calls.back().payload["requestType"]=="VERIFY_AND_CHANGE_EMAIL");
    reset();t=task("resend");t.session.pending_email="correct@example.invalid";firebase_worker(&t);
    assert(t.ok && calls.back().payload["newEmail"]=="correct@example.invalid");
    reset();fresh_verified=true;t=task("verify");t.session.pending_email="correct@example.invalid";firebase_worker(&t);
    assert(!t.ok && !t.session.verified && t.error=="EMAIL_NOT_VERIFIED");
    reset();fresh_verified=true;fresh_email="CORRECT@example.invalid";t=task("verify");t.session.pending_email="correct@example.invalid";firebase_worker(&t);
    assert(t.ok && t.session.verified && t.session.pending_email.empty());
    reset();send_ok=false;t=task("change_email");t.email="correct@example.invalid";firebase_worker(&t);
    assert(!t.ok && t.session_ready && t.session.pending_email.empty() && t.error==send_error);
    // The actual public request entrypoint rejects obsolete code submission and duplicate requests.
    assert(!script_firebase_request("verify","","123456",""));
    assert(!script_firebase_request("register","a@example.invalid","short","account-one"));
    assert(!script_firebase_request("register","a@example.invalid","test-password","x"));
    assert(!script_firebase_request("register","a@@example.invalid","test-password","account-one"));
    assert(!script_firebase_request("change_email","correct@example.invalid","",""));
    assert(script_firebase_request("verify","","",""));
    assert(spawned==1 && !script_firebase_request("verify","","",""));
    delete s_firebase_task;
}
'''
with TemporaryDirectory(prefix='firebase-links-') as tmp:
    cpp=Path(tmp)/'check.cpp'; exe=Path(tmp)/'check'
    cpp.write_text(fixture)
    subprocess.run(['g++','-std=c++17','-O2','-I',str(root/'src/3rd party/nlohmann'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Actual Firebase link worker: signup, token-bound delivery, fresh verification, resend/failure recovery, expiry, cached-flag denial and request validation PASS; no real accounts or mail')
