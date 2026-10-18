"""CI: actual preview assignment and deferred model-pool material restoration."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root=Path(__file__).resolve().parents[1]


def method(path, signature):
    text=(root/path).read_text(encoding='utf-8-sig')
    start=text.index(signature);begin=text.index('{',start);depth,end=1,begin+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


pool=(root/'src/Layers/xrRender/ModelPool.cpp').read_text(encoding='utf-8')
assert 'reset_model_materials(V);' in pool[pool.index('void CModelPool::DeleteInternal('):pool.index('void CModelPool::Delete(')]
source=r'''
#include <cassert>
#include <string>
#include <vector>
using BOOL=bool;using LPCSTR=const char*;using u32=unsigned;using xr_string=std::string;
constexpr bool FALSE=false;
#define VERIFY(x) assert(x)
struct Text:std::string{using std::string::string;using std::string::operator=;
 const char* operator*()const{return c_str();}bool equal(const Text& t)const{return *this==t;}};
struct Shader{std::string id;void create(const char* name,const char* texture){id=std::string(name)+":"+texture;}
 explicit operator bool()const{return !id.empty();}};using ref_shader=Shader;
struct IRenderVisual{virtual ~IRenderVisual()=default;virtual std::vector<IRenderVisual*>* get_children(){return nullptr;}
 virtual std::vector<IRenderVisual*>* get_children_invisible(){return nullptr;}virtual void ResetShaderTexture(){}
 virtual const char* getDebugTexture(){return "diffuse";}};
struct dxRender_Visual:IRenderVisual{Text dbg_shader="models",dbg_shader_def="models",dbg_texture="diffuse",dbg_texture_def="diffuse";Shader shader;
 dxRender_Visual(){shader.create(*dbg_shader,*dbg_texture);}void ResetShaderTexture()override;
 void SetShaderTexture(const char* s,const char* t){dbg_shader=s;dbg_texture=t;shader.create(s,t);}};
struct CSkeletonX:dxRender_Visual{int mode=2;int UISkinningMode(){return mode;}};
struct Group:dxRender_Visual{std::vector<IRenderVisual*> visible,invisible;
 std::vector<IRenderVisual*>* get_children()override{return &visible;}
 std::vector<IRenderVisual*>* get_children_invisible()override{return &invisible;}};
template<class T,class U>T fast_dynamic_cast(U* p){return dynamic_cast<T>(p);}
xr_string menu_material_textures(LPCSTR base){return xr_string(base)+",bump";}
struct CRender{int mode=-1;void shader_option_skinning(int value){mode=value;}bool PrepareUIModel(IRenderVisual*);};
''' + method('src/Layers/xrRenderPC_R4/r4_R_render.cpp','bool CRender::PrepareUIModel(') + '\n' + method(
    'src/Layers/xrRender/FBasicVisual.cpp','void dxRender_Visual::ResetShaderTexture()') + '\n' + method(
    'src/Layers/xrRender/ModelPool.cpp','static void reset_model_materials(') + r'''
bool g_bRendering=false;
struct CModelPool{std::vector<dxRender_Visual*> ModelsToDelete,cached;
 void DeleteInternal(dxRender_Visual*& v,BOOL discard=false){assert(!g_bRendering && !discard);reset_model_materials(v);cached.push_back(v);v=nullptr;}
 void Delete(dxRender_Visual*&,BOOL=false);void DeleteQueue();};
''' + method('src/Layers/xrRender/ModelPool.cpp','void CModelPool::Delete(') + '\n' + method(
    'src/Layers/xrRender/ModelPool.cpp','void CModelPool::DeleteQueue()') + r'''
int main(){
 CRender renderer;CModelPool pool;Group actor,nested;CSkeletonX body,weapon,hidden;
 actor.visible={&body,&nested};nested.visible={&weapon};nested.invisible={&hidden};
 assert(renderer.PrepareUIModel(&actor));
 // Hidden addon can have its own material from an earlier menu frame.
 assert(renderer.PrepareUIModel(&hidden));
 assert(body.shader.id=="netcoop_preview:diffuse,bump" && weapon.shader.id==body.shader.id);
 assert(body.dbg_shader_def=="models" && body.dbg_texture_def=="diffuse");
 dxRender_Visual* released=&actor;g_bRendering=true;pool.Delete(released,FALSE);
 assert(!released && pool.cached.empty() && pool.ModelsToDelete.size()==1);
 g_bRendering=false;pool.DeleteQueue();
 assert(pool.cached.size()==1 && pool.ModelsToDelete.empty());
 for(auto* mesh:{&body,&weapon,&hidden}){
  assert(mesh->shader.id=="models:diffuse"); // normal G-buffer/world materials again
  assert(mesh->dbg_shader==mesh->dbg_shader_def && mesh->dbg_texture==mesh->dbg_texture_def);
 }
 // Repeated menu/game reuse remains reversible.
 assert(renderer.PrepareUIModel(&actor));released=&actor;pool.Delete(released);
 assert(body.shader.id=="models:diffuse" && weapon.shader.id==body.shader.id);
}
'''
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='preview-pool-') as tmp:
    folder=Path(tmp);cpp=folder/'pool.cpp';exe=folder/'pool.exe';cpp.write_text(source,encoding='utf-8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)],cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
print('PASS actual preview/pool: deferred deletion, nested/hidden material restoration and repeated live-model reuse')
