"""Exercise actual keyboard dispatch, clipboard reading and edit insertion in CI."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]

def function(path, signature):
    source = (root/path).read_text()
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

fixture = r'''
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#include <memory>
#include <algorithm>
#include <functional>
#include <alloca.h>
using u32=unsigned; using u8=unsigned char; using BOOL=int; using DWORD=unsigned;
using HRESULT=int; using SIZE_T=size_t; using LPCSTR=const char*; using LPSTR=char*; using PSTR=char*;
#define VERIFY(x) assert(x)
#define _alloca alloca
template<class T> T _min(T a,T b) { return std::min(a,b); }
template<class T> void clamp(T& v,T a,T b) { v=std::max(a,std::min(v,b)); }
size_t xr_strlen(const char* s) { return strlen(s); }
void strncpy_s(char* dst,size_t size,const char* src,size_t count) { assert(size>count);memcpy(dst,src,count);dst[count]=0; }
const unsigned CF_TEXT=1, CF_UNICODETEXT=13, WC_NO_BEST_FIT_CHARS=1024;
std::wstring wide_clip; std::string ansi_clip;
bool open_ok=true, lock_ok=true, has_unicode=true, has_ansi=false, is_open=false;
int closes=0, unlocks=0;
using HGLOBAL=void*;
bool OpenClipboard(int) { if(!open_ok)return false;assert(!is_open);is_open=true;return true; }
void CloseClipboard() { assert(is_open);is_open=false;++closes; }
HGLOBAL GetClipboardData(unsigned f) { assert(is_open);return f==CF_UNICODETEXT?(has_unicode?(void*)&wide_clip:nullptr):(has_ansi?(void*)&ansi_clip:nullptr); }
const void* GlobalLock(HGLOBAL h) { if(!lock_ok)return nullptr;return h==&wide_clip?(void*)wide_clip.c_str():(void*)ansi_clip.c_str(); }
SIZE_T GlobalSize(HGLOBAL h) { return h==&wide_clip?(wide_clip.size()+1)*sizeof(wchar_t):ansi_clip.size()+1; }
void GlobalUnlock(HGLOBAL) { ++unlocks; }
int WideCharToMultiByte(unsigned cp,unsigned flags,const wchar_t* text,int count,char* dst,int size,const char*,void*) {
    assert(cp==1251 && flags==WC_NO_BEST_FIT_CHARS && count<=size);
    for(int i=0;i<count;++i) dst[i]=text[i]<128?char(text[i]):text[i]>=0x410 && text[i]<=0x44f?char(text[i]-0x410+0xc0):'?';
    return count;
}
namespace os_clipboard { void paste_from_clipboard(LPSTR,u32 const&); }
const int DIK_COUNT=256, DIK_LCONTROL=29, DIK_RCONTROL=157, DIK_LSHIFT=42, DIK_RSHIFT=54,
 DIK_LALT=56, DIK_RALT=184, DIK_LMENU=56, DIK_RMENU=184, DIK_PAUSE=197, DIK_F4=62,
 DIK_TAB=15, DIK_V=47, DIK_A=30, DIK_NUMLOCK=69;
const int KEYBOARDBUFFERSIZE=128, DIERR_INPUTLOST=-1, DIERR_NOTACQUIRED=-2, S_OK=0;
const int TRUE=1,FALSE=0,WM_SYSCOMMAND=274,SC_MINIMIZE=61472;
struct DIDEVICEOBJECTDATA { DWORD dwOfs=0,dwData=0,uAppData=0; };
struct Keyboard {
 std::vector<DIDEVICEOBJECTDATA> events;
 HRESULT GetDeviceData(size_t,DIDEVICEOBJECTDATA* out,DWORD* n,int) { *n=events.size();std::copy(events.begin(),events.end(),out);events.clear();return S_OK; }
 HRESULT Acquire() { return S_OK; }
};
struct Receiver { virtual void IR_OnKeyboardPress(int)=0;virtual void IR_OnKeyboardRelease(int)=0;virtual void IR_OnKeyboardHold(int)=0; };
struct CInput {
 static const int COUNT_KB_BUTTONS=256;
 BOOL KBState[COUNT_KB_BUTTONS]={};Keyboard* pKeyboard=nullptr;std::vector<Receiver*> cbStack;
 void KeyUpdate();bool iGetAsyncKeyState(int key) { return KBState[key]!=0; }
};
CInput* pInput=nullptr;BOOL b_altF4=FALSE;int g_screenmode=2,minimized=0;
struct { unsigned dwPrecacheFrame=0;void* m_hWnd=nullptr; } Device;
struct InputEvent { std::vector<std::string> calls;void Defer(const char* s) { calls.push_back(s); } };
struct { InputEvent Event; } Engine;
void SendMessage(void*,int,int,int) { ++minimized; }
namespace text_editor {
enum key_state { ks_free=0,ks_Shift=1,ks_Ctrl=2 };
struct Action { std::function<void(class line_edit_control*)> run;void on_key_press(line_edit_control* c) { run(c); } };
class line_edit_control {
public:
 int m_buffer_size=256,m_cur_pos=0,m_select_start=0,m_p1=0,m_p2=0;
 bool m_hold_mode=false,m_mark=false,m_repeat_mode=false,m_insert_mode=false,m_unselected_mode=false;
 float m_last_key_time=0,m_accel=1,m_rep_time=0;bool ctrl=false,shift=false;
 char m_edit_str[256]={},m_inserted[256]={},m_undo_buf[256]={};Action* m_actions[DIK_COUNT]={};
 void update_key_states() { ctrl=pInput->iGetAsyncKeyState(DIK_LCONTROL)||pInput->iGetAsyncKeyState(DIK_RCONTROL);shift=pInput->iGetAsyncKeyState(DIK_LSHIFT)||pInput->iGetAsyncKeyState(DIK_RSHIFT); }
 bool get_key_state(key_state k) { return k==ks_Ctrl?ctrl:k==ks_Shift?shift:true; }
 void update_bufs() {}
 void on_key_press(int);void clear_inserted();bool empty_inserted();void compute_positions();void clamp_cur_pos();
 void add_inserted_text();void paste_from_clipboard();void select_all_buf();void set_edit(LPCSTR);
};
}
'''
fixture += function('src/xrCore/os_clipboard.cpp','void os_clipboard::paste_from_clipboard')
fixture += function('src/xrEngine/Xr_input.cpp','void CInput::KeyUpdate()')
fixture += 'namespace text_editor {\n'
for method in ('on_key_press','clear_inserted','empty_inserted','compute_positions','clamp_cur_pos','add_inserted_text','paste_from_clipboard','select_all_buf','set_edit'):
    ret = 'bool' if method == 'empty_inserted' else 'void'
    fixture += function('src/xrEngine/line_edit_control.cpp', f'{ret} line_edit_control::{method}')
fixture += r'''
}
struct EditReceiver:Receiver {
 text_editor::line_edit_control edit; text_editor::Action paste,select;
 EditReceiver() {
  paste.run=[](auto c){if(c->get_key_state(text_editor::ks_Ctrl))c->paste_from_clipboard();};
  select.run=[](auto c){if(c->get_key_state(text_editor::ks_Ctrl))c->select_all_buf();};
  edit.m_actions[DIK_V]=&paste;edit.m_actions[DIK_A]=&select;
 }
 void IR_OnKeyboardPress(int key) override { edit.on_key_press(key); }
 void IR_OnKeyboardRelease(int) override { edit.update_key_states(); }
 void IR_OnKeyboardHold(int) override {}
};
int main() {
 Keyboard keyboard;CInput input;input.pKeyboard=&keyboard;pInput=&input;EditReceiver receiver;input.cbStack.push_back(&receiver);
 wide_clip=L"name@example.org";
 keyboard.events={{DIK_LCONTROL,128},{DIK_V,128},{DIK_V,0},{DIK_LCONTROL,0}};input.KeyUpdate();
 assert(std::string(receiver.edit.m_edit_str)=="name@example.org" && !input.KBState[DIK_LCONTROL] && !is_open);
 wide_clip=L"new@example.org";
 keyboard.events={{DIK_RCONTROL,128},{DIK_A,128},{DIK_A,0},{DIK_V,128},{DIK_V,0},{DIK_RCONTROL,0}};input.KeyUpdate();
 assert(std::string(receiver.edit.m_edit_str)=="new@example.org");
 char buffer[32];memset(buffer,'z',sizeof(buffer));wide_clip=L"\u041f\u043e\u0447\u0442\u0430";
 os_clipboard::paste_from_clipboard(buffer,sizeof(buffer));assert(std::string(buffer)==std::string("\xcf\xee\xf7\xf2\xe0") && !is_open);
 wide_clip=L"a\r\nb\tc";os_clipboard::paste_from_clipboard(buffer,sizeof(buffer));assert(std::string(buffer)=="a  b c");
 wide_clip=L"abcdefghijk";os_clipboard::paste_from_clipboard(buffer,5);assert(std::string(buffer)=="abcd");
 os_clipboard::paste_from_clipboard(buffer,1);assert(buffer[0]==0 && !is_open);
 has_unicode=has_ansi=false;os_clipboard::paste_from_clipboard(buffer,sizeof(buffer));assert(buffer[0]==0 && !is_open);
 has_unicode=true;lock_ok=false;os_clipboard::paste_from_clipboard(buffer,sizeof(buffer));assert(buffer[0]==0 && !is_open);lock_ok=true;
 open_ok=false;os_clipboard::paste_from_clipboard(buffer,sizeof(buffer));assert(buffer[0]==0 && !is_open);open_ok=true;
 has_unicode=false;has_ansi=true;ansi_clip="legacy text";os_clipboard::paste_from_clipboard(buffer,sizeof(buffer));assert(std::string(buffer)==ansi_clip);
 has_unicode=true;wide_clip=L"1234567";receiver.edit.m_buffer_size=8;receiver.edit.set_edit("");
 keyboard.events={{DIK_LCONTROL,128},{DIK_V,128},{DIK_V,0},{DIK_LCONTROL,0}};input.KeyUpdate();
 assert(std::string(receiver.edit.m_edit_str)=="1234567");
 wide_clip=L"xyz123";receiver.edit.set_edit("abcdef");receiver.edit.m_cur_pos=3;receiver.edit.m_select_start=3;
 keyboard.events={{DIK_LCONTROL,128},{DIK_V,128},{DIK_V,0},{DIK_LCONTROL,0}};input.KeyUpdate();
 assert(std::string(receiver.edit.m_edit_str)=="abcxyz1");
 Device.dwPrecacheFrame=1;keyboard.events={{DIK_RCONTROL,128},{DIK_RCONTROL,0}};input.KeyUpdate();assert(!input.KBState[DIK_RCONTROL]);Device.dwPrecacheFrame=0;
 keyboard.events={{DIK_LMENU,128},{DIK_TAB,128},{DIK_TAB,0},{DIK_LMENU,0}};input.KeyUpdate();assert(minimized==1);
 keyboard.events={{DIK_LMENU,128},{DIK_F4,128}};input.KeyUpdate();assert(b_altF4 && Engine.Event.calls.size()==2);
 assert(closes>5 && unlocks>3);
}
'''
with TemporaryDirectory(prefix='edit-input-') as tmp:
    cpp=Path(tmp)/'check.cpp';exe=Path(tmp)/'check'
    cpp.write_text(fixture)
    subprocess.run(['g++','-std=c++17','-O2',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Actual input/clipboard: quick left/right Ctrl+V, Ctrl+A replacement, CP1251 Unicode, empty/locked clipboard, bounds, long paste, precache and Alt+Tab/F4 PASS')
