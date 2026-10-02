// A private room assembled from original STALKER decor geometry.
// No level, physics world, ALife simulator or network server is needed here.
struct MenuRoomVertex { Fvector position, normal; u32 color; Fvector2 uv; };
static_assert(sizeof(MenuRoomVertex)==36,"menu vertex layout");
struct MenuRoomBatch
{
    shared_str texture;
    xr_vector<MenuRoomVertex> vertices;
    ref_shader shader, depth_shader;
};
static xr_vector<MenuRoomBatch> s_room_batches;
static bool s_room_loaded = false;
static ref_geom s_room_geometry;
void netcoop_menu_room_release()
{
    for (auto& batch : s_room_batches) { batch.shader.destroy(); batch.depth_shader.destroy(); }
    release_menu_shadow();
    s_room_geometry.destroy();
}
static void load_menu_room()
{
    if (s_room_loaded) return;
    s_room_loaded = true;
    IReader* file = FS.r_open("$game_meshes$", "netcoop\\personal_room.room");
    if (!file) { Msg("! [NetAnomaly] missing personal menu room"); return; }
    bool valid = file->length() >= 12;
    if (valid) valid = file->r_u32() == 0x4d52434e && file->r_u32() == 2;
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
            size_t(vertices) * sizeof(MenuRoomVertex) <= file->elapsed();
        if (!valid) break;
        batch.texture = texture; batch.vertices.resize(vertices);
        file->r(batch.vertices.data(), vertices * sizeof(MenuRoomVertex));
        s_room_batches.push_back(batch);
    }
    valid = valid && file->elapsed() == 0;
    FS.r_close(file);
    if (!valid) { s_room_batches.clear(); Msg("! [NetAnomaly] invalid personal menu room"); }
    else Msg("[NetAnomaly] personal room loaded: %u materials", count);
}
static void draw_menu_room(bool depth=false)
{
    load_menu_room();
    if (!s_room_geometry) s_room_geometry.create(D3DFVF_XYZ|D3DFVF_NORMAL|D3DFVF_DIFFUSE|D3DFVF_TEX1, RCache.Vertex.Buffer(), nullptr);
    Fmatrix identity; identity.identity(); RCache.set_xform_world(identity);
    RCache.set_CullMode(CULL_NONE);
    for (auto& batch : s_room_batches)
    {
        if (!batch.shader)
        {
            const xr_string textures=menu_material_textures(batch.texture.c_str());
            batch.shader.create("netcoop_room", textures.c_str());
        }
        if (depth && !batch.depth_shader) batch.depth_shader.create("netcoop_room_depth",batch.texture.c_str());
        RCache.set_Shader(depth ? batch.depth_shader : batch.shader);
        RCache.set_c("m_menu_shadow",s_menu_shadow_matrix);
        RCache.set_Geometry(s_room_geometry);
        // Keep each dynamic-buffer reservation below 192 KiB.
        for (u32 first=0; first<batch.vertices.size();)
        {
            const u32 count = _min(5460u, u32(batch.vertices.size())-first);
            u32 offset = 0;
            auto memory = static_cast<MenuRoomVertex*>(RCache.Vertex.Lock(count,sizeof(MenuRoomVertex),offset));
            CopyMemory(memory,batch.vertices.data()+first,count*sizeof(MenuRoomVertex));
            RCache.Vertex.Unlock(count,sizeof(MenuRoomVertex));
            RCache.Render(D3DPT_TRIANGLELIST,offset,count/3); first+=count;
        }
    }
    RCache.set_CullMode(CULL_CCW);
}
