// Included after character persistence. Only authenticated, detached characters
// may transact: no live Actor exists concurrently with this saved inventory.
static xr_string storage_number(u32 value) { string32 text; xr_sprintf(text,"%u",value); return text; }
static u32 storage_capacity(bool safe)
{
    string_path path;
    u32 capacity=safe ? 120 : 60;
    if (FS.exist(path,"$game_config$","netcoop\\storage.ltx"))
    {
        CInifile ini(path,TRUE,TRUE,FALSE);
        LPCSTR key=safe ? "safe_cells" : "backpack_cells";
        if (ini.line_exist("storage",key)) capacity=ini.r_u32("storage",key);
    }
    return _max(1u,_min(512u,capacity));
}
static u32 storage_section_cost(LPCSTR section)
{
    const u32 width=pSettings->line_exist(section,"inv_grid_width") ? pSettings->r_u32(section,"inv_grid_width") : 1;
    const u32 height=pSettings->line_exist(section,"inv_grid_height") ? pSettings->r_u32(section,"inv_grid_height") : 1;
    return _max(1u,_min(512u,width)*_min(512u,height));
}
static u32 storage_item_cost(const Character::Item& item) { return storage_section_cost(item.section.c_str()); }
static u32 storage_live_cells(xrServer* server, CSE_Abstract* owner)
{
    u32 used=0;
    for (u16 id:owner->children)
        if (auto item=server->game->get_entity_from_eid(id))
            if (smart_cast<CSE_ALifeInventoryItem*>(item)) used+=storage_section_cost(item->s_name.c_str());
    return used;
}
bool server_inventory_can_take(xrServer* server,u16 owner_id,u16 item_id)
{
    if (!enabled()) return true;
    auto owner=server->game->get_entity_from_eid(owner_id);
    auto item=server->game->get_entity_from_eid(item_id);
    if (!owner || !smart_cast<CSE_ALifeCreatureActor*>(owner) || !item || !smart_cast<CSE_ALifeInventoryItem*>(item)) return true;
    if (item->ID_Parent==owner_id) return true;
    return storage_live_cells(server,owner)+storage_section_cost(item->s_name.c_str())<=storage_capacity(false);
}
static bool storage_equipped(const Character::Item& item)
{
    SInvItemPlace place; place.value=item.place;
    return place.type==eItemPlaceSlot || place.type==eItemPlaceBelt;
}
static xr_string storage_execute(xrServer* server,xrClientData* CL,const StorageRequest& request)
{
    LPCSTR message="OK";
    Character* character=nullptr;
    if (!CL || CL->netcoop_role==role_none || request.slot<1 || request.slot>(CL->netcoop_role==role_admin ? 10 : 1))
        message="DENIED";
    else character=character_load(CL->netcoop_login.c_str(),request.slot);
    if (!character && !xr_strcmp(message,"OK")) message="CHARACTER_NOT_SAVED";
    bool live=false;
    if (character)
    {
        const auto key=character_key(character->account.c_str(),character->slot);
        for (const auto& actor:s_actor_character)
            if (actor.second==key && server->game->get_entity_from_eid(actor.first)) { live=true; break; }
        if (live) message="CHARACTER_ONLINE";
        else if (!character->initialized || character->respawn) message="CHARACTER_NOT_READY";
        else if (request.op>2) message="INVALID_REQUEST";
        else if (request.op)
        {
            // A committed retry is harmless, even after reconnect/restart.
            const xr_string signature=storage_number(request.op)+":"+storage_number(request.index)+":"+storage_number(request.revision);
            if (character->storage_request==request.id)
                message=character->storage_signature==signature ? "OK" : "INVALID_REQUEST";
            else if (request.id.size()!=32 || request.revision!=character->storage_revision || character->storage_revision==0xffffffffu)
                message="STALE";
            else
            {
                Character candidate=*character;
                auto& source=request.op==1 ? candidate.items : candidate.safe;
                auto& target=request.op==1 ? candidate.safe : candidate.items;
                const auto result=hideout_storage::transfer(source,target,request.index,storage_capacity(request.op==1),storage_item_cost,
                    [&request](const Character::Item& item) { return request.op==1 && storage_equipped(item); });
                if (result==hideout_storage::equipped) message="UNEQUIP_FIRST";
                else if (result==hideout_storage::full) message="NO_FREE_SLOTS";
                else if (result!=hideout_storage::ok) message="ITEM_UNAVAILABLE";
                else
                {
                    ++candidate.storage_revision; candidate.storage_request=request.id; candidate.storage_signature=signature;
                    // Inventory and safe share ONE flushed atomic save replacement.
                    // Publish the in-memory state only after that commit succeeds.
                    if (!character_save(candidate)) message="SAVE_FAILED";
                    else *character=std::move(candidate);
                }
            }
        }
    }
    xr_string out=message;
    out+='\n';
    if (!character || live) return out;
    out+=storage_number(character->storage_revision)+"|"+storage_number(hideout_storage::cells(character->items,storage_item_cost))+"|"+
        storage_number(storage_capacity(false))+"|"+storage_number(hideout_storage::cells(character->safe,storage_item_cost))+"|"+storage_number(storage_capacity(true))+"\n";
    for (u32 container=0;container<2;++container)
    {
        const auto& items=container ? character->safe : character->items;
        for (u32 i=0;i<items.size();++i)
        {
            if (items[i].parent) continue;
            out+=(container ? "S|" : "I|")+storage_number(i)+"|"+items[i].section+"|"+storage_number(storage_item_cost(items[i]))+"|"+
                storage_number(container ? 0 : storage_equipped(items[i]))+"\n";
        }
    }
    // The auth reply contains only this selected slot for storage requests.
    if (out.size()>14000) return "INVENTORY_TOO_LARGE\n";
    return out;
}
