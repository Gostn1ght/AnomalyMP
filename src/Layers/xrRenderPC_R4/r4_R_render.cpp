#include "stdafx.h"
#include "../../xrEngine/igame_persistent.h"
#include "../xrRender/FBasicVisual.h"
#include "../../xrEngine/customhud.h"
#include "../../xrEngine/xr_object.h"

#include "../xrRender/QueryHelper.h"
#include "../xrRender/SkeletonX.h"
#include "../../xrEngine/netcoop_menu_camera.h"

static xr_string menu_material_textures(LPCSTR base)
{
    // Use the same THM material metadata as the game; don't guess bump filenames.
    ref_texture texture; texture.create(base);
    xr_string list = base;
    if (texture.bump_exist()) { list += ","; list += texture.bump_get().c_str(); }
    return list;
}

bool CRender::PrepareUIModel(IRenderVisual* visual)
{
    if (!visual) return false;
    if (auto children = visual->get_children())
    {
        bool ready = false;
        for (auto child : *children) ready = PrepareUIModel(child) || ready;
        return ready;
    }
    auto geometry = fast_dynamic_cast<dxRender_Visual*>(visual);
    if (!geometry || !geometry->shader) return false;
    auto skin = fast_dynamic_cast<CSkeletonX*>(visual);
    shader_option_skinning(skin ? skin->UISkinningMode() : -1);
    // Each cloned mesh gets its own shader; the shared source model is intact.
    ref_shader preview;
    const xr_string textures = menu_material_textures(visual->getDebugTexture());
    preview.create("netcoop_preview", textures.c_str());
    shader_option_skinning(-1);
    geometry->shader = preview;
    return !!preview;
}

static ref_rt s_menu_shadow_depth;
static ref_shader s_menu_depth_shaders[6];
static Fmatrix s_menu_shadow_matrix;
static u32 s_menu_shadow_time=0;
static STextureList s_menu_no_textures;
static ID3D11Query *s_menu_gpu_start=nullptr, *s_menu_gpu_end=nullptr, *s_menu_gpu_disjoint=nullptr;
static bool s_menu_gpu_pending=false, s_menu_gpu_recording=false;
static u32 s_menu_gpu_sample=0,s_menu_gpu_report=0,s_menu_gpu_count=0;
static double s_menu_gpu_total=0,s_menu_gpu_max=0;
static void menu_gpu_begin()
{
    if (!s_menu_gpu_start)
    {
        D3D11_QUERY_DESC desc={D3D11_QUERY_TIMESTAMP,0};
        if(FAILED(HW.pDevice->CreateQuery(&desc,&s_menu_gpu_start))) return;
        if(FAILED(HW.pDevice->CreateQuery(&desc,&s_menu_gpu_end))) { _RELEASE(s_menu_gpu_start); return; }
        desc.Query=D3D11_QUERY_TIMESTAMP_DISJOINT;
        if(FAILED(HW.pDevice->CreateQuery(&desc,&s_menu_gpu_disjoint)))
        { _RELEASE(s_menu_gpu_start); _RELEASE(s_menu_gpu_end); return; }
        s_menu_gpu_sample=s_menu_gpu_report=Device.dwTimeContinual;
    }
    if(s_menu_gpu_pending)
    {
        D3D11_QUERY_DATA_TIMESTAMP_DISJOINT data={}; UINT64 begin=0,end=0;
        if(HW.pContext->GetData(s_menu_gpu_disjoint,&data,sizeof(data),D3D11_ASYNC_GETDATA_DONOTFLUSH)==S_OK &&
           HW.pContext->GetData(s_menu_gpu_start,&begin,sizeof(begin),D3D11_ASYNC_GETDATA_DONOTFLUSH)==S_OK &&
           HW.pContext->GetData(s_menu_gpu_end,&end,sizeof(end),D3D11_ASYNC_GETDATA_DONOTFLUSH)==S_OK)
        {
            s_menu_gpu_pending=false;
            if(!data.Disjoint && data.Frequency && end>=begin)
            {
                const double ms=double(end-begin)*1000./double(data.Frequency);
                s_menu_gpu_total+=ms; s_menu_gpu_max=_max(s_menu_gpu_max,ms); ++s_menu_gpu_count;
                if(Device.dwTimeContinual-s_menu_gpu_report>=10000)
                {
                    Msg("[Lost Zone] menu GPU: avg %.2f ms, max %.2f ms, %u samples (1024 shadow, 20 Hz)",
                        s_menu_gpu_total/s_menu_gpu_count,s_menu_gpu_max,s_menu_gpu_count);
                    s_menu_gpu_total=s_menu_gpu_max=0; s_menu_gpu_count=0; s_menu_gpu_report=Device.dwTimeContinual;
                }
            }
        }
    }
    if(!s_menu_gpu_pending && Device.dwTimeContinual-s_menu_gpu_sample>=1000)
    {
        HW.pContext->Begin(s_menu_gpu_disjoint); HW.pContext->End(s_menu_gpu_start);
        s_menu_gpu_recording=true; s_menu_gpu_sample=Device.dwTimeContinual;
    }
}
static void menu_gpu_end()
{
    if(!s_menu_gpu_recording) return;
    HW.pContext->End(s_menu_gpu_end); HW.pContext->End(s_menu_gpu_disjoint);
    s_menu_gpu_recording=false; s_menu_gpu_pending=true;
}
static void release_menu_shadow()
{
    for(auto& shader:s_menu_depth_shaders) shader.destroy();
    s_menu_shadow_depth.destroy(); s_menu_shadow_time=0;
    _RELEASE(s_menu_gpu_start); _RELEASE(s_menu_gpu_end); _RELEASE(s_menu_gpu_disjoint);
    s_menu_gpu_pending=s_menu_gpu_recording=false;
    s_menu_gpu_count=0; s_menu_gpu_total=s_menu_gpu_max=0;
}
static void draw_ui_geometry(IRenderVisual* visual, const Fmatrix& world, bool depth=false)
{
    if (auto children = visual->get_children())
    {
        for (auto child : *children) draw_ui_geometry(child, world, depth);
        return;
    }
    auto geometry = fast_dynamic_cast<dxRender_Visual*>(visual);
    if (!geometry || !geometry->shader) return;
    if (depth)
    {
        auto skin=fast_dynamic_cast<CSkeletonX*>(visual);
        const int mode=skin ? skin->UISkinningMode() : -1;
        auto& shader=s_menu_depth_shaders[_max(0,_min(5,mode+1))];
        if(!shader)
        {
            RImplementation.shader_option_skinning(mode);
            shader.create("netcoop_preview_depth");
            RImplementation.shader_option_skinning(-1);
        }
        RCache.set_Shader(shader);
    }
    else RCache.set_Shader(geometry->shader);
    const Fvector lamp=menu_room::lamp_position();
    RCache.set_c("menu_room_lamp",lamp.x,lamp.y,lamp.z,1.f);
    RCache.set_c("m_menu_shadow",s_menu_shadow_matrix);
    RCache.set_xform_world(world);
    geometry->Render(1.f);
}


#include "../../xrEngine/netcoop_menu_camera.h"
#include "netcoop_menu_room.inc"

void CRender::DrawUIModel(IRenderVisual* visual, const Fmatrix& world, IRenderVisual* item, const Fmatrix* itemWorld)
{
    if (!visual || g_pGameLevel) return;
    menu_gpu_begin();
    const Fmatrix old_world = RCache.xforms.m_w, old_view = RCache.xforms.m_v, old_projection = RCache.xforms.m_p;
    // One small shadow map for the private room, refreshed at most 20 Hz.
    // The menu never submits a full game level, AI, or physics to the renderer.
    if (!s_menu_shadow_depth || Device.dwTimeContinual-s_menu_shadow_time>=50)
    {
        if(!s_menu_shadow_depth) s_menu_shadow_depth.create("$user$menu_room_shadow",1024,1024,D3DFMT_D24S8);
        ID3DRenderTargetView* targets[4]={RCache.get_RT(0),RCache.get_RT(1),RCache.get_RT(2),RCache.get_RT(3)};
        auto depth=RCache.get_ZB();
        D3D_VIEWPORT viewport; UINT count=1; HW.pContext->RSGetViewports(&count,&viewport);
        RCache.set_Textures(&s_menu_no_textures);
        for(u32 i=0;i<4;++i) RCache.set_RT(nullptr,i);
        RCache.set_ZB(s_menu_shadow_depth->pZRT);
        const D3D_VIEWPORT shadow_viewport={0,0,1024,1024,0,1}; HW.pContext->RSSetViewports(1,&shadow_viewport);
        HW.pContext->ClearDepthStencilView(s_menu_shadow_depth->pZRT,D3D_CLEAR_DEPTH,1.f,0);
        Fmatrix light_view,light_projection,bias,light_combined;
        Fvector light_eye=menu_room::lamp_position();
        Fvector light_target=Fvector().set(light_eye.x,light_eye.y-1.f,light_eye.z+.01f);
        light_view.build_camera(light_eye,light_target,Fvector().set(0,0,1));
        light_projection.build_projection(deg2rad(110.f),1.f,.1f,12.f);
        light_combined.mul(light_projection,light_view);
        bias.identity(); bias._11=.5f; bias._22=-.5f; bias._41=.5f; bias._42=.5f;
        s_menu_shadow_matrix.mul(bias,light_combined);
        RCache.set_xform_view(light_view); RCache.set_xform_project(light_projection);
        RCache.set_Stencil(FALSE); RCache.set_CullMode(CULL_NONE);
        draw_menu_room(true); draw_ui_geometry(visual,world,true);
        if(item && itemWorld) draw_ui_geometry(item,*itemWorld,true);
        RCache.set_Textures(&s_menu_no_textures);
        for(u32 i=0;i<4;++i) RCache.set_RT(targets[i],i);
        RCache.set_ZB(depth); HW.pContext->RSSetViewports(1,&viewport);
        s_menu_shadow_time=Device.dwTimeContinual;
    }
    Fmatrix view, projection;
    menu_room::matrices(view, projection);
    HW.pContext->ClearDepthStencilView(HW.pBaseZB, D3D_CLEAR_DEPTH, 1.f, 0);
    RCache.set_xform_view(view); RCache.set_xform_project(projection);
    RCache.set_Stencil(FALSE); RCache.set_ColorWriteEnable();
    draw_menu_room();
    draw_ui_geometry(visual, world);
    if (item && itemWorld) draw_ui_geometry(item, *itemWorld);
    menu_gpu_end();
    RCache.set_xform_world(old_world); RCache.set_xform_view(old_view); RCache.set_xform_project(old_projection);
}

IC bool pred_sp_sort(ISpatial* _1, ISpatial* _2)
{
	float d1 = _1->spatial.sphere.P.distance_to_sqr(Device.vCameraPosition);
	float d2 = _2->spatial.sphere.P.distance_to_sqr(Device.vCameraPosition);
	return d1 < d2;
}

void CRender::render_main(Fmatrix& m_ViewProjection, bool _fportals)
{
	PIX_EVENT(render_main);
	//	Msg						("---begin");
	marker ++;

	// Calculate sector(s) and their objects
	if (pLastSector)
	{
		//!!!
		//!!! BECAUSE OF PARALLEL HOM RENDERING TRY TO DELAY ACCESS TO HOM AS MUCH AS POSSIBLE
		//!!!
		{
			// Traverse object database
			g_SpatialSpace->q_frustum
			(
				lstRenderables,
				ISpatial_DB::O_ORDERED,
				STYPE_RENDERABLE + STYPE_LIGHTSOURCE,
				ViewBase
			);

			// (almost) Exact sorting order (front-to-back)
			std::sort(lstRenderables.begin(), lstRenderables.end(), pred_sp_sort);

			// Determine visibility for dynamic part of scene
			set_Object(0);
			u32 uID_LTRACK = 0xffffffff;
			if (phase == PHASE_NORMAL)
			{
				uLastLTRACK ++;
				if (lstRenderables.size()) uID_LTRACK = uLastLTRACK % lstRenderables.size();

				// update light-vis for current entity / actor
				CObject* O = g_pGameLevel->CurrentViewEntity();
				if (O)
				{
					CROS_impl* R = (CROS_impl*)O->ROS();
					if (R) R->update(O);
				}

				// update light-vis for selected entity
				// track lighting environment
				if (lstRenderables.size())
				{
					IRenderable* renderable = lstRenderables[uID_LTRACK]->dcast_Renderable();
					if (renderable)
					{
						CROS_impl* T = (CROS_impl*)renderable->renderable_ROS();
						if (T) T->update(renderable);
					}
				}
			}
		}

		// Traverse sector/portal structure
		PortalTraverser.traverse
		(
			pLastSector,
			ViewBase,
			Device.vCameraPosition,
			m_ViewProjection,
			CPortalTraverser::VQ_HOM + CPortalTraverser::VQ_SSA + CPortalTraverser::VQ_FADE
			//. disabled scissoring (HW.Caps.bScissor?CPortalTraverser::VQ_SCISSOR:0)	// generate scissoring info
		);

		// Determine visibility for static geometry hierrarhy
		for (u32 s_it = 0; s_it < PortalTraverser.r_sectors.size(); s_it++)
		{
			CSector* sector = (CSector*)PortalTraverser.r_sectors[s_it];
			dxRender_Visual* root = sector->root();
			for (u32 v_it = 0; v_it < sector->r_frustums.size(); v_it++)
			{
				set_Frustum(&(sector->r_frustums[v_it]));
				add_Geometry(root);
			}
		}

		// Traverse frustums
		for (u32 o_it = 0; o_it < lstRenderables.size(); o_it++)
		{
			ISpatial* spatial = lstRenderables[o_it];
			spatial->spatial_updatesector();
			CSector* sector = (CSector*)spatial->spatial.sector;
			if (0 == sector) continue; // disassociated from S/P structure

			if (spatial->spatial.type & STYPE_LIGHTSOURCE)
			{
				// lightsource
				light* L = (light*)(spatial->dcast_Light());
				VERIFY(L);
				float lod = L->get_LOD();
				if (lod > EPS_L)
				{
					vis_data& vis = L->get_homdata();
					if (HOM.visible(vis)) Lights.add_light(L);
				}
				continue ;
			}

			if (PortalTraverser.i_marker != sector->r_marker) continue; // inactive (untouched) sector
			for (u32 v_it = 0; v_it < sector->r_frustums.size(); v_it++)
			{
				CFrustum& view = sector->r_frustums[v_it];
				if (!view.testSphere_dirty(spatial->spatial.sphere.P, spatial->spatial.sphere.R)) continue;

				if (spatial->spatial.type & STYPE_RENDERABLE)
				{
					// renderable
					IRenderable* renderable = spatial->dcast_Renderable();
					VERIFY(renderable);

					// Occlusion
					//	casting is faster then using getVis method
					vis_data& v_orig = ((dxRender_Visual*)renderable->renderable.visual)->vis;
					vis_data v_copy = v_orig;
					v_copy.box.xform(renderable->renderable.xform);
					BOOL bVisible = HOM.visible(v_copy);
					v_orig.marker = v_copy.marker;
					v_orig.accept_frame = v_copy.accept_frame;
					v_orig.hom_frame = v_copy.hom_frame;
					v_orig.hom_tested = v_copy.hom_tested;
					if (!bVisible) break; // exit loop on frustums

					// Rendering
					set_Object(renderable);
					renderable->renderable_Render();
					set_Object(0);
				}
				break; // exit loop on frustums
			}
		}
		if (g_pGameLevel && (phase == PHASE_NORMAL))
		{
			g_hud->Render_Last(); // HUD
			if (g_hud->RenderActiveItemUIQuery())
				r_dsgraph_render_hud_ui();
			if (g_hud->RenderCamAttachedUIQuery())
				r_dsgraph_render_cam_ui();
		}
	}
	else
	{
		set_Object(0);
		if (g_pGameLevel && (phase == PHASE_NORMAL))
		{
			g_hud->Render_Last(); // HUD
			if (g_hud->RenderActiveItemUIQuery())
				r_dsgraph_render_hud_ui();
			if (g_hud->RenderCamAttachedUIQuery())
				r_dsgraph_render_cam_ui();
		}
	}
}

void CRender::render_menu()
{
	PIX_EVENT(render_menu);
	//	Globals
	RCache.set_CullMode(CULL_CCW);
	RCache.set_Stencil(FALSE);
	RCache.set_ColorWriteEnable();

	// Main Render
	{
		Target->u_setrt(Target->rt_Generic_0, 0, 0, HW.pBaseZB); // LDR RT
		if (!g_pGameLevel && strstr(Core.Params, "-netcoop"))
		{
			// The 3D room does not cover every pixel. Never keep the previous
			// account screen or a closed dialog in the persistent menu target.
			const FLOAT clear[4] = { .012f, .015f, .012f, 1.f };
			HW.pContext->ClearRenderTargetView(Target->rt_Generic_0->pRT, clear);
		}
		g_pGamePersistent->OnRenderPPUI_main(); // PP-UI
	}

	// Distort
	{
		FLOAT ColorRGBA[4] = {127.0f / 255.0f, 127.0f / 255.0f, 0.0f, 127.0f / 255.0f};
		Target->u_setrt(Target->rt_Generic_1, 0, 0, HW.pBaseZB); // Now RT is a distortion mask
		HW.pContext->ClearRenderTargetView(Target->rt_Generic_1->pRT, ColorRGBA);
		g_pGamePersistent->OnRenderPPUI_PP(); // PP-UI
	}

	// Actual Display
	Target->u_setrt(Device.dwWidth, Device.dwHeight, HW.pBaseRT,NULL,NULL, HW.pBaseZB);
	RCache.set_Shader(Target->s_menu);
	RCache.set_Geometry(Target->g_menu);

	Fvector2 p0, p1;
	u32 Offset;
	u32 C = color_rgba(255, 255, 255, 255);
	float _w = float(Device.dwWidth);
	float _h = float(Device.dwHeight);
	float d_Z = EPS_S;
	float d_W = 1.f;
	p0.set(.5f / _w, .5f / _h);
	p1.set((_w + .5f) / _w, (_h + .5f) / _h);

	FVF::TL* pv = (FVF::TL*)RCache.Vertex.Lock(4, Target->g_menu->vb_stride, Offset);
	pv->set(EPS, float(_h + EPS), d_Z, d_W, C, p0.x, p1.y);
	pv++;
	pv->set(EPS, EPS, d_Z, d_W, C, p0.x, p0.y);
	pv++;
	pv->set(float(_w + EPS), float(_h + EPS), d_Z, d_W, C, p1.x, p1.y);
	pv++;
	pv->set(float(_w + EPS), EPS, d_Z, d_W, C, p1.x, p0.y);
	pv++;
	RCache.Vertex.Unlock(4, Target->g_menu->vb_stride);
	RCache.Render(D3DPT_TRIANGLELIST, Offset, 0, 4, 0, 2);
}

extern u32 g_r;

void CRender::Render()
{
	PIX_EVENT(CRender_Render);

	VERIFY(0 == mapDistort.size() + mapHUDDistort.size());

	rmNormal();

	bool _menu_pp = g_pGamePersistent ? g_pGamePersistent->OnRenderPPUI_query() : false;
	if (_menu_pp)
	{
		render_menu();
		return;
	};

	IMainMenu* pMainMenu = g_pGamePersistent ? g_pGamePersistent->m_pMainMenu : 0;
	bool bMenu = pMainMenu ? pMainMenu->CanSkipSceneRendering() : false;

	if (!(g_pGameLevel && g_hud)
		|| bMenu)
	{
		Target->u_setrt(Device.dwWidth, Device.dwHeight, HW.pBaseRT,NULL,NULL, HW.pBaseZB);
		if (!g_pGameLevel && strstr(Core.Params, "-netcoop"))
		{
			const FLOAT clear[4] = { .012f, .015f, .012f, 1.f };
			HW.pContext->ClearRenderTargetView(HW.pBaseRT, clear);
		}
		return;
	}

	if (m_bFirstFrameAfterReset)
	{
		m_bFirstFrameAfterReset = false;
		return;
	}

	//.	VERIFY					(g_pGameLevel && g_pGameLevel->pHUD);

	// Configure
	RImplementation.o.distortion = FALSE; // disable distorion
	Fcolor sun_color = ((light*)Lights.sun_adapted._get())->color;
	BOOL bSUN = ps_r2_ls_flags.test(R2FLAG_SUN) && (u_diffuse2s(sun_color.r, sun_color.g, sun_color.b)>EPS) && !strstr(Core.Params, "-r4_dev");
	if (o.sunstatic) bSUN = FALSE;
	// Msg						("sstatic: %s, sun: %s",o.sunstatic?;"true":"false", bSUN?"true":"false");

	// HOM
	ViewBase.CreateFromMatrix(Device.mFullTransform, FRUSTUM_P_LRTB + FRUSTUM_P_FAR);
	View = 0;
	if (!ps_r2_ls_flags.test(R2FLAG_EXP_MT_CALC))
	{
		HOM.Enable();
		HOM.Render(ViewBase);
	}

	//******* Z-prefill calc - DEFERRER RENDERER
	if (ps_r2_ls_flags.test(R2FLAG_ZFILL))
	{
		PIX_EVENT(DEFER_Z_FILL);
		Device.Statistic->RenderCALC.Begin();
		float z_distance = ps_r2_zfill;
		Fmatrix m_zfill, m_project;
		m_project.build_projection(
			deg2rad(Device.fFOV/* *Device.fASPECT*/),
			Device.fASPECT, VIEWPORT_NEAR,
			z_distance * g_pGamePersistent->Environment().CurrentEnv->far_plane);
		m_zfill.mul(m_project, Device.mView);
		r_pmask(true, false); // enable priority "0"
		set_Recorder(NULL);
		phase = PHASE_SMAP;
		render_main(m_zfill, false);
		r_pmask(true, false); // disable priority "1"
		Device.Statistic->RenderCALC.End();

		// flush
		Target->phase_scene_prepare();
		RCache.set_ColorWriteEnable(FALSE);
		r_dsgraph_render_graph(0);
		RCache.set_ColorWriteEnable();
	}
	else
	{
		Target->phase_scene_prepare();
	}

	//*******
	// Sync point
	Device.Statistic->RenderDUMP_Wait_S.Begin();
	if (ps_r2_qsync)
	{
		CTimer T;
		T.Start();
		BOOL result = FALSE;
		HRESULT hr = S_FALSE;
		//while	((hr=q_sync_point[q_sync_count]->GetData	(&result,sizeof(result),D3DGETDATA_FLUSH))==S_FALSE) {
		while ((hr = GetData(q_sync_point[q_sync_count], &result, sizeof(result))) == S_FALSE)
		{
			if (!SwitchToThread()) Sleep(ps_r2_wait_sleep);
			if (T.GetElapsed_ms() > 500)
			{
				result = FALSE;
				break;
			}
		}
	}
	Device.Statistic->RenderDUMP_Wait_S.End();
	q_sync_count = (q_sync_count + 1) % HW.Caps.iGPUNum;
	//CHK_DX										(q_sync_point[q_sync_count]->Issue(D3DISSUE_END));
	CHK_DX(EndQuery(q_sync_point[q_sync_count]));

	//******* Main calc - DEFERRER RENDERER
	// Main calc
	Device.Statistic->RenderCALC.Begin();
	r_pmask(true, false, true); // enable priority "0",+ capture wmarks
	if (bSUN) set_Recorder(&main_coarse_structure);
	else set_Recorder(NULL);
	phase = PHASE_NORMAL;
	render_main(Device.mFullTransform, true);
	set_Recorder(NULL);
	r_pmask(true, false); // disable priority "1"
	Device.Statistic->RenderCALC.End();
	
	/*if (RImplementation.o.ssfx_core) // SSS23: DEPRECATED
	{
		// HUD Masking rendering
		FLOAT ColorRGBA[4] = { 1.0f, 0.0f, 0.0f, 1.0f };
		HW.pContext->ClearRenderTargetView(Target->rt_ssfx_hud->pRT, ColorRGBA);

		Target->u_setrt(Target->rt_ssfx_hud, NULL, NULL, HW.pBaseZB);
		r_dsgraph_render_hud(true);

		// Reset Depth
		HW.pContext->ClearDepthStencilView(HW.pBaseZB, D3D_CLEAR_DEPTH, 1.0f, 0);
	}*/

	if (RImplementation.o.ssfx_motionvectors)
	{
		Target->u_setrt(Device.dwWidth, Device.dwHeight, 0, 0, Target->rt_ssfx_motion_vectors->pRT, 0);

		FLOAT ColorRGBA[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
		HW.pContext->ClearRenderTargetView(Target->rt_ssfx_motion_vectors->pRT, ColorRGBA);

		RCache.set_Stencil(FALSE);
		g_pGamePersistent->Environment().RenderSky(true);

		RCache.Index.Flush();
		RCache.Vertex.Flush();

		RCache.set_xform_world(Fidentity);
	}

	if (ps_r2_ls_flags.test(R2FLAG_TERRAIN_PREPASS))
	{
		Target->u_setrt(Device.dwWidth, Device.dwHeight, NULL, NULL, NULL, !RImplementation.o.dx10_msaa ? HW.pBaseZB : Target->rt_MSAADepth->pZRT);
		r_dsgraph_render_landscape(0, false);
	}

	BOOL split_the_scene_to_minimize_wait = FALSE;
	if (ps_r2_ls_flags.test(R2FLAG_EXP_SPLIT_SCENE)) split_the_scene_to_minimize_wait = TRUE;

	//******* Main render :: PART-0	-- first
	if (!split_the_scene_to_minimize_wait)
	{
		PIX_EVENT(DEFER_PART0_NO_SPLIT);
		// level, DO NOT SPLIT
		Target->phase_scene_begin();
		r_dsgraph_render_hud();
		r_dsgraph_render_graph(0);
		r_dsgraph_render_lods(true, true);
		if (Details) Details->Render();
		if (ps_r2_ls_flags.test(R2FLAG_TERRAIN_PREPASS)) r_dsgraph_render_landscape(1, true);
		Target->phase_scene_end();
	}
	else
	{
		PIX_EVENT(DEFER_PART0_SPLIT);
		// level, SPLIT
		Target->phase_scene_begin();
		r_dsgraph_render_graph(0);
		Target->disable_aniso();
	}

	//  Redotix99: for 3D Shader Based Scopes 	
	if (scope_3D_fake_enabled)
	{
		ID3D11Resource* zbuffer_res;
		HW.pBaseZB->GetResource(&zbuffer_res);
		HW.pContext->CopyResource(RImplementation.Target->rt_tempzb->pSurface, zbuffer_res);
	}

	//******* Occlusion testing of volume-limited light-sources
	Target->phase_occq();
	LP_normal.clear();
	LP_pending.clear();
	if (RImplementation.o.dx10_msaa)
		RCache.set_ZB(RImplementation.Target->rt_MSAADepth->pZRT);
	{
		PIX_EVENT(DEFER_TEST_LIGHT_VIS);
		// perform tests
		u32 count = 0;
		light_Package& LP = Lights.package;

		// stats
		stats.l_shadowed = LP.v_shadowed.size();
		stats.l_unshadowed = LP.v_point.size() + LP.v_spot.size();
		stats.l_total = stats.l_shadowed + stats.l_unshadowed;

		// perform tests
		count = _max(count, LP.v_point.size());
		count = _max(count, LP.v_spot.size());
		count = _max(count, LP.v_shadowed.size());
		for (u32 it = 0; it < count; it++)
		{
			if (it < LP.v_point.size())
			{
				light* L = LP.v_point[it];
				L->vis_prepare();
				if (L->vis.pending) LP_pending.v_point.push_back(L);
				else LP_normal.v_point.push_back(L);
			}
			if (it < LP.v_spot.size())
			{
				light* L = LP.v_spot[it];
				L->vis_prepare();
				if (L->vis.pending) LP_pending.v_spot.push_back(L);
				else LP_normal.v_spot.push_back(L);
			}
			if (it < LP.v_shadowed.size())
			{
				light* L = LP.v_shadowed[it];
				L->vis_prepare();
				if (L->vis.pending) LP_pending.v_shadowed.push_back(L);
				else LP_normal.v_shadowed.push_back(L);
			}
		}
	}
	LP_normal.sort();
	LP_pending.sort();

	//******* Main render :: PART-1 (second)
	if (split_the_scene_to_minimize_wait)
	{
		PIX_EVENT(DEFER_PART1_SPLIT);
		// skybox can be drawn here
		
		if (0)
		{
			if (!RImplementation.o.dx10_msaa)
				Target->u_setrt(Target->rt_Generic_0, Target->rt_Generic_1, 0, HW.pBaseZB);
			else
				Target->u_setrt(Target->rt_Generic_0_r, Target->rt_Generic_1, 0,
				                RImplementation.Target->rt_MSAADepth->pZRT);
			RCache.set_CullMode(CULL_NONE);
			RCache.set_Stencil(FALSE);

			// draw skybox
			RCache.set_ColorWriteEnable();
			//CHK_DX(HW.pDevice->SetRenderState			( D3DRS_ZENABLE,	FALSE				));
			RCache.set_Z(FALSE);
			g_pGamePersistent->Environment().RenderSky();
			//CHK_DX(HW.pDevice->SetRenderState			( D3DRS_ZENABLE,	TRUE				));
			RCache.set_Z(TRUE);
		}

		// level
		Target->phase_scene_begin();
		r_dsgraph_render_hud();
		r_dsgraph_render_lods(true, true);
		if (Details) Details->Render();
		if (ps_r2_ls_flags.test(R2FLAG_TERRAIN_PREPASS)) r_dsgraph_render_landscape(1, true);
		Target->phase_scene_end();
	}

	// Wall marks
	if (Wallmarks)
	{
		PIX_EVENT(DEFER_WALLMARKS);
		Target->phase_wallmarks();

		Wallmarks->Render(); // wallmarks has priority as normal geometry
	}

	// Update incremental shadowmap-visibility solver
	{
		PIX_EVENT(DEFER_FLUSH_OCCLUSION);
		u32 it = 0;
		for (it = 0; it < Lights_LastFrame.size(); it++)
		{
			if (0 == Lights_LastFrame[it]) continue ;
			try
			{
				Lights_LastFrame[it]->svis.flushoccq();
			}
			catch (...)
			{
				Msg("! Failed to flush-OCCq on light [%d] %X", it, *(u32*)(&Lights_LastFrame[it]));
			}
		}
		Lights_LastFrame.clear();
	}

	// full screen pass to mark msaa-edge pixels in highest stencil bit
	if (RImplementation.o.dx10_msaa)
	{
		PIX_EVENT(MARK_MSAA_EDGES);
		Target->mark_msaa_edges();
	}

	//	TODO: DX10: Implement DX10 rain.
	if (ps_r2_ls_flags.test(R3FLAG_DYN_WET_SURF))
	{
		PIX_EVENT(DEFER_RAIN);
		render_rain();
	}

	{
		// Save previus and current matrices
		{
			static Fmatrix mm_saved_viewproj;

			if (!Device.m_SecondViewport.IsSVPFrame())
			{
				Target->Matrix_previous.mul(mm_saved_viewproj, Device.mInvView);
				Target->Matrix_current.set(Device.mProject);
				mm_saved_viewproj.set(Device.mFullTransform);
			}
		}

		if (RImplementation.o.ssfx_sss && !Device.m_SecondViewport.IsSVPFrame())
		{
			static bool sss_rendered, sss_extended_rendered;

			// SSS Shadows
			if (ps_ssfx_sss_quality.z > 0)
			{
				Target->phase_ssfx_sss();
				sss_rendered = true;
			}
			else
			{
				if (sss_rendered) // Clear buffer
				{
					sss_rendered = false;
					FLOAT ColorRGBA[4] = { 1,1,1,1 };
					HW.pContext->ClearRenderTargetView(Target->rt_ssfx_sss->pRT, ColorRGBA);
				}
			}

			if (ps_ssfx_sss_quality.w > 0)
			{
				// Extra lights
				Target->phase_ssfx_sss_ext(Lights.package);
				sss_extended_rendered = true;
			}
			else
			{
				if (sss_extended_rendered) // Clear buffer
				{
					sss_extended_rendered = false;
					FLOAT ColorRGBA[4] = { 1,1,1,1 };
					HW.pContext->ClearRenderTargetView(Target->rt_ssfx_sss_tmp->pRT, ColorRGBA);
				}
			}
		}
	}

	// Directional light - fucking sun
	if (bSUN) //bSUN && Device.dwFrame & 1 --Delayed sun update. Worth to check it in future
	{
		PIX_EVENT(DEFER_SUN);
		RImplementation.stats.l_visible ++;
		if (!ps_r2_ls_flags_ext.is(R2FLAGEXT_SUN_OLD))
			render_sun_cascades();
		else
		{
			render_sun_near();
			render_sun();
			render_sun_filtered();
		}
		Target->accum_direct_blend();
	}

	{
		PIX_EVENT(DEFER_SELF_ILLUM);
		Target->phase_accumulator();
		// Render emissive geometry, stencil - write 0x0 at pixel pos
		RCache.set_xform_project(Device.mProject);
		RCache.set_xform_view(Device.mView);
		// Stencil - write 0x1 at pixel pos - 
		if (!RImplementation.o.dx10_msaa)
			RCache.set_Stencil(TRUE, D3DCMP_ALWAYS, 0x01, 0xff, 0xff, D3DSTENCILOP_KEEP, D3DSTENCILOP_REPLACE,
			                   D3DSTENCILOP_KEEP);
		else
			RCache.set_Stencil(TRUE, D3DCMP_ALWAYS, 0x01, 0xff, 0x7f, D3DSTENCILOP_KEEP, D3DSTENCILOP_REPLACE,
			                   D3DSTENCILOP_KEEP);
		//RCache.set_Stencil				(TRUE,D3DCMP_ALWAYS,0x00,0xff,0xff,D3DSTENCILOP_KEEP,D3DSTENCILOP_REPLACE,D3DSTENCILOP_KEEP);
		RCache.set_CullMode(CULL_CCW);
		RCache.set_ColorWriteEnable();
		RImplementation.r_dsgraph_render_emissive(RImplementation.o.ssfx_bloom ? false : true);
	}

	if (RImplementation.o.ssfx_bloom)
	{
		// Render Emissive on `rt_ssfx_bloom_emissive`
		FLOAT ColorRGBA[4] = { 0,0,0,0 };
		HW.pContext->ClearRenderTargetView(Target->rt_ssfx_bloom_emissive->pRT, ColorRGBA);
		Target->u_setrt(Target->rt_ssfx_bloom_emissive, NULL, NULL, !RImplementation.o.dx10_msaa ? HW.pBaseZB : Target->rt_MSAADepth->pZRT);
		RImplementation.r_dsgraph_render_emissive(true, true);
	}

	// Lighting, non dependant on OCCQ
	{
		PIX_EVENT(DEFER_LIGHT_NO_OCCQ);
		Target->phase_accumulator();
		HOM.Disable();
		render_lights(LP_normal);
	}

	// Lighting, dependant on OCCQ
	{
		PIX_EVENT(DEFER_LIGHT_OCCQ);
		render_lights(LP_pending);
	}

	{
		if (RImplementation.o.ssfx_volumetric)
			Target->phase_ssfx_volumetric_blur();
	}

	// Postprocess
	{
		PIX_EVENT(DEFER_LIGHT_COMBINE);
		Target->phase_combine();
	}

	if (Details)
		Details->details_clear();

	VERIFY(0 == mapDistort.size() + mapHUDDistort.size());
}

void CRender::render_forward()
{
	VERIFY(0 == mapDistort.size() + mapHUDDistort.size());
	RImplementation.o.distortion = RImplementation.o.distortion_enabled; // enable distorion

	//******* Main render - second order geometry (the one, that doesn't support deffering)
	//.todo: should be done inside "combine" with estimation of of luminance, tone-mapping, etc.
	{
		// level
		r_pmask(false, true); // enable priority "1"
		phase = PHASE_NORMAL;
		render_main(Device.mFullTransform, false); //
		//	Igor: we don't want to render old lods on next frame.
		mapLOD.clear();
		r_dsgraph_render_graph(1); // normal level, secondary priority
		PortalTraverser.fade_render(); // faded-portals
		r_dsgraph_render_sorted(); // strict-sorted geoms
		//g_pGamePersistent->Environment().RenderLast(); // rain/thunder-bolts
	}

	RImplementation.o.distortion = FALSE; // disable distorion
}

// Redotix99: for 3D Shader Based Scopes
void CRender::render_Reticle()
{
	VERIFY(0 == mapDistort.size() + mapHUDDistort.size());
	RImplementation.o.distortion = RImplementation.o.distortion_enabled;

	r_dsgraph_render_ScopeSorted();

	RImplementation.o.distortion = FALSE;
}

void CRender::RenderToTarget(RRT target)
{
	ref_rt* RT = nullptr;

	switch (target)
	{
	case rtPDA:
		RT = &Target->rt_ui_pda;
		break;
	case rtSVP:
		RT = &Target->rt_secondVP;
		break;
	default:
		Debug.fatal(DEBUG_INFO, "None or wrong Target specified: %i", target);
		break;
	}

	ID3DTexture2D* pBuffer = nullptr;
	HW.m_pSwapChain->GetBuffer(0, __uuidof(ID3D11Texture2D), (LPVOID*)&pBuffer);
	HW.pContext->CopyResource((*RT)->pSurface, pBuffer);
	pBuffer->Release();
}

// Downsample the dedicated PDA target; the game backbuffer is never exposed
// through this API. Network capture is limited to three frames per second.
bool CRender::CapturePdaPixels(u32 width, u32 height, u8* pixels, const Fvector4& crop)
{
    if (!width || !height || width > 256 || height > 192 || !pixels || !Target || !Target->rt_ui_pda) return false;
    ID3D11Texture2D* source = Target->rt_ui_pda->pSurface;
    D3D11_TEXTURE2D_DESC desc; source->GetDesc(&desc);
    if (crop.x < 0.f || crop.y < 0.f || crop.z > 1.f || crop.w > 1.f || crop.x >= crop.z || crop.y >= crop.w) return false;
    const u32 left = u32(crop.x * desc.Width), top = u32(crop.y * desc.Height);
    const u32 crop_width = _max(1u, u32((crop.z - crop.x) * desc.Width));
    const u32 crop_height = _max(1u, u32((crop.w - crop.y) * desc.Height));
    if (desc.Format != DXGI_FORMAT_R8G8B8A8_UNORM && desc.Format != DXGI_FORMAT_B8G8R8A8_UNORM &&
        desc.Format != DXGI_FORMAT_R10G10B10A2_UNORM) return false;
    desc.Usage = D3D11_USAGE_STAGING; desc.BindFlags = 0; desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ; desc.MiscFlags = 0;
    ID3D11Texture2D* staging = nullptr;
    if (FAILED(HW.pDevice->CreateTexture2D(&desc, nullptr, &staging))) return false;
    HW.pContext->CopyResource(staging, source);
    D3D11_MAPPED_SUBRESOURCE mapped;
    if (FAILED(HW.pContext->Map(staging, 0, D3D11_MAP_READ, 0, &mapped))) { staging->Release(); return false; }
    for (u32 y = 0; y < height; ++y)
    {
        const u32 sy = _min(desc.Height - 1, top + y * crop_height / height);
        const u32* row = (const u32*)((const u8*)mapped.pData + sy * mapped.RowPitch);
        for (u32 x = 0; x < width; ++x)
        {
            const u32 pixel = row[_min(desc.Width - 1, left + x * crop_width / width)];
            u32 red, green, blue;
            if (desc.Format == DXGI_FORMAT_R10G10B10A2_UNORM)
            { red = (pixel & 1023) >> 5; green = ((pixel >> 10) & 1023) >> 4; blue = ((pixel >> 20) & 1023) >> 5; }
            else
            {
                red = (pixel & 255) >> 3; green = ((pixel >> 8) & 255) >> 2; blue = ((pixel >> 16) & 255) >> 3;
                if (desc.Format == DXGI_FORMAT_B8G8R8A8_UNORM) std::swap(red, blue);
            }
            const u16 rgb = u16((red << 11) | (green << 5) | blue);
            pixels[(y * width + x) * 2] = u8(rgb); pixels[(y * width + x) * 2 + 1] = u8(rgb >> 8);
        }
    }
    HW.pContext->Unmap(staging, 0); staging->Release(); return true;
}

bool CRender::UploadPdaPixels(LPCSTR name, u32 width, u32 height, const u8* pixels)
{
    if (!name || !pixels || !width || !height || width > 256 || height > 192) return false;
    xr_vector<u32> rgba(width * height);
    for (u32 i = 0; i < rgba.size(); ++i)
    {
        const u16 rgb = u16(pixels[i * 2] | (u16(pixels[i * 2 + 1]) << 8));
        const u32 red = ((rgb >> 11) & 31) * 255 / 31, green = ((rgb >> 5) & 63) * 255 / 63, blue = (rgb & 31) * 255 / 31;
        rgba[i] = red | (green << 8) | (blue << 16) | 0xff000000;
    }
    D3D11_TEXTURE2D_DESC desc = {};
    desc.Width = width; desc.Height = height; desc.MipLevels = desc.ArraySize = desc.SampleDesc.Count = 1;
    desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM; desc.Usage = D3D11_USAGE_DEFAULT; desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    D3D11_SUBRESOURCE_DATA data = {rgba.data(), width * 4, 0};
    ID3D11Texture2D* surface = nullptr;
    if (FAILED(HW.pDevice->CreateTexture2D(&desc, &data, &surface))) return false;
    ref_texture& texture = netcoop_pda_textures[shared_str(name)];
    if (!texture) texture.create(name);
    texture->surface_set(surface); surface->Release(); texture->flags.bLoaded = true; texture->PostLoad();
    return true;
}

void CRender::ForgetPdaTexture(LPCSTR name)
{
    netcoop_pda_textures.erase(shared_str(name));
}
