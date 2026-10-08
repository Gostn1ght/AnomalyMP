"""Compare the qualified actual GAMMA stats constructor before/after patch."""
from pathlib import Path
import re
from lupa.lua51 import LuaRuntime

root=Path(__file__).resolve().parents[1]
legacy=(root/'scripts/fixtures/inventory-compat/stats-constructor.lua').read_bytes()
current=legacy
for polarity in ['P','N']:
    field=polarity.lower()
    old=f'self.stat[name].ico_{field}:InitTexture("ui_inGame2_inv_state_{polarity}_" .. name)'.encode()
    new=f'netcoop_inventory_compat.init_bonus_texture(self.stat[name].ico_{field}, "{polarity}", name)'.encode()
    assert current.count(old)==1
    current=current.replace(old,new,1)
lua=LuaRuntime(encoding=None)
helper=(root/'scripts/netcoop-overlay/client/netcoop_inventory_compat.script').read_bytes()
namespace=lua.eval(b'function(source) local env={};setmetatable(env,{__index=_G});setfenv(assert(loadstring(source)),env)();return env end')(helper)
lua.globals().netcoop_inventory_compat=namespace
runner=lua.eval(br'''function(code)
 local trace={};local count=0
 local function create(kind,path,parent)
  count=count+1
  local control={id=count}
  trace[#trace+1]='create:'..kind..':'..path..':'..tostring(parent and parent.id or 0)
  function control:InitTexture(name) self.texture=name;trace[#trace+1]='texture:'..name end
  function control:Show(visible) self.visible=visible;trace[#trace+1]='show:'..self.id..':'..tostring(visible) end
  return control
 end
 local names={'health','radia','acid','shock','fire','psi','wound','fire_wound','power','thirst','sleep','br_class','br_mitigation','strike','explosion'}
 local instance={stat_list={},equ_dialog={id=0}}
 for _,name in ipairs(names) do instance.stat_list[name]={} end
 local xml={}
 function xml:InitStatic(path,parent) return create('static',path,parent) end
 function xml:InitProgressBar(path,parent) return create('bar',path,parent) end
 function xml:InitTextWnd(path,parent) return create('text',path,parent) end
 local env={self=instance,xml=xml};setmetatable(env,{__index=_G})
 setfenv(assert(loadstring(code)),env)()
 for _,name in ipairs(names) do
  local stat=instance.stat[name]
  assert(stat.base and stat.bar and stat.ico_base and stat.text and stat.text_bonus and stat.text_bonus_regen)
  assert(stat.ico_p.visible==false and stat.ico_n.visible==false)
 end
 return trace,instance
end''')
old_trace,old=runner(legacy);new_trace,new=runner(current)
unused={b'thirst',b'sleep',b'br_class',b'br_mitigation',b'strike',b'explosion'}
reference=[];removed=[]
for event in old_trace.values():
    match=re.fullmatch(br'texture:ui_inGame2_inv_state_[PN]_(.+)',event)
    (removed if match and match[1] in unused else reference).append(event)
assert len(removed)==12 and list(new_trace.values())==reference
for name,old_stat in old[b'stat'].items():
    new_stat=new[b'stat'][name]
    for field in [b'ico_p',b'ico_n']:
        if name in unused:assert new_stat[field][b'texture'] is None
        else:assert new_stat[field][b'texture']==old_stat[field][b'texture']
print('PASS actual15-row stats constructor: identical widget creation/parents/show states;18valid P/N textures retained,12hidden nonexistent textures skipped')
