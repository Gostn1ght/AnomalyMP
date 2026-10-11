"""Actual news presentation: PDA required for news, NPC dialogue stays available."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/ui/UIMainIngameWnd.cpp").read_text(encoding="utf-8")
start = text.index("void CUIMainIngameWnd::ReceiveNews(")
brace = text.index("{", start)
depth, end = 1, brace + 1
while depth:
    depth += (text[end] == "{") - (text[end] == "}")
    end += 1
source = r'''
#include <cassert>
#include <cstdio>
namespace netcoop{bool client=true;bool pure_client(){return client;}}
#define VERIFY(x) assert(x)
struct GAME_NEWS_DATA{
 enum {eNews,eTalk};int m_type=eNews;
 struct{unsigned size(){return 1;}}texture_name;
};
struct Player{bool pda=false;bool GetPDA(){return pda;}}player;
Player* actor=&player;Player* Actor(){return actor;}
unsigned popups=0,updates=0;
struct Messages{void AddIconedPdaMessage(GAME_NEWS_DATA*){++popups;}}messages;
struct UI{Messages* m_pMessagesWnd=&messages;void UpdatePda(){++updates;}}ui;
UI* CurrentGameUI(){return &ui;}
struct CUIMainIngameWnd{void ReceiveNews(GAME_NEWS_DATA*);};
'''
source += text[start:end]
source += r'''
int main(){
 CUIMainIngameWnd wnd;GAME_NEWS_DATA news;
 wnd.ReceiveNews(&news);assert(popups==0 && updates==0);
 player.pda=true;wnd.ReceiveNews(&news);assert(popups==1 && updates==1);
 player.pda=false;news.m_type=GAME_NEWS_DATA::eTalk;
 wnd.ReceiveNews(&news);assert(popups==2 && updates==2);
 news.m_type=GAME_NEWS_DATA::eNews;actor=nullptr;
 wnd.ReceiveNews(&news);assert(popups==2 && updates==2);
 netcoop::client=false;wnd.ReceiveNews(&news);assert(popups==3 && updates==3);
 std::puts("PASS actual news presentation: PDA slot required, dialogue and freeplay preserved");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "news.cpp"
    exe = Path(tmp) / ("news.exe" if os.name == "nt" else "news")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
