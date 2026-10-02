// An isolated copy of the original Cordon bunker, with original game props.
// No level, physics world, ALife simulator or network server is needed here.
struct MenuRoomBatch
{
    shared_str texture;
    xr_vector<FVF::LIT> vertices;
    ref_shader shader;
};
struct MenuRoomProp
{
    LPCSTR model;
    Fvector position, angles;
    float scale;
    IRenderVisual* visual = nullptr;
};
static xr_vector<MenuRoomBatch> s_room_batches;
static bool s_room_loaded = false;
static ref_geom s_room_geometry;
static MenuRoomProp s_room_props[] = {
    {"netcoop\\room_map", Fvector().set(-1.30f,1.55f,.20f), Fvector().set(-PI/2,PI/2,0), .50f},
    {"netcoop\\room_table", Fvector().set(1.25f,0.f,.62f), Fvector().set(0,0,0), .60f},
    {"netcoop\\dev_pda", Fvector().set(1.1f,.57f,.28f), Fvector().set(0,-.28f,.30f), 1.4f},
    {"netcoop\\room_crate", Fvector().set(-1.10f,0.f,-.18f), Fvector().set(.15f,0,0), .65f},
    {"netcoop\\room_radio", Fvector().set(1.35f,.54f,.75f), Fvector().set(PI,0,0), .42f}
};
void netcoop_menu_room_release()
{
    for (auto& batch : s_room_batches) batch.shader.destroy();
    for (auto& prop : s_room_props)
        if (prop.visual) RImplementation.model_Delete(prop.visual, FALSE);
    s_room_geometry.destroy();
}
static void load_menu_room()
{
    if (s_room_loaded) return;
    s_room_loaded = true;
    IReader* file = FS.r_open("$game_meshes$", "netcoop\\cordon_bunker.room");
    if (!file) { Msg("! [NetAnomaly] missing original Cordon menu room"); return; }
    bool valid = file->length() >= 12;
    if (valid) valid = file->r_u32() == 0x4d52434e && file->r_u32() == 1;
    const u32 count = valid ? file->r_u32() : 0;
    valid = valid && count > 0 && count <= 128;
    for (u32 index = 0; valid && index < count; ++index)
    {
        MenuRoomBatch batch;
        string256 texture; u32 length = 0;
        while (file->elapsed() && length < sizeof(texture)-1)
        {
            const char ch = char(file->r_u8()); texture[length++] = ch;
            if (!ch) break;
        }
        valid = length > 1 && texture[length-1] == 0 && file->elapsed() >= 4;
        if (!valid) break;
        const u32 vertices = file->r_u32();
        valid = vertices > 0 && vertices % 3 == 0 && vertices <= 300000 &&
            size_t(vertices) * sizeof(FVF::LIT) <= file->elapsed();
        if (!valid) break;
        batch.texture = texture; batch.vertices.resize(vertices);
        file->r(batch.vertices.data(), vertices * sizeof(FVF::LIT));
        s_room_batches.push_back(batch);
    }
    valid = valid && file->elapsed() == 0;
    FS.r_close(file);
    if (!valid) { s_room_batches.clear(); Msg("! [NetAnomaly] invalid Cordon menu room"); }
    else Msg("[NetAnomaly] original Cordon bunker loaded: %u materials", count);
}
static void draw_menu_room()
{
    load_menu_room();
    if (!s_room_geometry) s_room_geometry.create(FVF::F_LIT, RCache.Vertex.Buffer(), nullptr);
    Fmatrix identity; identity.identity(); RCache.set_xform_world(identity);
    RCache.set_CullMode(CULL_NONE);
    for (auto& batch : s_room_batches)
    {
        if (!batch.shader) batch.shader.create("netcoop_room", batch.texture.c_str());
        RCache.set_Shader(batch.shader); RCache.set_Geometry(s_room_geometry);
        // Keep each dynamic-buffer reservation below 192 KiB.
        for (u32 first=0; first<batch.vertices.size();)
        {
            const u32 count = _min(8190u, u32(batch.vertices.size())-first);
            u32 offset = 0;
            auto memory = static_cast<FVF::LIT*>(RCache.Vertex.Lock(count,sizeof(FVF::LIT),offset));
            CopyMemory(memory,batch.vertices.data()+first,count*sizeof(FVF::LIT));
            RCache.Vertex.Unlock(count,sizeof(FVF::LIT));
            RCache.Render(D3DPT_TRIANGLELIST,offset,count/3); first+=count;
        }
    }
    for (auto& prop : s_room_props)
    {
        if (!prop.visual)
        {
            if (!RImplementation.models_Exists(prop.model)) continue;
            prop.visual=RImplementation.model_Create(prop.model);
            RImplementation.PrepareUIModel(prop.visual);
        }
        if (auto bones=prop.visual->dcast_PKinematics()) bones->CalculateBones(TRUE);
        Fmatrix world,scale; world.setHPB(prop.angles.x,prop.angles.y,prop.angles.z);
        scale.scale(prop.scale,prop.scale,prop.scale); world.mulB_43(scale); world.translate_over(prop.position);
        draw_ui_geometry(prop.visual,world);
    }
    RCache.set_CullMode(CULL_CCW);
}
