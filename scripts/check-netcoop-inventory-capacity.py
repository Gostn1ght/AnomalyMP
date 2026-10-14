"""Actual GAMMA weight method and slots wrapper, XML footer and matching config."""
from pathlib import Path
import xml.etree.ElementTree as ET
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
overlay = root/'scripts/netcoop-overlay'
assert 'LPCSTR script_inventory_slots();' in (root/'src/xrGame/netcoop.h').read_text(encoding='utf-8')
assert 'LPCSTR script_inventory_slots()' in (root/'src/xrGame/netcoop_storage.inc').read_text(encoding='utf-8')
assert (overlay/'client/configs/netcoop/storage.ltx').read_bytes() == (overlay/'server/configs/netcoop/storage.ltx').read_bytes()
layout = ET.parse(overlay/'client/configs/ui/ui_inventory_16.xml').getroot().find('player')
slots, weight, button = [layout.find(name) for name in ('slots', 'weight', 'putall_button')]
assert float(button.attrib['x']) + float(button.attrib['width']) <= float(slots.attrib['x'])
assert float(slots.attrib['x']) + float(slots.attrib['width']) <= float(weight.attrib['x'])
assert slots.attrib['y'] == weight.attrib['y']
for language in ('rus', 'eng'):
    strings = ET.parse(overlay/f'client/configs/text/{language}/st_netcoop.xml').getroot()
    assert len(strings.findall("string[@id='lz_inventory_cells']")) == 1

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
ui_inventory={UIInventory={}};UIInventory=ui_inventory.UIInventory
local actor={}
function actor:item_in_slot(slot) return {get_additional_max_weight=function() return slot==7 and 5 or 15 end} end
function actor:get_total_weight() return 12.5 end
function actor:get_actor_max_weight() return 40 end
function actor:iterate_inventory() end
function actor:cast_Actor() return self end
function actor:conditions() return self end
function actor:BoosterForEach(callback) callback(4,60,10) end
db={actor=actor};ini_sys={};clr_weight={1,2,3};weight_unit='kg';strformat=string.format
function round_idp(value) return value end
function GetARGB(a,r,g,b) return r*65536+g*256+b end
local function widget()
 return {SetText=function(self,text) self.text=text end,SetTextColor=function(self,color) self.color=color end,
 Show=function(self,value) self.visible=value end}
end
created=0;stats='35|280';level={netcoop_inventory_slots=function() return stats end}
game={translate_string=function(key) assert(key=='lz_inventory_cells');return 'Cells:' end}
function CScriptXmlInit()
 return {ParseFile=function(self,path) assert(path=='ui_inventory.xml') end,
 InitTextWnd=function(self,path,parent) assert(path=='player:slots' and parent);created=created+1;return widget() end}
end
gui={player_dialog={},player_weight=widget(),player_weight_max=widget(),player_weight_cap=widget()}
function gui:GetPartner() return nil end
setmetatable(gui,{__index=ui_inventory.UIInventory})
''')
lua.execute((root/'scripts/fixtures/inventory-compat/weight-update.lua').read_bytes().decode('cp1251'))
helper = lua.eval('''function(source)
 local env={};setmetatable(env,{__index=_G});setfenv(assert(loadstring(source)),env)();return env
end''')((overlay/'client/netcoop_inventory_capacity.script').read_text(encoding='utf-8'))
original = lua.globals().ui_inventory.UIInventory.UpdateWeight
assert helper.install() is True
assert helper.install() is True
gui = lua.globals().gui
gui.UpdateWeight(gui)
assert gui.player_weight.text == '12.5 kg' and gui.player_weight_max.text == '(max 70 kg)'
assert gui.lz_inventory_cells.text == 'Cells: 35/280' and gui.player_weight_cap.visible is False
assert lua.globals().created == 1
lua.globals().stats = '300|160'
gui.UpdateWeight(gui)
assert gui.lz_inventory_cells.text == 'Cells: 300/160' and lua.globals().created == 1
assert gui.lz_inventory_cells.color == lua.globals().GetARGB(255,220,90,70)
lua.globals().stats = '0|999999'
gui.UpdateWeight(gui)
assert gui.lz_inventory_cells.text == 'Cells: 300/160'
lua.execute('level.netcoop_inventory_slots=nil')
gui.UpdateWeight(gui)
assert lua.globals().created == 1 and gui.player_weight.text == '12.5 kg'
print('PASS actual GAMMA weight/gear/booster update preserved; cells, overflow, repeated update, old native compatibility, localized nonoverlapping footer and matching client/server policy')
