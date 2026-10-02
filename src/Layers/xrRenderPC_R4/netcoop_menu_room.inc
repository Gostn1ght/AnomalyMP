// A real, depth-tested menu room, independent of a running level/server.
// CPU geometry persists; GPU resources are released on device reset/teardown.
static void room_face(xr_vector<FVF::LIT>& vertices, const Fvector& a, const Fvector& b,
    const Fvector& c, const Fvector& d, u32 color)
{
    FVF::LIT v[4]; v[0].set(a, color, 0, 1); v[1].set(b, color, 0, 0);
    v[2].set(c, color, 1, 0); v[3].set(d, color, 1, 1);
    for (int index : {0, 1, 2, 0, 2, 3}) vertices.push_back(v[index]);
}
static void room_box(xr_vector<FVF::LIT>& v, float x, float y, float z, float w, float h, float depth, u32 color)
{
    const float l = x-w/2, r = x+w/2, b = y-h/2, t = y+h/2, f = z-depth/2, k = z+depth/2;
    auto p = [](float x, float y, float z) { Fvector result; result.set(x, y, z); return result; };
    auto shade = [color](float factor) { return color_rgba(_min(255u,u32(color_get_R(color)*factor)), _min(255u,u32(color_get_G(color)*factor)), _min(255u,u32(color_get_B(color)*factor)), 255); };
    room_face(v,p(l,b,f),p(l,t,f),p(r,t,f),p(r,b,f),color);
    room_face(v,p(r,b,k),p(r,t,k),p(l,t,k),p(l,b,k),shade(.55f));
    room_face(v,p(l,b,k),p(l,t,k),p(l,t,f),p(l,b,f),shade(.68f));
    room_face(v,p(r,b,f),p(r,t,f),p(r,t,k),p(r,b,k),shade(.8f));
    room_face(v,p(l,t,f),p(l,t,k),p(r,t,k),p(r,t,f),shade(1.1f));
    room_face(v,p(l,b,k),p(l,b,f),p(r,b,f),p(r,b,k),shade(.4f));
}
static ref_shader s_room_shaders[3];
static ref_geom s_room_geometry;
void netcoop_menu_room_release()
{
    for (auto& shader : s_room_shaders) shader.destroy();
    s_room_geometry.destroy();
}
static void room_draw(const xr_vector<FVF::LIT>& vertices, const char* texture, unsigned material)
{
    if (!s_room_shaders[material]) s_room_shaders[material].create("netcoop_room", texture);
    if (!s_room_geometry) s_room_geometry.create(FVF::F_LIT, RCache.Vertex.Buffer(), nullptr);
    u32 offset = 0;
    auto memory = static_cast<FVF::LIT*>(RCache.Vertex.Lock(u32(vertices.size()), sizeof(FVF::LIT), offset));
    CopyMemory(memory, vertices.data(), vertices.size()*sizeof(FVF::LIT));
    RCache.Vertex.Unlock(u32(vertices.size()), sizeof(FVF::LIT));
    RCache.set_Shader(s_room_shaders[material]); RCache.set_Geometry(s_room_geometry);
    RCache.set_CullMode(CULL_NONE);
    Fmatrix identity; identity.identity(); RCache.set_xform_world(identity);
    RCache.Render(D3DPT_TRIANGLELIST, offset, u32(vertices.size()/3));
}
static void draw_menu_room()
{
    static xr_vector<FVF::LIT> room, map, screen;
    if (room.empty())
    {
        // Plank floor, aged masonry and ceiling beams.
        for (int i=0; i<24; ++i)
            room_box(room,-3.f+(i+.5f)*.25f,-.045f,0,.245f,.07f,7.6f,color_rgba(62+(i%4)*4,49+(i%3)*3,34,255));
        room_box(room,0,1.6f,1.96f,6.4f,3.2f,.22f,color_rgba(51,53,45,255));
        for (int y=0;y<16;++y) for(int x=0;x<13;++x)
            room_box(room,-3.1f+x*.5f+(y%2)*.25f,.1f+y*.2f,1.835f,.485f,.185f,.035f,
                color_rgba(69+(x*13+y*7)%15,65+(x*7+y*11)%10,52+(x+y)%7,255));
        room_box(room,-3.25f,1.6f,-.4f,.15f,3.2f,4.7f,color_rgba(42,46,40,255));
        room_box(room,3.25f,1.6f,-.4f,.15f,3.2f,4.7f,color_rgba(42,46,40,255));
        for(int i=0;i<5;++i) room_box(room,-2.5f+i*1.25f,2.95f,-.2f,.13f,.2f,4.3f,color_rgba(43,33,24,255));
        // Wall map in a wooden frame. Clicking it opens entry/server controls.
        room_box(room,-1.12f,1.5f,1.78f,1.22f,.9f,.1f,color_rgba(54,36,22,255));
        Fvector a,b,c,d; a.set(-1.68f,1.1f,1.72f);b.set(-1.68f,1.9f,1.72f);
        c.set(-.56f,1.9f,1.72f);d.set(-.56f,1.1f,1.72f);
        room_face(map,a,b,c,d,color_rgba(200,186,139,255));
        // Workbench, drawer, radio and a lit handheld PDA for settings.
        room_box(room,1.25f,.73f,.45f,1.05f,.09f,.65f,color_rgba(92,66,38,255));
        for(float x : {.8f,1.7f}) for(float z : {.2f,.7f}) room_box(room,x,.35f,z,.08f,.7f,.08f,color_rgba(42,43,38,255));
        room_box(room,1.55f,.87f,.57f,.3f,.2f,.17f,color_rgba(45,49,42,255));
        room_box(room,1.64f,1.02f,.57f,.012f,.3f,.012f,color_rgba(92,93,78,255));
        room_box(room,1.1f,.87f,.15f,.33f,.2f,.055f,color_rgba(47,53,45,255));
        a.set(.97f,.79f,.118f);b.set(.97f,.94f,.118f);c.set(1.19f,.94f,.118f);d.set(1.19f,.79f,.118f);
        room_face(screen,a,b,c,d,color_rgba(132,208,125,255));
        // The equipment crate, straps, supply boxes and a cot.
        room_box(room,-1.25f,.25f,-.35f,.68f,.5f,.52f,color_rgba(73,79,48,255));
        for(float x : {-1.5f,-1.f}) room_box(room,x,.25f,-.621f,.04f,.5f,.016f,color_rgba(35,37,27,255));
        room_box(room,2.3f,.28f,1.2f,1.2f,.2f,.65f,color_rgba(63,66,49,255));
        for(float x : {1.77f,2.83f}) room_box(room,x,.16f,1.2f,.06f,.3f,.66f,color_rgba(37,41,36,255));
        room_box(room,-2.35f,.32f,1.15f,.62f,.64f,.6f,color_rgba(69,53,32,255));
        room_box(room,-2.35f,.82f,1.15f,.42f,.34f,.4f,color_rgba(76,59,34,255));
        // Warm hanging light and cable.
        room_box(room,0,2.7f,.5f,.025f,.45f,.025f,color_rgba(30,30,26,255));
        room_box(room,0,2.45f,.5f,.42f,.08f,.34f,color_rgba(112,100,69,255));
        room_box(room,0,2.39f,.5f,.27f,.04f,.2f,color_rgba(233,186,106,255));
    }
    room_draw(room,"ui\\netcoop_menu_solid",0);
    room_draw(map,"map\\map_escape",1);
    room_draw(screen,"pda_screen\\fix_pda",2);
    RCache.set_CullMode(CULL_CCW);
}
