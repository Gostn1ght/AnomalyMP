"""CI only: real Lua resize adapters and XML widget reinitializers."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root=Path(__file__).resolve().parents[1]
folder=root/'src/xrGame/ui'
button=(folder/'UI3tButton.cpp').read_text(encoding='utf-8-sig')
button=button[button.index('void CUI3tButton::InitButton('):button.index('void CUI3tButton::SetWidth(')]
edit=(folder/'UIEditBox.cpp').read_text(encoding='utf-8-sig')
edit=edit[edit.index('void CUIEditBox::InitCustomEdit('):edit.index('void CUIEditBox::InitTextureEx(')]
button_bind=(folder/'UIButton_script.cpp').read_text(encoding='utf-8-sig')
edit_bind=(folder/'UIEditBox_script.cpp').read_text(encoding='utf-8-sig')
adapters=''
for binding,name in ((button_bind,'resize_button_script'),(edit_bind,'resize_edit_box_script')):
    assert f'.def("SetWndSize", &{name})' in binding
    adapters+=binding[binding.index(f'static void {name}('):binding.index('#pragma optimize')]
source=r'''
#include <cassert>
#include <string>
struct Fvector2 {float x=0,y=0;Fvector2& set(float a,float b){x=a;y=b;return *this;}};
struct Window {
 Fvector2 test_pos,test_size;unsigned children=0;std::string text="kept text";
 void SetWndPos(Fvector2 p){test_pos=p;}void SetWndSize(Fvector2 s){test_size=s;}
 Fvector2 GetWndPos()const{return test_pos;}
 void SetAutoDelete(bool){}void SetCustomDraw(bool){}void AttachChild(Window*){++children;}
};
using CUI_IB_FrameLineWnd=Window;using CUI_IB_Static=Window;using CUIFrameLineWnd=Window;
struct CUIButton:Window {};
struct CUI3tButton:CUIButton {
 bool m_frameline_mode=false;Window* m_back_frameline=nullptr;Window* m_background=nullptr;
 void InitButton(Fvector2,Fvector2);
 ~CUI3tButton(){delete m_back_frameline;delete m_background;}
};
template<class T>T* xr_new(){return new T;}
struct CUICustomEdit:Window {void InitCustomEdit(Fvector2 p,Fvector2 s){SetWndPos(p);SetWndSize(s);}};
struct CUIEditBox:CUICustomEdit {
 Window* m_frameLine=nullptr;void InitCustomEdit(Fvector2,Fvector2);
 ~CUIEditBox(){delete m_frameLine;}
};
''' + button + edit + adapters + r'''
int main(){
 for(bool frame: {false,true}){
  CUI3tButton control;control.m_frameline_mode=frame;
  control.InitButton(Fvector2().set(40,620),Fvector2().set(10,30));
  Window* background=frame?control.m_back_frameline:control.m_background;
  resize_button_script(&control,Fvector2().set(152,34));
  assert(control.test_size.x==152 && control.test_size.y==34);
  assert(background->test_size.x==152 && background->test_size.y==34);
  assert(control.test_pos.x==40 && control.test_pos.y==620 && control.text=="kept text");
  assert(control.children==1 && (frame?control.m_back_frameline:control.m_background)==background);
  resize_button_script(&control,Fvector2().set(264,28));
  assert(background->test_size.x==264 && background->test_size.y==28 && control.children==1);
 }
 CUIEditBox input;input.m_frameLine=new Window;
 input.InitCustomEdit(Fvector2().set(44,620),Fvector2().set(10,32));
 resize_edit_box_script(&input,Fvector2().set(580,34));
 assert(input.test_size.x==580 && input.test_size.y==34);
 assert(input.m_frameLine->test_size.x==580 && input.m_frameLine->test_size.y==34);
 assert(input.test_pos.x==44 && input.test_pos.y==620 && input.text=="kept text");
 CUIEditBox bare;resize_edit_box_script(&bare,Fvector2().set(120,30));
 assert(bare.test_size.x==120 && bare.test_size.y==30 && !bare.m_frameLine);
}
'''
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native fixture compiles only in GitHub Actions; no local compiler invocation.')
with TemporaryDirectory(prefix='ui-resize-') as temporary:
    target=Path(temporary);cpp=target/'resize.cpp';exe=target/('resize.exe' if os.name=='nt' else 'resize')
    cpp.write_text(source,encoding='utf-8')
    args=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt'
          else ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(args,cwd=target,check=True);subprocess.run([str(exe)],cwd=target,check=True)
print('PASS actual UI resize: buttons and frames follow outer size; edit frame resizes; text, position and child identity retained')
