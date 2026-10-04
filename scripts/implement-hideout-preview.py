from pathlib import Path
root=Path(__file__).resolve().parents[1]
def edit(name,pairs):
    p=root/name; s=p.read_text(encoding='cp1251')
    for before,after in pairs:
        assert before in s,(name,before[:80]);s=s.replace(before,after,1)
    p.write_text(s,encoding='cp1251')
edit('src/xrEngine/device.cpp',[
 ('Fvector().set(1.4f,1.7f,.1f),Fvector().set(-1.6f,1.f,-.85f)};', 'Fvector().set(1.4f,1.7f,.1f),Fvector().set(-1.6f,1.f,-.85f),Fvector().set(-.75f,1.1f,-.1f),Fvector().set(-.75f,1.45f,.1f)};'),
 ('Fvector().set(1.5f,.95f,1.1f),Fvector().set(-1.65f,.36f,.3f)};', 'Fvector().set(1.5f,.95f,1.1f),Fvector().set(-1.65f,.36f,.3f),Fvector().set(-1.55f,.65f,1.15f),Fvector().set(-1.9f,1.f,-1.2f)};'),
 ('static void load_config()\n{', 'static Fvector seat=Fvector().set(.45f,.61f,2.37f);\nstatic void load_config()\n{'),
 ('bool valid=file->length()==8+27*sizeof(float);\n    if(valid) valid=file->r_u32()==0x4352434e && file->r_u32()==1;\n    Fvector values[9];', '''const u32 bytes=file->length();
    bool valid=bytes==8+27*sizeof(float) || bytes==8+42*sizeof(float);
    u32 version=0;
    if(valid) { valid=file->r_u32()==0x4352434e; version=file->r_u32(); }
    valid=valid && ((version==1 && bytes==8+27*sizeof(float)) || (version==2 && bytes==8+42*sizeof(float)));
    const int cameras=version==2 ? 6 : 4;
    Fvector values[14];'''),
 ('file->r(values,sizeof(values));\n        for(const auto& value:values)\n            valid=valid && _valid(value) && _abs(value.x)<=1000.f && _abs(value.y)<=1000.f && _abs(value.z)<=1000.f;\n        for(int i=0;i<4;++i)', 'file->r(values,(cameras*2+(version==2 ? 2 : 1))*sizeof(Fvector));\n        for(int i=0;i<cameras*2+(version==2 ? 2 : 1);++i)\n            valid=valid && _valid(values[i]) && _abs(values[i].x)<=1000.f && _abs(values[i].y)<=1000.f && _abs(values[i].z)<=1000.f;\n        for(int i=0;i<cameras;++i)'),
 ('for(int i=0;i<4;++i) { eyes[i]=values[i*2]; targets[i]=values[i*2+1]; }\n    lamp=values[8];', 'for(int i=0;i<cameras;++i) { eyes[i]=values[i*2]; targets[i]=values[i*2+1]; }\n    lamp=values[cameras*2]; if(version==2) seat=values[13];'),
 ('/650.f)', '/850.f)'),
 ('object > 2', 'object > 4'),
 ('projection.build_projection(deg2rad(40.f)', 'projection.build_projection(deg2rad(52.f)'),
 ('targets[_max(0,_min(2,object))+1]', 'targets[_max(0,_min(4,object))+1]'),
 ('Fvector lamp_position() { load_config(); return lamp; }', 'Fvector lamp_position() { load_config(); return lamp; }\nFvector seat_position() { load_config(); return seat; }'),
])
edit('src/xrEngine/netcoop_menu_camera.h',[
 ('// -1 overview, 0 map, 1 PDA, 2 chest','// -1 overview, 0 map, 1 PDA, 2 backpack, 3 safe, 4 door'),
 ('ENGINE_API Fvector lamp_position();','ENGINE_API Fvector lamp_position();\nENGINE_API Fvector seat_position();'),
])
edit('src/xrGame/netcoop.cpp',[
 ('static u32 s_preview_restart = 0;', '''static u32 s_preview_restart = 0;
static bool s_preview_seated=false;
static u32 s_preview_idle_change=0,s_preview_frame=0;
static xr_vector<shared_str> s_preview_seated_motions;
static u32 s_preview_idle_seed=0x31415926;
static u32 preview_random() { s_preview_idle_seed=1664525u*s_preview_idle_seed+1013904223u; return s_preview_idle_seed; }'''),
 ('s_preview_name.clear(); s_preview_motion.clear(); s_preview_restart = 0;', 's_preview_name.clear(); s_preview_motion.clear(); s_preview_restart = 0;\n    s_preview_seated=false; s_preview_idle_change=s_preview_frame=0; s_preview_seated_motions.clear();'),
 ('s_preview_armed = pose < 0 && s_preview_item;', '''s_preview_seated=pose==-2;
    s_preview_armed = pose == -1 && s_preview_item;
    if (s_preview_seated)
    {
        s_preview_seated_motions.clear();
        for (LPCSTR candidate:{"animpoint_sit_normal_idle_1","animpoint_sit_normal_idle_2","animpoint_sit_normal_idle_3"})
            if (k->ID_Cycle_Safe(candidate).valid()) s_preview_seated_motions.push_back(candidate);
        if (s_preview_seated_motions.empty())
            for (LPCSTR candidate:{"sit_2_idle_0","sit_0_idle_0"})
                if(k->ID_Cycle_Safe(candidate).valid()) { s_preview_seated_motions.push_back(candidate); break; }
        if(s_preview_seated_motions.empty()) return false;
        motion=s_preview_seated_motions.front().c_str();
        s_preview_idle_seed=Device.dwTimeContinual|1; s_preview_idle_change=Device.dwTimeContinual+12000;
        Msg("[Lost Zone] sofa preview: %s, %u available idle motions",motion,u32(s_preview_seated_motions.size()));
    }'''),
 ('if (pose < 0)\n    {','if (pose == -1)\n    {'),
 ('combined.mul(projection, view); combined.transform(point);', '''Fvector local; view.transform_tiny(local,point);
    Fvector2 result; result.set(-10000,-10000);
    if (local.z<=.08f) return result;
    combined.mul(projection, view); combined.transform(point);'''),
 ('Fvector2 result; result.set((point.x + 1.f)', 'result.set((point.x + 1.f)'),
 ('if (auto k = s_preview_visual->dcast_PKinematicsAnimated())\n    {\n        if (s_preview_restart', '''if (auto k = s_preview_visual->dcast_PKinematicsAnimated())
    {
        if (s_preview_seated)
        {
            const u32 now=Device.dwTimeContinual;
            if(now>=s_preview_idle_change)
            {
                s_preview_motion=s_preview_seated_motions[preview_random()%s_preview_seated_motions.size()].c_str();
                const MotionID id=k->ID_Cycle_Safe(s_preview_motion.c_str());
                if (auto blend=k->PlayCycle(id,TRUE)) blend->speed=.90f+float(preview_random()%15)*.01f;
                s_preview_idle_change=now+12000+preview_random()%10000;
            }
            // The menu runs on a continual clock, independently of a paused game.
            k->LL_UpdateTracks(s_preview_frame ? _min(.066f,float(now-s_preview_frame)/1000.f) : 0.f,true,false);
            s_preview_frame=now;
        }
        if (!s_preview_seated && s_preview_restart'''),
 ('        k->UpdateTracks();\n    }\n    float heading=PI;', '        if(!s_preview_seated) k->UpdateTracks();\n    }\n    float heading=PI;'),
 ('world.c.y=_max(-.25f,_min(.25f,-s_preview_visual->getVisData().box.min.y));', '''world.c.y=_max(-.25f,_min(.25f,-s_preview_visual->getVisData().box.min.y));
    if(s_preview_seated)
    {
        if(auto skeleton=s_preview_visual->dcast_PKinematics())
        {
            const u16 pelvis=skeleton->LL_BoneID("bip01_pelvis");
            if(pelvis!=BI_NONE)
            {
                Fvector local; world.transform_dir(local,skeleton->LL_GetTransform(pelvis).c);
                world.c.sub(menu_room::seat_position(),local);
            }
        }
    }'''),
 ('Render->DrawUIModel(s_preview_visual, world, item, item ? &itemWorld : nullptr);', '''if(s_preview_seated && s_preview_item)
    {
        item=s_preview_item; itemWorld.setHPB(PI*.6f,0,PI*.5f);
        itemWorld.c.set(.3f,.70f,.57f);
        if (auto k=item->dcast_PKinematicsAnimated()) k->UpdateTracks();
        if (auto k=item->dcast_PKinematics()) k->CalculateBones(TRUE);
    }
    Render->DrawUIModel(s_preview_visual, world, item, item ? &itemWorld : nullptr);'''),
])
print('Six-camera menu and seated preview integrated')
