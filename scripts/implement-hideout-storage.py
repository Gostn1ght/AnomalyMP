"""One-time source migration, with exact-match guards for the current branch."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def edit(file, changes):
    path=root/file
    text=path.read_text(encoding='cp1251')
    for before,after in changes:
        assert before in text,(file,before[:100])
        text=text.replace(before,after,1)
    path.write_text(text,encoding='cp1251')
edit('src/xrGame/netcoop_characters.inc',[
 ('xr_vector<Item> items;', 'xr_vector<Item> items, safe;\n\tu32 storage_revision = 1;\n\txr_string storage_request, storage_signature;'),
 ('const u32 magic = 0x3548434e;', 'const u32 magic = 0x3648434e;'),
 ('const bool ok = !ferror(f);', '''fwrite(&character.storage_revision,4,1,f);
    fwrite(character.storage_request.c_str(),1,character.storage_request.size()+1,f);
    fwrite(character.storage_signature.c_str(),1,character.storage_signature.size()+1,f);
    const u32 safe_count=u32(character.safe.size()); fwrite(&safe_count,4,1,f);
    for (const auto& item:character.safe)
    {
        fwrite(item.section.c_str(),1,item.section.size()+1,f);
        fwrite(&item.parent,2,1,f); fwrite(&item.place,2,1,f);
        character_write_packet(f,item.spawn);
    }
    const bool ok = !ferror(f) && fflush(f)==0 && _commit(_fileno(f))==0;'''),
 ('magic == 0x3548434e) &&', 'magic == 0x3548434e || magic == 0x3648434e) &&'),
 ('if (ok && magic == 0x3548434e)', 'if (ok && magic >= 0x3548434e)'),
 ('\tfclose(f);\n\tif (!ok || !character_name_valid', '''    if (ok && magic==0x3648434e)
    {
        ok=fread(&character.storage_revision,4,1,f)==1 && character.storage_revision &&
            character_read_string(f,character.storage_request,32) && character_read_string(f,character.storage_signature,80) &&
            fread(&count,4,1,f)==1 && count<=512;
        for (u32 i=0;ok && i<count;++i)
        {
            Character::Item item;
            ok=character_read_string(f,item.section,128) && fread(&item.parent,2,1,f)==1 && item.parent<=i &&
                fread(&item.place,2,1,f)==1 && character_read_packet(f,item.spawn) && pSettings->section_exist(item.section.c_str());
            if (ok) character.safe.push_back(std::move(item));
        }
    }
    ok=ok && fgetc(f)==EOF && !ferror(f);
\tfclose(f);
\tif (!ok || !character_name_valid'''),
 ('\tcharacter.initialized = true;\n\tif (!character_save(character))', '\tcharacter.initialized = true;\n    if (character.storage_revision!=0xffffffffu) ++character.storage_revision;\n\tif (!character_save(character))'),
])
edit('src/xrGame/netcoop.cpp',[
 ('#include <bcrypt.h>', '#include <bcrypt.h>\n#include <io.h>\n#include "netcoop_storage_policy.h"'),
 ('void client_write_auth(NET_Packet& P)', '''struct StorageRequest
{
    bool active=false; u8 op=0,slot=1; u16 index=0; u32 revision=0; xr_string id;
};
static StorageRequest s_storage_request;
void storage_write_auth(NET_Packet& P)
{
    if (!s_storage_request.active || s_client_character_slot) return;
    P.w_u32(0x54535a4c); P.w_u8(s_storage_request.op); P.w_u8(s_storage_request.slot);
    P.w_u16(s_storage_request.index); P.w_u32(s_storage_request.revision); P.w_stringZ(s_storage_request.id.c_str());
    s_storage_request.active=false;
}
bool script_storage_prepare(int op,int slot,int index,int revision)
{
    if (g_pGameLevel || op<0 || op>2 || slot<1 || slot>10 || index<0 || index>511) return false;
    u8 nonce[16]; if (BCryptGenRandom(nullptr,nonce,sizeof(nonce),BCRYPT_USE_SYSTEM_PREFERRED_RNG)!=0) return false;
    s_storage_request.active=true; s_storage_request.op=u8(op); s_storage_request.slot=u8(slot);
    s_storage_request.index=u16(index); s_storage_request.revision=u32(revision); s_storage_request.id=to_hex(nonce,sizeof(nonce));
    return true;
}
void client_write_auth(NET_Packet& P)'''),
 ('\ts_client_register = false;\n\ts_client_role = role_none;', '\tstorage_write_auth(P);\n\ts_client_register = false;\n\ts_client_role = role_none;'),
 ('\tcall_lua("netcoop_client_compat.on_auth_result", !!ok, s_client_role, message);', '''    xr_string storage_reply;
    char storage[14336];
    if (ok && P.r_elapsed() && read_string(P,storage,sizeof(storage))) storage_reply=storage;
\tcall_lua("netcoop_client_compat.on_auth_result", !!ok, s_client_role, message);
    if (!storage_reply.empty())
    {
        ::luabind::functor<void> callback;
        if (ai().script_engine().functor("netcoop_login_ui.on_storage_result",callback)) callback(storage_reply.c_str());
    }'''),
 ('#include "netcoop_characters.inc"', '#include "netcoop_characters.inc"\n#include "netcoop_storage.inc"'),
 ('u8 role, LPCSTR message)\n{\n\tNET_Packet P;\n\tP.w_begin(M_NETCOOP_AUTH_RESULT);', 'u8 role, LPCSTR message, LPCSTR storage=nullptr)\n{\n\tNET_Packet P;\n\tP.w_begin(M_NETCOOP_AUTH_RESULT);'),
 ('P.w_stringZ(previews.c_str());', '''// Storage snapshots occupy a separate bounded payload. Full account
        // previews can approach the packet limit and are omitted in that case.
        P.w_stringZ(storage ? "" : previews.c_str());
        if (storage) P.w_stringZ(storage);'''),
 ('\tbool create;\n\tu8 slot', '\tbool create;\n    StorageRequest storage;\n\tu8 slot'),
 ('if (P.r_elapsed()) { xr_delete(pending); reject(server, CL, "Unexpected authentication data"); return; }', '''if (P.r_elapsed())
            {
                char id[33];
                if (pending->slot!=0 || P.r_elapsed()<13 || P.r_u32()!=0x54535a4c)
                { xr_delete(pending); reject(server,CL,"Invalid storage request"); return; }
                pending->storage.active=true; pending->storage.op=P.r_u8(); pending->storage.slot=P.r_u8();
                pending->storage.index=P.r_u16(); pending->storage.revision=P.r_u32();
                if (!read_string(P,id,sizeof(id)) || xr_strlen(id)!=32 || P.r_elapsed() || pending->storage.op>2)
                { xr_delete(pending); reject(server,CL,"Invalid storage request"); return; }
                pending->storage.id=id;
            }'''),
 ('send_auth_result(server, CL, true, a->role, "Account verified");', '''if (pending->storage.active)
        {
            const xr_string result=storage_execute(server,CL,pending->storage);
            send_auth_result(server,CL,true,a->role,"Account verified",result.c_str());
        }
        else send_auth_result(server, CL, true, a->role, "Account verified");'''),
])
edit('src/xrGame/level_script.cpp',[
 ('bool script_frontend_auth(LPCSTR options);', 'bool script_storage_prepare(int op,int slot,int index,int revision); bool script_frontend_auth(LPCSTR options);'),
 ('def("netcoop_frontend_auth", &netcoop::script_frontend_auth),', 'def("netcoop_frontend_auth", &netcoop::script_frontend_auth),\n        def("netcoop_storage_prepare", &netcoop::script_storage_prepare),'),
])
print('Authoritative storage source integrated')
