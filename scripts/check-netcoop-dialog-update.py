"""Exercise actual dialog update/clear/deferred-add with engine API doubles."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/UIDialogHolder.cpp").read_text()
start = text.index("void CDialogHolder::OnFrame()")
update = text[start:text.index("void CDialogHolder::CleanInternals()", start)]
start = text.index("void CDialogHolder::CleanInternals()")
clear = text[start:text.index("bool CDialogHolder::IR_UIOnKeyboardPress(", start)]
start = text.index("void CDialogHolder::AddDialogToRender(")
add = text[start:text.index("void CDialogHolder::RemoveDialogToRender(", start)]
# Previous loop retained exactly for non-mutating differential traces only.
old_loop = """\t\txr_vector<dlgItem>::iterator it = m_dialogsToRender.begin();
\t\tfor (; it != m_dialogsToRender.end(); ++it)
\t\t\tif ((*it).enabled && (*it).wnd && (*it).wnd->IsEnabled())
\t\t\t\t(*it).wnd->Update();"""
begin = update.index("\t\t// A dialog callback")
end = update.index("\n\t}\n\n\tm_b_in_update = false;", begin)
legacy = (update[:begin] + old_loop + update[end:]).replace("CDialogHolder::OnFrame()", "CDialogHolder::OnFrame_legacy()")
source = r'''
#include <algorithm>
#include <cassert>
#include <functional>
#include <iostream>
#include <string>
#include <vector>
template<class T>using xr_vector=std::vector<T>;
std::vector<std::string> trace;
struct CUIWindow {
 std::string name;bool enabled=true,shown=false;std::function<void()> callback;
 explicit CUIWindow(std::string n):name(std::move(n)){}
 virtual ~CUIWindow()=default;
 bool IsEnabled()const{return enabled;}void Show(bool value){shown=value;}
 void Update(){trace.push_back(name);auto local=callback;if(local)local();}
};
struct CUIDialogWnd:CUIWindow {using CUIWindow::CUIWindow;};
struct dlgItem {CUIWindow* wnd;bool enabled=true;explicit dlgItem(CUIWindow* p):wnd(p){}
 bool operator<(const dlgItem& o)const{return int(enabled)>int(o.enabled);}};
bool operator==(const dlgItem& a,const dlgItem& b){return a.wnd==b.wnd && a.enabled==b.enabled;}
struct Cursor {int hidden=0;void Hide(){++hidden;}} cursor;
Cursor& GetUICursor(){return cursor;}
struct CDialogHolder {
 xr_vector<CUIDialogWnd*> m_input_receivers;
 xr_vector<dlgItem> m_dialogsToRender,m_dialogsToRender_new;
 bool m_b_in_update=false;
 CUIDialogWnd* TopInputReceiver(){return m_input_receivers.empty()?nullptr:m_input_receivers.back();}
 void OnFrame();void OnFrame_legacy();void CleanInternals();void AddDialogToRender(CUIWindow*);
};
''' + update + clear + add + legacy + r'''
int main(){
 // Exact legacy trace/count for enabled/list/top combinations without structural mutation.
 for(unsigned mask=0;mask<64;++mask)for(int top=-1;top<3;++top){
  CUIDialogWnd a("a"),b("b"),c("c");CUIDialogWnd* windows[]={&a,&b,&c};
  CDialogHolder current,reference;
  for(int i=0;i<3;++i){windows[i]->enabled=(mask & (1u<<i))!=0;dlgItem item(windows[i]);item.enabled=(mask & (1u<<(i+3)))!=0;
   current.m_dialogsToRender.push_back(item);reference.m_dialogsToRender.push_back(item);}
  if(top>=0){current.m_input_receivers.push_back(windows[top]);reference.m_input_receivers.push_back(windows[top]);}
  trace.clear();current.OnFrame();auto actual=trace;trace.clear();reference.OnFrame_legacy();assert(actual==trace);
  assert(current.m_dialogsToRender.size()==reference.m_dialogsToRender.size());
  for(size_t i=0;i<current.m_dialogsToRender.size();++i)assert(current.m_dialogsToRender[i]==reference.m_dialogsToRender[i]);
  assert(!current.m_b_in_update);
 }
 // Close from inside the rendered-list Update, free its windows and return through the loop.
 {CDialogHolder holder;auto* a=new CUIDialogWnd("a");auto* b=new CUIDialogWnd("b");auto* c=new CUIDialogWnd("c");
  holder.AddDialogToRender(a);holder.AddDialogToRender(b);holder.AddDialogToRender(c);
  b->callback=[&]{holder.CleanInternals();delete a;delete b;delete c;};
  trace.clear();holder.OnFrame();assert((trace==std::vector<std::string>{"a","b"}));
  assert(holder.m_dialogsToRender.empty() && holder.m_dialogsToRender_new.empty() && !holder.TopInputReceiver());}
 // Close from the top receiver, including a queued new popup destroyed by close.
 {CDialogHolder holder;auto* top=new CUIDialogWnd("top");auto* pending=new CUIDialogWnd("pending");
  holder.m_input_receivers.push_back(top);holder.AddDialogToRender(top);
  top->callback=[&]{holder.AddDialogToRender(pending);holder.CleanInternals();delete pending;delete top;};
  trace.clear();holder.OnFrame();assert((trace==std::vector<std::string>{"top"}));
  assert(holder.m_dialogsToRender.empty() && holder.m_dialogsToRender_new.empty());}
 // Additions are deferred, deduplicated and receive their first Update next frame.
 {CDialogHolder holder;CUIDialogWnd top("top"),fresh("fresh");holder.m_input_receivers.push_back(&top);holder.AddDialogToRender(&top);
  top.callback=[&]{holder.AddDialogToRender(&fresh);holder.AddDialogToRender(&fresh);};
  trace.clear();holder.OnFrame();assert((trace==std::vector<std::string>{"top","top"}));
  assert(fresh.shown && holder.m_dialogsToRender.size()==2 && holder.m_dialogsToRender_new.empty());
  trace.clear();holder.OnFrame();assert((trace==std::vector<std::string>{"top","top","fresh"}));}
 // A dialog intentionally added AFTER clear survives, without updating during the closing frame.
 {CDialogHolder holder;CUIDialogWnd old("old"),fresh("fresh");holder.AddDialogToRender(&old);
  old.callback=[&]{holder.CleanInternals();holder.AddDialogToRender(&fresh);};
  trace.clear();holder.OnFrame();assert((trace==std::vector<std::string>{"old"}));
  assert(holder.m_dialogsToRender.size()==1 && holder.m_dialogsToRender[0].wnd==&fresh);
  trace.clear();holder.OnFrame();assert((trace==std::vector<std::string>{"fresh"}));}
 // Disabled subsequent entries are skipped and removed after the original cleanup order.
 {CDialogHolder holder;CUIDialogWnd a("a"),b("b");holder.AddDialogToRender(&a);holder.AddDialogToRender(&b);
  a.callback=[&]{holder.m_dialogsToRender[1].enabled=false;};trace.clear();holder.OnFrame();
  assert((trace==std::vector<std::string>{"a"}));assert(holder.m_dialogsToRender.size()==1);}
 std::cout<<"PASS: actual dialog update/clear/add; 256 exact legacy callback traces, clear+destroy during rendered/top Update, no pending resurrection, deferred/deduplicated new dialogs and disabled cleanup\n";
}
'''
with TemporaryDirectory(prefix="dialog-update-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True, cwd=tmp)
