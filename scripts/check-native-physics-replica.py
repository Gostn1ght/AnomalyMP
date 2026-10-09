"""Exercise actual pose-only replica preparation; authoritative snapshots remain untouched."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run on GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/PhysicsShellHolder.cpp').read_text(encoding='utf-8-sig')
method=text[text.index('void CPhysicsShellHolder::netcoop_physics_update()'):text.index('float CPhysicsShellHolder::EffectiveGravity()')]
assert 'if (!netcoop::pure_client() || m_netcoop_physics.empty()) return;' in method
start=method.index('state.previous_position = state.position;')
prepare=method[start:method.index('PHGetSyncItem(i)->set_State(state);',start)]
server=(root/'src/xrGame/netcoop.cpp').read_text(encoding='utf-8-sig')
begin=server.index('const bool item_or_corpse =',server.index('void server_physics_update('))
select=server[begin:server.index('if (!item_or_corpse && !prop) continue;',begin)]
effects=(root/'src/xrGame/physics_game.cpp').read_text(encoding='latin-1')
begin=effects.index('static float netcoop_contact_effect_criterion(')
effect_method=effects[begin:effects.index('template <class Pars>',begin)]
source=r'''
#include <cassert>
#include <cstdio>
#include <random>
#include <cmath>
#include <limits>
#include <vector>
struct Vec {float x=0,y=0,z=0;void set(float a,float b,float c){x=a;y=b;z=c;}};
struct Quat {float x=0,y=0,z=0,w=1;};
bool same(const Vec& a,const Vec& b){return a.x==b.x&&a.y==b.y&&a.z==b.z;}
bool zero(const Vec& a){return a.x==0&&a.y==0&&a.z==0;}
bool same(const Quat& a,const Quat& b){return a.x==b.x&&a.y==b.y&&a.z==b.z&&a.w==b.w;}
struct SPHNetState {Vec position,previous_position,linear_vel,angular_vel,force,torque;Quat quaternion,previous_quaternion;bool enabled=false;};
struct CObject {virtual ~CObject()=default;};
struct CInventoryItem:CObject {};
struct CPhysicObject:CObject {};
struct CPhysicsSkeletonObject:CObject {};
struct CEntityAlive:CObject {bool alive=true;bool g_Alive()const{return alive;}};
template<class T>T smart_cast(CObject* object){return dynamic_cast<T>(object);}
bool pure=true;namespace netcoop{bool pure_client(){return pure;}}
bool _valid(float x){return std::isfinite(x);}float _sqrt(float x){return std::sqrt(x);}
struct CPhysicsElement{bool fixed=true;float mass=.5f;bool isFixed(){return fixed;}float getMass(){return mass;}};
struct CPhysicsShell{std::vector<CPhysicsElement*> elements;unsigned get_ElementsNumber(){return unsigned(elements.size());}
 CPhysicsElement* get_ElementByStoreOrder(unsigned n){return elements[n];}};
struct CPhysicsShellHolder:CObject{bool buffered=true;CPhysicsShell* shell=nullptr;
 bool netcoop_physics_buffered(){return buffered;}CPhysicsShell* PPhysicsShell(){return shell;}};
struct dxGeomUserData{CObject* ph_ref_object=nullptr;unsigned element_position=0;};
CObject* live_holder=nullptr;bool PHIsShellHolderLive(CObject* p){return p&&p==live_holder;}
struct Body{float mass=100000000.f;};using dBodyID=Body*;
struct Geometry{Body* body=nullptr;};struct dContactGeom{Geometry* g1=nullptr;Geometry* g2=nullptr;};
dBodyID dGeomGetBody(Geometry* g){return g?g->body:nullptr;}
struct dMass{float mass=0;};void dBodyGetMass(Body* b,dMass* m){m->mass=b->mass;}
'''+effect_method+r'''
bool selected(CObject* object){
 auto* creature=smart_cast<CEntityAlive*>(object);
'''+select+r'''
 return item_or_corpse||prop;
}
SPHNetState prepare_replica(SPHNetState state){
'''+prepare+r'''
 return state;
}
int main(){
 CObject unrelated;CInventoryItem item;CPhysicObject prop;CPhysicsSkeletonObject fragment;
 CEntityAlive live,corpse;corpse.alive=false;
 CPhysicsElement element;CPhysicsShell shell;shell.elements={&element};CPhysicsShellHolder holder;holder.shell=&shell;
 live_holder=&holder;dxGeomUserData data;data.ph_ref_object=&holder;
 Body body;Geometry geometry;geometry.body=&body;dContactGeom contact;contact.g1=&geometry;
 const float synthetic=.05f*std::sqrt(body.mass);
 assert(synthetic==500.f); // a tiny solver velocity on FixBody used to exceed every FX threshold
 for(float mass:{.01f,.5f,1.f,10.f,10000.f}){
  element.mass=mass;const float expected=.05f*std::sqrt(mass);
  assert(std::abs(netcoop_contact_effect_criterion(&data,&contact,synthetic)-expected)<.00001f);
 }
 pure=false;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);pure=true;
 holder.buffered=false;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);holder.buffered=true;
 element.fixed=false;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);element.fixed=true;
 assert(netcoop_contact_effect_criterion(nullptr,&contact,synthetic)==synthetic);
 live_holder=nullptr;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);live_holder=&holder;
 data.element_position=1;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);data.element_position=0;
 holder.shell=nullptr;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);holder.shell=&shell;
 element.mass=0;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);
 element.mass=std::numeric_limits<float>::quiet_NaN();assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);
 element.mass=.5f;contact.g1=nullptr;contact.g2=&geometry;
 assert(std::abs(netcoop_contact_effect_criterion(&data,&contact,synthetic)-.05f*std::sqrt(.5f))<.00001f);
 contact.g2=nullptr;assert(netcoop_contact_effect_criterion(&data,&contact,synthetic)==synthetic);
 assert(!selected(&unrelated)&&!selected(&live));
 assert(selected(&item)&&selected(&corpse)&&selected(&prop)&&selected(&fragment));
 std::mt19937 gen(92831);std::uniform_real_distribution<float> value(-10000,10000);
 for(int i=0;i<10000;++i){
  SPHNetState snapshot;snapshot.position={value(gen),value(gen),value(gen)};
  snapshot.previous_position={value(gen),value(gen),value(gen)};
  snapshot.quaternion={.1f,.2f,.3f,.4f};snapshot.previous_quaternion={.4f,.3f,.2f,.1f};
  snapshot.linear_vel={value(gen),value(gen),value(gen)};
  snapshot.angular_vel={value(gen),value(gen),value(gen)};
  snapshot.force={value(gen),value(gen),value(gen)};snapshot.torque={value(gen),value(gen),value(gen)};
  snapshot.enabled=(i%2)!=0;const SPHNetState original=snapshot;
  const SPHNetState replica=prepare_replica(snapshot);
  assert(same(replica.position,snapshot.position)&&same(replica.quaternion,snapshot.quaternion));
  assert(same(replica.previous_position,replica.position)&&same(replica.previous_quaternion,replica.quaternion));
  assert(replica.enabled&&zero(replica.linear_vel)&&zero(replica.angular_vel)&&zero(replica.force)&&zero(replica.torque));
  assert(same(original.position,snapshot.position)&&same(original.previous_position,snapshot.previous_position));
  assert(same(original.quaternion,snapshot.quaternion)&&same(original.previous_quaternion,snapshot.previous_quaternion));
  assert(same(original.linear_vel,snapshot.linear_vel)&&same(original.angular_vel,snapshot.angular_vel));
  assert(same(original.force,snapshot.force)&&same(original.torque,snapshot.torque)&&original.enabled==snapshot.enabled);
 }
 puts("PASS actual replica preparation10000:4dynamics zero, pose/enabled/authority retained; fragment filter; actual contact FX use physical mass only for buffered fixed replicas, SP/server/dynamic/stale/missing guards retained");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'replica.cpp';exe=Path(tmp)/('replica.exe' if os.name=='nt' else 'replica')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
