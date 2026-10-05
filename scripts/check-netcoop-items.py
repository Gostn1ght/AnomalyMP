"""Execute the actual server-run item action Lua (stage 3) in Lua 5.1."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
client = (root/'scripts/netcoop-overlay/client/netcoop_client_compat.script').read_text(encoding='cp1251')
server = (root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
lua = LuaRuntime(unpack_returned_tuples=True)

# Both whole files must compile.
for name, source in (('client', client), ('server', server)):
    ok, err = lua.eval('function(s) local f, e = loadstring(s); return f ~= nil, e end')(source)
    assert ok, f'{name} compat does not compile: {err}'

lua.execute(r'''
function printf() end
game={translate_string=function(s) return s end}
created={}; released={}
function alife_create_item(sec, parent, t) created[#created+1]={sec=sec, parent=parent, cond=t and t.cond} end
function alife_release(obj) released[#released+1]=obj:id() end
local function item(id, sec, cond)
  local o={_id=id,_sec=sec,_cond=cond}
  function o:id() return self._id end
  function o:section() return self._sec end
  function o:condition() return self._cond end
  function o:set_condition(c) self._cond=c end
  return o
end
objects={}
level={object_by_id=function(id) return objects[id] end}
db={actor={id=function() return 91 end}}
item_device={device_battery='batteries_dead', dev_consumption={device_pda_1={}}, dev_critical={device_pda_1=0.1}}
functors={device_pda_1={use2_action_functor='item_device.func_battery'}}
ini_sys={r_string_ex=function(_, sec, key) return functors[sec] and functors[sec][key] end}
unpacked=nil
item_device.func_battery=function(obj) unpacked=obj:id() end
make_item=item
''')
start = server.index('local SERVER_MENU_ACTIONS')
lua.execute(server[start:])
lua.execute(r'''
local battery=make_item(5,'batteries_dead',0.8); objects[5]=battery
local pda=make_item(6,'device_pda_1',0.12); objects[6]=pda
assert(item_action(91,1,5,6,'battery_swap')=='')
assert(pda:condition()==0.8,'device takes the battery charge')
assert(#released==1 and released[1]==5,'the battery is used up')
assert(#created==1 and created[1].cond==0.12 and created[1].parent==db.actor,'the old charge comes back as a battery')
local weak=make_item(7,'batteries_dead',0.3); objects[7]=weak
assert(item_action(91,1,7,6,'battery_swap')=='ui_st_battery_more_power','a weaker battery is refused')
assert(#released==1)
local flat=make_item(8,'device_pda_1',0.05); objects[8]=flat
local full=make_item(9,'batteries_dead',1.0); objects[9]=full
assert(item_action(91,1,9,8,'battery_swap')=='' and #created==1,'a flat device returns no battery')
assert(item_action(91,0,6,65535,'item_device.func_battery')=='' and unpacked==6,'whitelisted menu action runs')
assert(item_action(91,0,6,65535,'item_device.other')~='','unlisted functor is refused')
functors.device_pda_1.use2_action_functor=nil
assert(item_action(91,0,6,65535,'item_device.func_battery')~='','functor must belong to the item section')
assert(item_action(91,1,5,404,'battery_swap')~='','missing target')
''')

# Server repair: GAMMA's formula, kit range, parts, kit use.
lua.execute(r'''
function clamp(v,a,b) if v<a then return a elseif v>b then return b end return v end
items_of={repair_kit={'repair'}, wpn_ak74={'weapon'}, wpn_part={'part'}}
function IsItem(typ, sec, obj) sec=sec or obj:section(); for _,t in ipairs(items_of[sec] or {}) do if t==typ then return true end end; return false end
kits={repair_kit={repair_only='wpn_ak74', repair_min_condition=0.2, repair_max_condition=0.9, repair_add_condition=0.25,
  repair_use_parts=true, repair_parts_sections='wpn_part', repair_parts_multi=1}}
function parse_list(_, sec, key) local v=kits[sec] and kits[sec][key]; if not v then return nil end; return {[v]=true} end
ini_sys.r_float_ex=function(_, sec, key) return kits[sec] and kits[sec][key] or (sec=='wpn_part' and key=='repair_part_bonus' and 0.1) or nil end
ini_sys.r_bool_ex=function(_, sec, key, d) local v=kits[sec] and kits[sec][key]; if v==nil then return d end; return v end
discharged={}; degraded={}
utils_item={get_cond_static=function(c) return c end, discharge=function(o) discharged[#discharged+1]=o:id() end,
  degrade=function(o,n) degraded[#degraded+1]={o:id(),n} end}
''')
lua.execute(r'''
local kit=make_item(40,'repair_kit',1); objects[40]=kit
local ak=make_item(41,'wpn_ak74',0.43); objects[41]=ak
local part=make_item(42,'wpn_part',1); objects[42]=part
part.parent=function() return {id=function() return 91 end} end
assert(item_action(91,1,40,41,'repair 65535')=='')
assert(math.abs(ak:condition()-0.68)<1e-6,'43% + 25% without a part: '..ak:condition())
assert(#degraded==1 and degraded[1][1]==40,'single-use kit degrades')
ak:set_condition(0.43)
assert(item_action(91,1,40,41,'repair 42')=='')
assert(math.abs(ak:condition()-0.78)<1e-6,'part adds its 10% bonus: '..ak:condition())
assert(#discharged==1 and discharged[1]==42,'the part is used')
ak:set_condition(0.95)
assert(item_action(91,1,40,41,'repair 65535')~='','above the kit range refused')
local other=make_item(43,'wpn_ak74',0.5); objects[43]=other
other.parent=function() return {id=function() return 7 end} end
ak:set_condition(0.43)
assert(item_action(91,1,40,41,'repair 43')~='','a part of another player refused')
assert(item_action(91,1,41,40,'repair 65535')~='','a non-kit refused')
''')

# Client: menu routing and the battery drop replacement.
lua.execute(r'''
sent={}
function netcoop_item_action(kind,item,target,action) sent[#sent+1]={kind,item,target,action}; return true end
function netcoop_pure_client() return true end
callbacks={}
function RegisterScriptCallback(name,fn) callbacks[name]=callbacks[name] or {}; callbacks[name][fn]=true end
function UnregisterScriptCallback(name,fn) if callbacks[name] then callbacks[name][fn]=nil end end
EDDListType={iActorBag=1,iActorSlot=2}
actor_menu={set_msg=function() msg=true end}
actor_effects={play_item_fx=function() end}; utils_obj={play_sound=function() end}
original_called=0
ui_inventory={UIInventory={Action_Custom=function() original_called=original_called+1 end}}
functors.device_pda_1.use2_action_functor='item_device.func_battery'
functors.food={use1_action_functor='itms_manager.eat'}
local function on_item_drag_dropped() local_drop_called=true end
local_drop=on_item_drag_dropped
item_device.on_game_start=function() RegisterScriptCallback("ActorMenu_on_item_drag_drop", on_item_drag_dropped) end
item_device.on_game_start()
''')
start = client.index('local SERVER_ITEM_ACTIONS')
end = client.index('\nfunction on_game_start()', start)
lua.execute(client[start:end] + '\ninstall_items = install_server_item_actions\ninstall_server_item_actions()')
lua.execute(r'''
local ui=ui_inventory.UIInventory
local wnd=setmetatable({CheckItem=function(_,o) return o end,On_Item_Update=function() end},{__index=ui})
wnd:Action_Custom(objects[6],nil,nil,2)
assert(#sent==1 and sent[1][1]==0 and sent[1][2]==6 and sent[1][4]=='item_device.func_battery' and original_called==0)
wnd:Action_Custom(make_item(20,'food',1),nil,nil,1)
assert(#sent==1 and original_called==1,'other actions still run on the client')
local drops=callbacks.ActorMenu_on_item_drag_drop
local replacement=nil
for fn in pairs(drops) do replacement=fn end
assert(replacement and not drops[local_drop],'local battery handler replaced')
replacement(make_item(30,'batteries_dead',0.9),objects[6],1,2)
assert(#sent==2 and sent[2][1]==1 and sent[2][2]==30 and sent[2][3]==6 and sent[2][4]=='battery_swap')
replacement(make_item(31,'batteries_dead',0.1),objects[6],1,2)
assert(#sent==2 and msg,'weaker battery refused locally with the GAMMA message')
replacement(make_item(32,'batteries_dead',0.9),objects[6],3,2)
assert(#sent==2,'only from the backpack')
''')
lua.execute(r'''
item_repair={UIRepair={OnRepair=function() local_repair=true end}}
install_items()
local sel={GetCell_Selected=function() return objects[41] end}
local none={GetCell_Selected=function() return nil end}
local w={CC={sel,none},obj=objects[40],con_val={[4]=68},OnCancel=function() closed=true end}
item_repair.UIRepair.OnRepair(w)
assert(not local_repair and sent[#sent][1]==1 and sent[#sent][2]==40 and sent[#sent][3]==41 and sent[#sent][4]=='repair 65535' and closed)
assert(objects[41]:condition()==0.43,'the client does not repair by itself')
''')
print('Item actions Lua: battery swap/unpack and repair on the server, whitelist, client routing PASS')
