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
source=r'''
#include <cassert>
#include <cstdio>
#include <random>
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
 puts("PASS actual replica preparation10000:4dynamics zero, pose/enabled contract retained, authoritative queue unchanged; actual selection includes fragments/items/corpses/props, excludes live creatures/unrelated objects");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'replica.cpp';exe=Path(tmp)/('replica.exe' if os.name=='nt' else 'replica')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
