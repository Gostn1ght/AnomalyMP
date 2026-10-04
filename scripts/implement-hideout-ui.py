from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
p=root/'scripts/netcoop-overlay/client/netcoop_login_ui.script';s=p.read_text(encoding='cp1251')
def swap(before,after):
    global s
    assert before in s,before[:100];s=s.replace(before,after,1)
swap('function on_auth_result(ok, role, message)\n', '''function on_auth_result(ok, role, message)
    if wnd and wnd.storage_pending then
        auth_return = nil
        if not ok then wnd.storage_pending=nil; wnd:StorageMessage(tr("auth_failed") .. " " .. (message or "")) end
        return
    end
''')
start=s.index('function netcoop_login_wnd:CloseRoomView()');end=s.index('function netcoop_login_wnd:SetMsg',start)
s=s[:start]+'''function netcoop_login_wnd:CloseRoomView()
    self.room_view, self.room_pending = nil, nil
    if self.inventory_panel then self.inventory_panel:Show(false) end
    if self.server_panel then self.server_panel:Show(false) end
    if self.room_back then self.room_back:Show(false) end
end
function netcoop_login_wnd:OpenRoomView(kind, object)
    if self.room_view == kind then return self:CloseRoomView() end
    self:CloseRoomView()
    self.room_view, self.room_pending = kind, kind
    self.view_index = object
    netcoop_preview_focus(object)
    self.room_back:Show(true)
    if kind == "inventory" or kind == "safe" then self:RequestStorage(0,0) end
end
function netcoop_login_wnd:ToggleInventory() self:OpenRoomView("inventory",2) end
function netcoop_login_wnd:ChangeView(delta)
    if self.storage_pending or self.settings_pending then return end
    self:CloseRoomView()
    self.view_index=((self.view_index or -1)+1+delta)%6-1
    netcoop_preview_focus(self.view_index)
    local labels={"room_overview","room_map","room_pda","room_backpack","room_safe","room_door"}
    self.camera_caption:TextControl():SetText(tr(labels[self.view_index+2]))
end
function netcoop_login_wnd:PositionRoomControls()
    if not self.room_buttons then return end
    for _,entry in ipairs(self.room_buttons) do
        local point=netcoop_preview_point(entry.object)
        entry.button:SetWndPos(vector2():set(point.x-58,point.y-14))
        entry.button:Show(not self.room_view and point.x>65 and point.x<959 and point.y>110 and point.y<650)
    end
end
function netcoop_login_wnd:StorageMessage(message)
    self.storage_status:TextControl():SetText(message or "")
    self:SetMsg(message)
end
function netcoop_login_wnd:RequestStorage(op,index)
    if self.storage_pending or auth_return=="pending" then return end
    self.storage_pending={op=op,index=index,slot=self.slot,revision=self.storage_revision or 0}
    self:StorageMessage(tr("connecting"))
    if cloud_enabled() then
        if not self:CloudRequest("refresh") then self.storage_pending=nil end
    else self:StartStorageRequest() end
end
function netcoop_login_wnd:StartStorageRequest()
    local request=self.storage_pending
    if not request then return end
    netcoop_character(0,"","stalker",1,"")
    if not netcoop_storage_prepare(request.op,request.slot,request.index,request.revision) or
        not netcoop_frontend_auth(string.format("%s/name=%s/port=%s",self.pending_ip,self.pending_login,self.pending_port)) then
        self.storage_pending=nil; auth_return=nil; self:StorageMessage(tr("auth_failed")); return
    end
    auth_return="pending"
end
function on_storage_result(data)
    if not wnd or not wnd.storage_pending then return end
    local request=wnd.storage_pending; wnd.storage_pending=nil; auth_return=nil
    if request.slot~=wnd.slot then return end
    local code,rest=string.match(data or "","^([^\\n]+)\\n(.*)$")
    local errors={DENIED="storage_denied",CHARACTER_ONLINE="storage_online",CHARACTER_NOT_READY="storage_first_join",
        CHARACTER_NOT_SAVED="storage_first_join",STALE="storage_stale",UNEQUIP_FIRST="storage_equipped",
        NO_FREE_SLOTS="storage_full",ITEM_UNAVAILABLE="storage_stale",SAVE_FAILED="storage_save_failed",INVENTORY_TOO_LARGE="storage_full"}
    wnd:StorageMessage(code=="OK" and tr("storage_saved") or tr(errors[code] or "auth_failed"))
    local revision,used,capacity,safe_used,safe_capacity=string.match(rest or "","^(%d+)|(%d+)|(%d+)|(%d+)|(%d+)\\n")
    if not revision then return end
    wnd.storage_revision=tonumber(revision)
    wnd.backpack_capacity:TextControl():SetText(tr("room_backpack") .. "  " .. used .. " / " .. capacity)
    wnd.safe_capacity:TextControl():SetText(tr("room_safe") .. "  " .. safe_used .. " / " .. safe_capacity)
    wnd.inventory_scroll:Clear(); wnd.safe_scroll:Clear()
    for container,index,section,cost,equipped in string.gmatch(rest,"([IS])|(%d+)|([^|\\n]+)|(%d+)|(%d+)\\n") do
        wnd:AddStorageRow(container,tonumber(index),section,tonumber(cost),equipped=="1")
    end
end
function netcoop_login_wnd:AddStorageRow(container,index,section,cost,equipped)
    if not ini_sys:section_exist(section) then return end
    local xml=CScriptXmlInit(); xml:ParseFile("ui_netcoop_characters.xml")
    local row=xml:Init3tButton("storage_row",nil)
    local name=game.translate_string(SYS_GetParam(0,section,"inv_name",section))
    row:TextControl():SetText(name .. "\\n" .. cost .. " " .. tr("storage_cells") .. (equipped and "  " .. tr("storage_worn") or ""))
    local icon=CUIStatic(); row:AttachChild(icon); icon:SetAutoDelete(true)
    icon:InitTexture(utils_xml.get_icons_texture(section)); icon:SetTextureRect(Frect():set(utils_xml.get_item_axis(section,nil,true)))
    icon:SetStretchTexture(true); icon:SetWndPos(vector2():set(8,8)); icon:SetWndSize(vector2():set(50,45))
    local id="storage_" .. container .. index
    self:Register(row,id)
    self:AddCallback(id,ui_events.BUTTON_CLICKED,function()
        if equipped then self:StorageMessage(tr("storage_equipped")); return end
        self:RequestStorage(container=="I" and 1 or 2,index)
    end,self)
    (container=="I" and self.inventory_scroll or self.safe_scroll):AddWindow(row,true)
end

''' + s[end:]
swap('if kind == "inventory" then self.inventory_panel:Show(true)', 'if kind == "inventory" or kind == "safe" then self.inventory_panel:Show(true)')
swap('self:CloseRoomView()\n            self:HideDialog(); self:Show(false)\n            self.opt_dlg.background:Show(true)', 'self.settings_open=true\n            self:HideDialog(); self:Show(false)\n            self.opt_dlg.background:Show(false)')
swap('if auth_return and auth_return ~= "pending" then frontend_update(self.owner) end', '''if self.settings_open and self:IsShown() then self.settings_open=nil; self:CloseRoomView() end
    if self.mode=="characters" then self:PositionRoomControls() end
    if auth_return and auth_return ~= "pending" then frontend_update(self.owner) end''')
swap('self.previous_slot = button("previous", "<", function() self:ChangeSlot(-1) end)', 'self.previous_slot = button("previous", "<", function() self:ChangeView(-1) end)')
swap('self.next_slot = button("next", ">", function() self:ChangeSlot(1) end)', 'self.next_slot = button("next", ">", function() self:ChangeView(1) end)')
swap('self.enter = button("enter", tr("enter_zone"), function() self:SelectCharacter(self.slot) end)', 'self.enter = button("enter", tr("enter_zone"), function() self:OpenRoomView("server",4) end)')
swap('button("server", tr("server"), self.ShowServer)', 'local server=button("server",tr("room_map"),self.ShowServer)')
swap('button("inventory", tr("inventory"), self.ToggleInventory)', '''local inventory=button("inventory",tr("room_backpack"),self.ToggleInventory)
        local safe=button("safe",tr("room_safe"),function() self:OpenRoomView("safe",3) end)
        self.room_buttons={{button=server,object=0},{button=settings,object=1},{button=inventory,object=2},{button=safe,object=3},{button=self.enter,object=4}}
        self.camera_caption=caption("camera_caption",tr("room_overview"))
        self.character_badge:Show(false)
        self.character_description:Show(false)''')
swap('self.inventory_scroll = xml:InitScrollView("inventory_scroll", self.inventory_panel)', '''self.inventory_scroll = xml:InitScrollView("inventory_scroll", self.inventory_panel)
        self.safe_scroll=xml:InitScrollView("safe_scroll",self.inventory_panel)
        self.storage_status=xml:InitStatic("storage_status",self.inventory_panel)
        self.backpack_capacity=xml:InitStatic("backpack_capacity",self.inventory_panel)
        self.safe_capacity=xml:InitStatic("safe_capacity",self.inventory_panel)
        self.backpack_capacity:TextControl():SetText(tr("room_backpack"))
        self.safe_capacity:TextControl():SetText(tr("room_safe"))''')
swap('self:FillInventory(preview.items)\n\nend\nfunction netcoop_login_wnd:SetPose(pose) end', '''self.storage_revision=nil
    self.view_index=-1; netcoop_preview_focus(-1)
    local model=preview.visual and preview.visual~="" and preview.visual or BASE_MODEL
    if not netcoop_preview_model(model,-2) then netcoop_preview_model(BASE_MODEL,-2) end
    local weapon=""
    for section in string.gmatch(preview.items or "","[^,]+") do
        if ini_sys:section_exist(section) and string.sub(section,1,4)=="wpn_" and SYS_GetParam(2,section,"slot",0)==2 then weapon=section; break end
    end
    if netcoop_preview_weapon then netcoop_preview_weapon(weapon) end
    self:FillInventory(preview.items); self:PositionRoomControls()
end
function netcoop_login_wnd:SetPose(pose)
    local preview=self.previews[self.slot] or {}; netcoop_preview_model(preview.visual or BASE_MODEL,-2)
end''')
swap('self.slot = ((self.slot - 1 + delta) % limit) + 1','if self.storage_pending then return end\n    self.slot = ((self.slot - 1 + delta) % limit) + 1')
swap('if not self.room_view and dik == DIK_keys.DIK_LEFT then self:ChangeSlot(-1)', 'if not self.room_view and dik == DIK_keys.DIK_LEFT then self:ChangeView(-1)')
swap('if not self.room_view and dik == DIK_keys.DIK_RIGHT then self:ChangeSlot(1)', 'if not self.room_view and dik == DIK_keys.DIK_RIGHT then self:ChangeView(1)')
swap('if wnd.role_probe then\n        auth_return = nil', '''if wnd.storage_pending then
        auth_return=nil
        if ok and verified then wnd:StartStorageRequest()
        else wnd.storage_pending=nil; wnd:StorageMessage(ok and tr("verify_help") or cloud_error(error)) end
        return
    end
    if wnd.role_probe then
        auth_return = nil''')
# In a menu with no Actor, fallback draft icons never permit transfers.
swap('self.inventory_scroll:Clear()\n    local counts', 'self.inventory_scroll:Clear()\n    self.safe_scroll:Clear(); self:StorageMessage(tr("storage_readonly"))\n    local counts')
# End a storage operation cleanly if connecting failed before sending extension.
p.write_text(s,encoding='cp1251')

p=root/'scripts/netcoop-overlay/client/configs/ui/ui_netcoop_characters.xml'
tree=ET.parse(p);w=tree.getroot()
panel=w.find('panel');panel.clear();panel.attrib.update(x='0',y='0',width='1024',height='768')
def pos(name,x,y,width,height):w.find(name).attrib.update(x=str(x),y=str(y),width=str(width),height=str(height))
pos('title',30,25,220,40);pos('account',32,68,220,22)
pos('slots_title',770,26,224,25);pos('name',30,685,650,30);pos('info',30,720,650,22)
pos('description',0,0,1,1);pos('status',280,35,450,50);pos('hint',220,746,720,20)
for name in ('enter','inventory','server','settings'):pos(name,0,0,116,28)
pos('back',874,719,120,28);pos('previous',30,365,38,48);pos('next',956,365,38,48)
for i in range(1,11):pos('slot'+str(i),770,58+(i-1)*32,224,28)
pos('inventory_panel',180,140,664,514);pos('inventory_scroll',16,65,304,344);pos('room_back',424,669,176,30)
inv=w.find('inventory_panel')
for e in list(inv):
    if e.tag=='auto_static': inv.remove(e)
def text(name,x,y,width,height,font='letterica16'):
    e=ET.SubElement(w,name,dict(x=str(x),y=str(y),width=str(width),height=str(height)))
    ET.SubElement(e,'text',dict(r='221',g='204',b='177',font=font,align='l',vert_align='c',complex_mode='1'));return e
def button(name,x,y,width,height):
    e=text(name,x,y,width,height);ET.SubElement(e,'texture').text='ui_button_ordinary';return e
button('safe',0,0,116,28);text('camera_caption',394,704,236,24)
text('backpack_capacity',16,16,304,35,'letterica18');text('safe_capacity',344,16,304,35,'letterica18')
text('storage_status',16,420,630,76)
ET.SubElement(w,'safe_scroll',dict(x='344',y='65',width='304',height='344',always_show_scroll='1',vert_interval='5'))
row=button('storage_row',0,0,296,64);row.find('text').attrib.update(x='65',width='223',align='l')
ET.indent(tree);tree.write(p,encoding='windows-1251',xml_declaration=True)
translations={
 'room_overview':('Личная комната','Personal room'),'room_map':('Карта · сервер','Map · server'),
 'room_pda':('КПК · настройки','PDA · settings'),'room_backpack':('Рюкзак','Backpack'),
 'room_safe':('Личный сейф','Personal safe'),'room_door':('Дверь · в Зону','Door · enter Zone'),
 'storage_saved':('Сохранено. Нажмите предмет, чтобы перенести его в соседний контейнер.','Saved. Click an item to move it to the other container.'),
 'storage_denied':('Нет доступа к этому персонажу.','Character access denied.'),
 'storage_online':('Персонаж ещё в игре. Дождитесь завершения выхода с сервера.','Character is still online. Wait for server logout to finish.'),
 'storage_first_join':('Снаряжение доступно после первого входа персонажа на сервер.','Equipment becomes available after the first server join.'),
 'storage_stale':('Список изменился. Проверьте обновлённое снаряжение и повторите перенос.','Inventory changed. Review the refreshed items before retrying.'),
 'storage_equipped':('Сначала снимите предмет с персонажа в игре.','Unequip this item in game first.'),
 'storage_full':('В контейнере не хватает свободных ячеек.','The container has insufficient free cells.'),
 'storage_save_failed':('Сервер не смог сохранить перенос. Вещи остались на своих местах.','Server could not save the transfer. Items remain in their original containers.'),
 'storage_readonly':('Предпросмотр. Для переноса вещей нужен доступный игровой сервер.','Preview. Item transfers require an available game server.'),
 'storage_cells':('ячеек','cells'),'storage_worn':('надето','equipped')}
for lang,index in [('rus',0),('eng',1)]:
    p=root/f'scripts/netcoop-overlay/client/configs/text/{lang}/st_netcoop.xml';tree=ET.parse(p);w=tree.getroot()
    for key,values in translations.items():
        e=ET.SubElement(w,'string',id='st_netcoop_'+key);ET.SubElement(e,'text').text=values[index]
    ET.indent(tree);tree.write(p,encoding='windows-1251',xml_declaration=True)
print('Interactive hideout menu and storage panels integrated')
