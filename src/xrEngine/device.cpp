#include "stdafx.h"
#include "../xrCDB/frustum.h"
#include "xr_ioconsole.h"
#include "xr_input.h"
#include "../xrCore/profiler.h"

#pragma warning(disable:4995)
// mmsystem.h
#define MMNOSOUND
#define MMNOMIDI
#define MMNOAUX
#define MMNOMIXER
#define MMNOJOY
#include <mmsystem.h>
// d3dx9.h
#include <d3dx9.h>
#pragma warning(default:4995)

#include "x_ray.h"
#include "discord\discord.h"
#include "render.h"
#include <chrono>

// must be defined before include of FS_impl.h
#define INCLUDE_FROM_ENGINE
#include "../xrCore/FS_impl.h"

#ifdef INGAME_EDITOR
# include "../include/editor/ide.hpp"
# include "engine_impl.hpp"
#endif // #ifdef INGAME_EDITOR

#include "xrSash.h"
#include "igame_persistent.h"
#include "shader_bus.h"

#pragma comment( lib, "d3dx9.lib" )

ENGINE_API CRenderDevice Device;
ENGINE_API CLoadScreenRenderer load_screen_renderer;


ENGINE_API BOOL g_bRendering = FALSE;

BOOL g_bLoaded = FALSE;
ref_light precache_light = 0;

BOOL psLua_ParallelGC = TRUE;
BOOL psLua_ParallelGC_debug = FALSE;
int psLua_ParallelGC_CallAmount = 25;

extern discord::Core* discord_core;
extern bool use_discord;

extern Fvector4 ps_ssfx_grass_interactive;

#ifdef ECO_RENDER
std::chrono::high_resolution_clock::time_point tlastf = std::chrono::high_resolution_clock::now(), tcurrentf = std::
	                                               chrono::high_resolution_clock::now();
std::chrono::duration<float> time_span;
ENGINE_API float refresh_rate = 0;
#endif // ECO_RENDER

BOOL CRenderDevice::Begin()
{
	PROF_EVENT();

#ifndef DEDICATED_SERVER
	switch (m_pRender->GetDeviceState())
	{
	case IRenderDeviceRender::dsOK:
		break;

	case IRenderDeviceRender::dsLost:
		// If the device was lost, do not render until we get it back
		Sleep(33);
		return FALSE;
		break;

	case IRenderDeviceRender::dsNeedReset:
		// Check if the device is ready to be reset
		Reset();
		break;

	default:
		R_ASSERT(0);
	}

	m_pRender->Begin();

	FPU::m24r();
	g_bRendering = TRUE;
#endif
	return TRUE;
}

void CRenderDevice::Clear()
{
	m_pRender->Clear();
}

extern void CheckPrivilegySlowdown();


void CRenderDevice::End(void)
{
	PROF_EVENT();

#ifndef DEDICATED_SERVER


#ifdef INGAME_EDITOR
    bool load_finished = false;
#endif // #ifdef INGAME_EDITOR
	if (dwPrecacheFrame)
	{
		::Sound->set_master_volume(0.f);
		dwPrecacheFrame--;

		if (!dwPrecacheFrame)
		{
#ifdef INGAME_EDITOR
            load_finished = true;
#endif // #ifdef INGAME_EDITOR

			m_pRender->updateGamma();

			if (precache_light)
			{
				precache_light->set_active(false);
				precache_light.destroy();
			}
			::Sound->set_master_volume(1.f);

			m_pRender->ResourcesDestroyNecessaryTextures();

			Msg("* [x-ray]: Handled Necessary Textures Destruction");
			Memory.mem_compact();
			Msg("* MEMORY USAGE: %lld K", Memory.mem_usage() / 1024);
			Msg("* End of synchronization A[%d] R[%d]", b_is_Active, b_is_Ready);

#ifdef FIND_CHUNK_BENCHMARK_ENABLE
            g_find_chunk_counter.flush();
#endif // FIND_CHUNK_BENCHMARK_ENABLE

			CheckPrivilegySlowdown();

			if (g_pGamePersistent->GameType() == 1) //haCk
			{
				WINDOWINFO wi;
				GetWindowInfo(m_hWnd, &wi);
				if (wi.dwWindowStatus != WS_ACTIVECAPTION)
					Pause(TRUE, TRUE, TRUE, "application start");
			}
		}
	}

	g_bRendering = FALSE;
	// end scene
	// Present goes here, so call OA Frame end.
	if (g_SASH.IsBenchmarkRunning())
		g_SASH.DisplayFrame(Device.fTimeGlobal);
	m_pRender->End();

# ifdef INGAME_EDITOR
    if (load_finished && m_editor)
        m_editor->on_load_finished();
# endif // #ifdef INGAME_EDITOR
#endif
}


volatile u32 mt_Thread_marker = 0x12345678;

// The secondary thread (ALife update, path builders, bullets, script GC):
// the Lost Zone hitch sampler logs its stack too when the main thread waits.
ENGINE_API HANDLE g_mt_thread_handle = 0;

void mt_Thread(void* ptr)
{
	auto& device = *static_cast<CRenderDevice*>(ptr);
	DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &g_mt_thread_handle,
		THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, 0);
	while (true)
	{
		PROF_EVENT();

		START_PROFILE("Wait for device");
		// waiting for Device permission to execute
		device.mt_csEnter.Enter();

		if (device.mt_bMustExit)
		{
			PROF_EVENT("Must exit");

			device.mt_bMustExit = FALSE; // Important!!!
			device.mt_csEnter.Leave(); // Important!!!
			return;
		}
		// we has granted permission to execute
		mt_Thread_marker = device.dwFrame;
		STOP_PROFILE;

		START_PROFILE("Process seqParallel");
		for (u32 pit = 0; pit < device.seqParallel.size(); pit++)
			device.seqParallel[pit]();
		device.seqParallel.clear_not_free();
		STOP_PROFILE;

		START_PROFILE("Process seqFrameMT");
		device.seqFrameMT.Process(rp_Frame);
		STOP_PROFILE;

		// demonized: While Renderer prepares frame and GPU renders it, use time opportunity to repeatedly call Lua GC with small step value
		// Reduces stutters since less work will be done in main GC step or no work at all
		{
			PROF_EVENT("seqLuaGC");
			if (psLua_ParallelGC && Device.LuaGC)
			{
				// Do at least once
				do
				{
					Device.LuaGCCount++;
					if (Device.LuaGC() == 1) // 1 informs that GC cycle is complete
					{
						Device.LuaGCDone = true;
						break;
					}

				} while (Device.isRendering && Device.LuaGCCount < psLua_ParallelGC_CallAmount);
			}
		}

		START_PROFILE("Synchronization");
		// now we give control to device - signals that we are ended our work
		device.mt_csEnter.Leave();
		// waits for device signal to continue - to start again
		device.mt_csLeave.Enter();
		// returns sync signal to device
		device.mt_csLeave.Leave();
		STOP_PROFILE;
	}
}

#include "igame_level.h"

void CRenderDevice::PreCache(u32 amount, bool b_draw_loadscreen, bool b_wait_user_input)
{
#ifdef DEDICATED_SERVER
    amount = 0;
#else
	if (m_pRender->GetForceGPU_REF())
		amount = 0;
#endif

	dwPrecacheFrame = dwPrecacheTotal = amount;
	if (amount && !precache_light && g_pGameLevel && g_loading_events.empty())
	{
		precache_light = ::Render->light_create();
		precache_light->set_shadow(false);
		precache_light->set_position(vCameraPosition);
		precache_light->set_color(255, 255, 255);
		precache_light->set_range(5.0f);
		precache_light->set_active(true);
	}

	if (amount && b_draw_loadscreen && !load_screen_renderer.b_registered)
	{
		load_screen_renderer.start(b_wait_user_input);
	}
}

int g_svDedicateServerUpdateReate = 100;

ENGINE_API xr_list<LOADING_EVENT> g_loading_events;

extern bool IsMainMenuActive(); //ECO_RENDER add

static HMONITOR g_StartupMonitor = NULL;

#include "MonitorList.h"

static void InitMonitor()
{
	if (g_StartupMonitor)
		return;

	HMONITOR chosen = ResolveSelectedMonitor();
	if (chosen)
	{
		MONITORINFO mi;
		mi.cbSize = sizeof(mi);
		if (GetMonitorInfoA(chosen, &mi))
		{
			g_StartupMonitor = chosen;
			return;
		}
		Msg("! vid_monitor: resolved handle is invalid, using Auto");
	}

	POINT cursorPos;
	GetCursorPos(&cursorPos);
	g_StartupMonitor = MonitorFromPoint(cursorPos, MONITOR_DEFAULTTOPRIMARY);
}

ENGINE_API void ResetStartupMonitor()
{
	g_StartupMonitor = NULL;
}

ENGINE_API void SetStartupMonitor(HMONITOR h)
{
	g_StartupMonitor = h;
}

ENGINE_API HMONITOR GetStartupMonitor()
{
	InitMonitor();
	return g_StartupMonitor;
}

void GetMonitorResolution(u32& horizontal, u32& vertical)
{
	InitMonitor();

	MONITORINFO mi;
	mi.cbSize = sizeof(mi);
	if (GetMonitorInfoA(g_StartupMonitor, &mi))
	{
		horizontal = mi.rcMonitor.right - mi.rcMonitor.left;
		vertical = mi.rcMonitor.bottom - mi.rcMonitor.top;
	}
	else
	{
		RECT desktop;
		const HWND hDesktop = GetDesktopWindow();
		GetWindowRect(hDesktop, &desktop);
		horizontal = desktop.right - desktop.left;
		vertical = desktop.bottom - desktop.top;
	}
}

void GetMonitorPosition(int& x, int& y)
{
	InitMonitor();

	MONITORINFO mi;
	mi.cbSize = sizeof(mi);
	if (GetMonitorInfoA(g_StartupMonitor, &mi))
	{
		x = mi.rcMonitor.left;
		y = mi.rcMonitor.top;
	}
	else
	{
		x = 0;
		y = 0;
	}
}

float GetMonitorRefresh()
{
	DEVMODE lpDevMode;
	memset(&lpDevMode, 0, sizeof(DEVMODE));
	lpDevMode.dmSize = sizeof(DEVMODE);
	lpDevMode.dmDriverExtra = 0;

	if (EnumDisplaySettings(NULL, ENUM_CURRENT_SETTINGS, &lpDevMode) == 0)
	{
		return 1.f / 60.f;
	}
	else
		return 1.f / lpDevMode.dmDisplayFrequency;
}

extern int ps_framelimiter;
extern u32 g_screenmode;

CTimer FreezeTimer;
void mt_FreezeThread(void *ptr) {
	float freezetime = 0.f;
	float repeatcheck = 500.f;

	while (true)
	{
		PROF_EVENT();

		if (g_loading_events.size())
			freezetime = 25000.0f;
		else
			freezetime = 5000.0f;

		repeatcheck = 500.f;

		START_PROFILE("Check timer");
		if (FreezeTimer.GetElapsed_sec()*1000.f > freezetime)
		{
			FlushLog();
			repeatcheck = 5000.f;
		}
		STOP_PROFILE;

		Sleep(repeatcheck);
	}
}

void CRenderDevice::on_idle()
{
	FreezeTimer.Start();

	if (!b_is_Ready)
	{
		Sleep(100);
		return;
	}

	PROF_FRAME("X-RAY Primary thread");
	PROF_EVENT();

#ifdef DEDICATED_SERVER
    u32 FrameStartTime = TimerGlobal.GetElapsed_ms();
#endif

	START_PROFILE("Set stat gathering");
	if (psDeviceFlags.test(rsStatistic))
		g_bEnableStatGather = TRUE;
	else g_bEnableStatGather = FALSE;
	STOP_PROFILE;

	if (g_loading_events.size())
	{
		PROF_EVENT("Pop loading event");
		if (g_loading_events.front()())
			g_loading_events.pop_front();
		pApp->LoadDraw();
		return;
	}

	if (!Device.dwPrecacheFrame && !g_SASH.IsBenchmarkRunning() && g_bLoaded)
	{
		PROF_EVENT("Start xrSASH Benchmark");
		g_SASH.StartBenchmark();
	}

	FrameMove();

	// Precache
	if (dwPrecacheFrame)
	{
		PROF_EVENT("Precache frame");
		float factor = float(dwPrecacheFrame) / float(dwPrecacheTotal);
		float angle = PI_MUL_2 * factor;
		vCameraDirection.set(_sin(angle), 0, _cos(angle));
		vCameraDirection.normalize();
		vCameraTop.set(0, 1, 0);
		vCameraRight.crossproduct(vCameraTop, vCameraDirection);

		mView.build_camera_dir(vCameraPosition, vCameraDirection, vCameraTop);
	}

	// Matrices
	START_PROFILE("Matrices");
	mFullTransform.mul(mProject, mView);
	mFullTransformHud.mul(mProjectHud, mView);
	m_pRender->SetCacheXform(mView, mProject);

	// Previous frame data -- 
	mView_prev = mView_saved;
	mProject_prev = mProject_saved;
	//mFullTransform_prev = mFullTransform_saved; // Unused?

	m_pRender->SetCacheXform_prev(mView_prev, mProject_prev);

	// Save previous frame grass benders data
	IGame_Persistent::grass_data& GData = g_pGamePersistent->grass_shader_data;

	GData.prev_pos[0].set(Device.vCameraPosition.x, Device.vCameraPosition.y, Device.vCameraPosition.z, -1);
	GData.prev_dir[0].set(0.0f, -99.0f, 0.0f, 1.0f);

	for (int pBend = 1; pBend < _min(16, ps_ssfx_grass_interactive.y + 1); pBend++)
	{
		GData.prev_pos[pBend].set(GData.pos[pBend].x, GData.pos[pBend].y, GData.pos[pBend].z, GData.radius_curr[pBend]);
		GData.prev_dir[pBend].set(GData.dir[pBend].x, GData.dir[pBend].y, GData.dir[pBend].z, GData.str[pBend]);
	}

	// Save wind animation position
	wind_anim_prev = wind_anim_saved;
	wind_anim_saved = g_pGamePersistent->Environment().wind_anim;

	//RCache.set_xform_view ( mView );
	//RCache.set_xform_project ( mProject );
	D3DXMatrixInverse((D3DXMATRIX*)&mInvFullTransform, 0, (D3DXMATRIX*)&mFullTransform);

	vCameraPosition_saved = vCameraPosition;
	mFullTransform_saved = mFullTransform;
	mView_saved = mView;
	mProject_saved = mProject;
	STOP_PROFILE;

	Device.isRendering = true;
	Device.LuaGCCount = 0;
	Device.LuaGCDone = false;

	// *** Resume threads
	// Capture end point - thread must run only ONE cycle
	// Release start point - allow thread to run
	START_PROFILE("Resume threads");
	mt_csLeave.Enter();
	mt_csEnter.Leave();
	STOP_PROFILE;

#ifdef ECO_RENDER // ECO_RENDER START
	if (Device.Paused() || IsMainMenuActive() || ps_framelimiter)
	{
		PROF_EVENT("Eco Render");

		if (refresh_rate == 0)
			refresh_rate = GetMonitorRefresh();

		float rr;

		if (ps_framelimiter)
			rr = 1.f / ps_framelimiter;
		else
			rr = refresh_rate;

		time_span = std::chrono::duration_cast<std::chrono::duration<float>>(tcurrentf - tlastf);
		while (time_span.count() < rr)
		{
			tcurrentf = std::chrono::high_resolution_clock::now();
			time_span = std::chrono::duration_cast<std::chrono::duration<float>>(tcurrentf - tlastf);
		}
		tlastf = std::chrono::high_resolution_clock::now();
	}
#endif // ECO_RENDER END

#ifndef DEDICATED_SERVER
	Statistic->RenderTOTAL_Real.FrameStart();
	Statistic->RenderTOTAL_Real.Begin();

	// The dedicated server's window is a GDI text console (CTextConsole):
	// rendering the level through D3D whenever that window was active only
	// cost frame time (driver calls in 0.6 s server hitches, 2026-10-06).
	if (b_is_Active && !g_dedicated_server && Begin())
	{
		START_PROFILE("Process seqRender");
		seqRender.Process(rp_Render);
		STOP_PROFILE;

		if (psDeviceFlags.test(rsCameraPos) || psDeviceFlags.test(rsStatistic) || Statistic->errors.size())
		{
			PROF_EVENT("Draw statistics");
			Statistic->Show();
		}

		End();
	}
	Statistic->RenderTOTAL_Real.End();
	Statistic->RenderTOTAL_Real.FrameEnd();
	Statistic->RenderTOTAL.accum = Statistic->RenderTOTAL_Real.accum;
#endif // #ifndef DEDICATED_SERVER

	// The dedicated server's frame pause was in IGame_Level::OnRender, which
	// it no longer runs (no D3D level render, 2026-10-06): an empty location
	// server spun a whole core with 1 ms frames (2026-10-07). A frame shorter
	// than -netcoop_frame_ms (5 ms: the old pause, so snapshot timing stays as
	// it was) sleeps the rest; a longer one does not sleep at all (it used to
	// sleep 5 ms every frame).
	if (g_dedicated_server)
	{
		static int frame_ms = -1;
		if (frame_ms < 0)
		{
			LPCSTR option = strstr(Core.Params, "-netcoop_frame_ms=");
			frame_ms = option ? atoi(option + xr_strlen("-netcoop_frame_ms=")) : 5;
			if (frame_ms < 0 || frame_ms > 100) frame_ms = 5;
		}
		static u64 frame_begin = 0;
		const u64 now = CPU::QPC();
		if (frame_begin && frame_ms > 0)
		{
			const u64 spent = (now - frame_begin) * 1000 / CPU::qpc_freq;
			if (spent < u64(frame_ms))
				Sleep(DWORD(u64(frame_ms) - spent));
		}
		frame_begin = CPU::QPC();
	}
	Device.isRendering = false;

	// *** Suspend threads
	// Capture startup point
	// Release end point - allow thread to wait for startup point
	START_PROFILE("Suspend threads");
	mt_csEnter.Enter();
	mt_csLeave.Leave();
	STOP_PROFILE;

	// Ensure, that second thread gets chance to execute anyway
	if (dwFrame != mt_Thread_marker)
	{
		PROF_EVENT("Execute second thread");
		for (u32 pit = 0; pit < Device.seqParallel.size(); pit++)
			Device.seqParallel[pit]();
		Device.seqParallel.clear_not_free();
		seqFrameMT.Process(rp_Frame);
	}

	if (psLua_ParallelGC_debug && psLua_ParallelGC && Device.LuaGCDebug)
	{
		Device.LuaGCDebug();
	}

#ifdef DEDICATED_SERVER
    u32 FrameEndTime = TimerGlobal.GetElapsed_ms();
    u32 FrameTime = (FrameEndTime - FrameStartTime);
    u32 DSUpdateDelta = 1000 / g_svDedicateServerUpdateReate;
    if (FrameTime < DSUpdateDelta)
        Sleep(DSUpdateDelta - FrameTime);
#endif
	if (!b_is_Active)
		Sleep(1);
}

#ifdef INGAME_EDITOR
void CRenderDevice::message_loop_editor()
{
    m_editor->run();
    m_editor_finalize(m_editor);
    xr_delete(m_engine);
}
#endif // #ifdef INGAME_EDITOR

void CRenderDevice::Screenshot()
{
	PROF_EVENT();
	Render->Screenshot();
}

void CRenderDevice::message_loop()
{
#ifdef INGAME_EDITOR
    if (editor())
    {
        message_loop_editor();
        return;
    }
#endif
	MSG msg;
	PeekMessage(&msg, NULL, 0U, 0U, PM_NOREMOVE);
	while (msg.message != WM_QUIT)
	{
		if (PeekMessage(&msg, NULL, 0U, 0U, PM_REMOVE))
		{
			TranslateMessage(&msg);
			DispatchMessage(&msg);
			continue;
		}
		on_idle();
	}
}

void mt_DiscordThread(void*)
{
	while (true)
	{
		if (!pApp)
		{
			Msg("[Discord] pApp destroyed, killing thread");
			return;
		}

		//Discord
		if (use_discord && psDeviceFlags2.test(rsDiscord))
		{
			START_PROFILE("Discord");
			discord_core->RunCallbacks();
			updateDiscordPresence();
			STOP_PROFILE;
			Sleep(int(discord_update_rate * 1000));
		}
		else
		{
			Sleep(1000); // Sleep for 1 second if Discord is not used or disabled
		}
	}
}

void CRenderDevice::Run()
{
	// DUMP_PHASE;
	g_bLoaded = FALSE;
	Log("Starting engine...");
	thread_name("X-RAY Primary thread");
	// Startup timers and calculate timer delta
	dwTimeGlobal = 0;
	Timer_MM_Delta = 0;
	{
		u32 time_mm = timeGetTime();
		while (timeGetTime() == time_mm); // wait for next tick
		u32 time_system = timeGetTime();
		u32 time_local = TimerAsync();
		Timer_MM_Delta = time_system - time_local;
	}
	// Start all threads
	// InitializeCriticalSection (&mt_csEnter);
	// InitializeCriticalSection (&mt_csLeave);
	mt_csEnter.Enter();
	mt_bMustExit = FALSE;
	thread_spawn(mt_FreezeThread, "Freeze detecting thread", 0, 0);
	thread_spawn(mt_Thread, "X-RAY Secondary thread", 0, this);
	thread_spawn(mt_DiscordThread, "X-RAY Discord thread", 0, 0);
	// Message cycle
	seqAppStart.Process(rp_AppStart);
	m_pRender->ClearTarget();
	SetForegroundWindow(m_hWnd);
    // Startup activation can precede device/input initialization. Synchronize
    // from the real window state; do not wait for another WM_ACTIVATE (Alt+Tab).
    OnWM_Activate(MAKEWPARAM(GetForegroundWindow() == m_hWnd ? WA_ACTIVE : WA_INACTIVE,
        IsIconic(m_hWnd)), 0);
    Msg("[Lost Zone] startup window: visible=%d active=%d", IsWindowVisible(m_hWnd), b_is_Active);
	message_loop();
	seqAppEnd.Process(rp_AppEnd);
	// Stop Balance-Thread
	mt_bMustExit = TRUE;
	mt_csEnter.Leave();
	while (mt_bMustExit) Sleep(0);
	// DeleteCriticalSection (&mt_csEnter);
	// DeleteCriticalSection (&mt_csLeave);
}

u32 app_inactive_time = 0;
u32 app_inactive_time_start = 0;

void CRenderDevice::FrameMove()
{
	PROF_EVENT();

	if (InterlockedExchange(&g_monitor_list_dirty, 0))
		refresh_vid_monitor_list();

	dwFrame++;
	Core.dwFrame = dwFrame;
	dwTimeContinual = TimerMM.GetElapsed_ms() - app_inactive_time;
	if (psDeviceFlags.test(rsConstantFPS))
	{
		PROF_EVENT("Constant FPS");

		// 20ms = 50fps
		//fTimeDelta = 0.020f;
		//fTimeGlobal += 0.020f;
		//dwTimeDelta = 20;
		//dwTimeGlobal += 20;
		// 33ms = 30fps
		fTimeDelta = 0.033f;
		fTimeGlobal += 0.033f;
		dwTimeDelta = 33;
		dwTimeGlobal += 33;
	}
	else
	{
		PROF_EVENT("Timer FPS");

		// Timer
		float fPreviousFrameTime = Timer.GetElapsed_sec();
		Timer.Start(); // previous frame
		fTimeDelta = 0.1f * fTimeDelta + 0.9f * fPreviousFrameTime;
		// smooth random system activity - worst case ~7% error
		//fTimeDelta = 0.7f * fTimeDelta + 0.3f*fPreviousFrameTime; // smooth random system activity
		if (fTimeDelta > .1f)
			fTimeDelta = .1f; // limit to 15fps minimum
		if (fTimeDelta <= 0.f)
			fTimeDelta = EPS_S + EPS_S; // limit to 15fps minimum
		if (Paused())
			fTimeDelta = 0.0f;
		// u64 qTime = TimerGlobal.GetElapsed_clk();
		fTimeGlobal = TimerGlobal.GetElapsed_sec(); //float(qTime)*CPU::cycles2seconds;
		u32 _old_global = dwTimeGlobal;
		dwTimeGlobal = TimerGlobal.GetElapsed_ms();
		dwTimeDelta = dwTimeGlobal - _old_global;
	}
	// Frame move
	Statistic->EngineTOTAL.Begin();

	ShaderBus::frame_latch();

	// TODO: HACK to test loading screen.
	//if(!g_bLoaded)
	START_PROFILE("Process seqFrame");
	Device.seqFrame.Process(rp_Frame);
	STOP_PROFILE;
	g_bLoaded = TRUE;
	//else
	// seqFrame.Process(rp_Frame);
	Statistic->EngineTOTAL.End();
}

ENGINE_API BOOL bShowPauseString = TRUE;
#include "IGame_Persistent.h"

void CRenderDevice::Pause(BOOL bOn, BOOL bTimer, BOOL bSound, LPCSTR reason)
{
	PROF_EVENT();

	static int snd_emitters_ = -1;

	if (g_bBenchmark)
		return;
#ifndef DEDICATED_SERVER
	if (bOn)
	{
		if (!Paused())
			bShowPauseString =
#ifdef INGAME_EDITOR
                editor() ? FALSE :
#endif // #ifdef INGAME_EDITOR
#ifdef DEBUG
                !xr_strcmp(reason, "li_pause_key_no_clip") ? FALSE :
#endif // DEBUG
				TRUE;

		if (bTimer && (!g_pGamePersistent || g_pGamePersistent->CanBePaused()))
		{
			g_pauseMngr().Pause(true);
#ifdef DEBUG
            if (!xr_strcmp(reason, "li_pause_key_no_clip"))
                TimerGlobal.Pause(FALSE);
#endif // DEBUG
		}

		if (bSound && ::Sound)
		{
			snd_emitters_ = ::Sound->pause_emitters(true);
#ifdef DEBUG
			// Log("snd_emitters_[true]",snd_emitters_);
#endif // DEBUG
		}
	}
	else
	{
		if (bTimer && g_pauseMngr().Paused())
		{
			fTimeDelta = EPS_S + EPS_S;
			g_pauseMngr().Pause(false);
		}

		if (bSound)
		{
			if (snd_emitters_ > 0) //avoid crash
			{
				snd_emitters_ = ::Sound->pause_emitters(false);
#ifdef DEBUG
				// Log("snd_emitters_[false]",snd_emitters_);
#endif
			}
			else
			{
#ifdef DEBUG
                Log("Sound->pause_emitters underflow");
#endif
			}
		}
	}

#endif
}

bool CRenderDevice::Paused()
{
	return g_pauseMngr().Paused();
}

void CRenderDevice::OnWM_Activate(WPARAM wParam, LPARAM lParam)
{
	u16 fActive = LOWORD(wParam);
	BOOL fMinimized = (BOOL)HIWORD(wParam);
	BOOL bActive = ((fActive != WA_INACTIVE) && (!fMinimized)) ? TRUE : FALSE;

	// The dedicated window is a text console. Never apply the game cursor
	// capture or hide rules to it, even in the regular (non-DEDICATED_SERVER)
	// build used by the separate server executable.
	if (g_dedicated_server)
	{
		if (bActive != Device.b_is_Active)
		{
			Device.b_is_Active = bActive;
			if (bActive)
			{
				Device.seqAppActivate.Process(rp_AppActivate);
				app_inactive_time += TimerMM.GetElapsed_ms() - app_inactive_time_start;
			}
			else
			{
				app_inactive_time_start = TimerMM.GetElapsed_ms();
				Device.seqAppDeactivate.Process(rp_AppDeactivate);
			}
		}
		ClipCursor(nullptr);
		ShowCursor(TRUE);
		return;
	}

	if (psDeviceFlags2.test(rsAlwaysActive) && g_screenmode != 2)
	{
		Device.b_is_Active = TRUE;

		if (Device.b_hide_cursor != bActive)
		{
			Device.b_hide_cursor = bActive;

			if (Device.b_hide_cursor)
			{
				ShowCursor(FALSE);
				if (m_hWnd)
				{
					RECT winRect;
					GetClientRect(m_hWnd, &winRect);
					MapWindowPoints(m_hWnd, nullptr, reinterpret_cast<LPPOINT>(&winRect), 2);
					ClipCursor(&winRect);
				}
				pInput->OnAppActivate();
			}
			else
			{
				ShowCursor(TRUE);
				ClipCursor(NULL);
				pInput->OnAppDeactivate();
			}
		}

		return;
	}

	if (bActive != Device.b_is_Active)
	{
		Device.b_is_Active = bActive;

		if (Device.b_is_Active)
		{
			Device.seqAppActivate.Process(rp_AppActivate);
			app_inactive_time += TimerMM.GetElapsed_ms() - app_inactive_time_start;

#ifndef DEDICATED_SERVER
# ifdef INGAME_EDITOR
            if (!editor())
# endif // #ifdef INGAME_EDITOR
			ShowCursor(FALSE);
			if (m_hWnd)
			{
				RECT winRect;
				GetClientRect(m_hWnd, &winRect);
				MapWindowPoints(m_hWnd, nullptr, reinterpret_cast<LPPOINT>(&winRect), 2);
				ClipCursor(&winRect);
			}
#endif // #ifndef DEDICATED_SERVER
		}
		else
		{
			app_inactive_time_start = TimerMM.GetElapsed_ms();
			Device.seqAppDeactivate.Process(rp_AppDeactivate);
			ShowCursor(TRUE);
			ClipCursor(NULL);
		}
	}
}

void CRenderDevice::AddSeqFrame(pureFrame* f, bool mt)
{
	PROF_EVENT();

	if (mt)
		seqFrameMT.Add(f, REG_PRIORITY_HIGH);
	else
		seqFrame.Add(f, REG_PRIORITY_LOW);
}

void CRenderDevice::RemoveSeqFrame(pureFrame* f)
{
	PROF_EVENT();

	seqFrameMT.Remove(f);
	seqFrame.Remove(f);
}

CLoadScreenRenderer::CLoadScreenRenderer()
	: b_registered(false)
{
}

void CLoadScreenRenderer::start(bool b_user_input)
{
	PROF_EVENT();

	Device.seqRender.Add(this, 0);
	b_registered = true;
	b_need_user_input = b_user_input;
}

void CLoadScreenRenderer::stop()
{
	PROF_EVENT();

	if (!b_registered)
		return;
	Device.seqRender.Remove(this);
	pApp->destroy_loading_shaders();
	b_registered = false;
	b_need_user_input = false;
}

void CLoadScreenRenderer::OnRender()
{
	PROF_EVENT();

	pApp->load_draw_internal();
}

void CRenderDevice::CSecondVPParams::SetSVPActive(bool bState) //--#SM+#-- +SecondVP+
{
	isActive = bState;
	if (g_pGamePersistent != NULL)
		g_pGamePersistent->m_pGShaderConstants->m_blender_mode.z = (isActive ? 1.0f : 0.0f);
}

bool CRenderDevice::CSecondVPParams::IsSVPFrame() //--#SM+#-- +SecondVP+
{
	return IsSVPActive() && Device.dwFrame % frameDelay == 0;
}


#include "netcoop_menu_camera.h"
namespace menu_room
{
static Fvector camera = Fvector().set(0,1.35f,-4.6f);
static Fvector target = Fvector().set(0,1.25f,.5f);
static Fvector from_camera, from_target;
static int destination = -1;
static u32 start = 0;
static bool moving = false;
static bool room_presented = false;
static u32 room_draw_frame = u32(-1);
static Fvector eyes[] = {Fvector().set(0,1.35f,-4.6f),Fvector().set(-1.5f,1.6f,.9f),
    Fvector().set(1.4f,1.7f,.1f),Fvector().set(-1.6f,1.f,-.85f),Fvector().set(-.75f,1.1f,-.1f),Fvector().set(-.75f,1.45f,.1f)};
static Fvector targets[] = {Fvector().set(0,1.25f,.5f),Fvector().set(-1.5f,1.65f,2.14f),
    Fvector().set(1.5f,.95f,1.1f),Fvector().set(-1.65f,.36f,.3f),Fvector().set(-1.55f,.65f,1.15f),Fvector().set(-1.9f,1.f,-1.2f)};
static Fvector lamp = Fvector().set(-1.4f,2.7f,-1.6f);
static Fvector seat=Fvector().set(.45f,.61f,2.37f);
static float seat_yaw=PI;
static Fbox pick_boxes[5];
static bool pick_valid[5]={false,false,false,false,false};
static int hover_target=-1, hover_shown=-1;
static float hover_strength=0.f;
static u32 hover_time=0;
// Cursor picking boxes written by scripts/build-lostzone-room.py.
static void load_picks()
{
    IReader* file=FS.r_open("$game_meshes$","netcoop\\personal_room.pick");
    if(!file) { Msg("~ [Lost Zone] room has no pick boxes; objects are not clickable"); return; }
    bool valid=file->length()==12+5*6*sizeof(float) && file->r_u32()==0x5052434e && file->r_u32()==1 && file->r_u32()==5;
    float values[30];
    if(valid) file->r(values,sizeof(values));
    FS.r_close(file);
    for(int i=0;valid && i<30;++i) valid=_valid(values[i]) && _abs(values[i])<=1000.f;
    if(!valid) { Msg("! [Lost Zone] invalid room pick boxes; objects are not clickable"); return; }
    for(int i=0;i<5;++i)
    {
        pick_boxes[i].set(values[i*6],values[i*6+1],values[i*6+2],values[i*6+3],values[i*6+4],values[i*6+5]);
        pick_valid[i]=pick_boxes[i].min.x<=pick_boxes[i].max.x && pick_boxes[i].min.y<=pick_boxes[i].max.y && pick_boxes[i].min.z<=pick_boxes[i].max.z;
    }
}
static void load_config()
{
    static bool loaded=false;
    if(loaded) return;
    loaded=true;
    IReader* file=FS.r_open("$game_meshes$","netcoop\\personal_room.camera");
    if(!file) return;
    const u32 bytes=file->length();
    // v1: 4 views + lamp; v2: 6 views + lamp + seat; v3: v2 + seat heading.
    bool valid=bytes==8+27*sizeof(float) || bytes==8+42*sizeof(float) || bytes==8+43*sizeof(float);
    u32 version=0;
    if(valid) { valid=file->r_u32()==0x4352434e; version=file->r_u32(); }
    valid=valid && ((version==1 && bytes==8+27*sizeof(float)) || (version==2 && bytes==8+42*sizeof(float)) ||
        (version==3 && bytes==8+43*sizeof(float)));
    const int cameras=version>=2 ? 6 : 4;
    Fvector values[14];
    float heading=PI;
    if(valid)
    {
        file->r(values,(cameras*2+(version>=2 ? 2 : 1))*sizeof(Fvector));
        if(version==3) heading=file->r_float();
        for(int i=0;i<cameras*2+(version>=2 ? 2 : 1);++i)
            valid=valid && _valid(values[i]) && _abs(values[i].x)<=1000.f && _abs(values[i].y)<=1000.f && _abs(values[i].z)<=1000.f;
        for(int i=0;i<cameras;++i) valid=valid && values[i*2].distance_to_sqr(values[i*2+1])>=.01f;
        valid=valid && _valid(heading) && _abs(heading)<=10.f;
    }
    FS.r_close(file);
    load_picks();
    if(!valid) { Msg("! [Lost Zone] invalid room editor cameras; using defaults"); return; }
    for(int i=0;i<cameras;++i) { eyes[i]=values[i*2]; targets[i]=values[i*2+1]; }
    lamp=values[cameras*2]; if(version>=2) seat=values[13]; seat_yaw=heading; camera=eyes[0]; target=targets[0];
    Msg("[Lost Zone] room editor cameras and lamp loaded");
}
static void update()
{
    load_config();
    if (!moving) return;
    const float t = _min(1.f, float(Device.dwTimeContinual-start)/850.f);
    const float blend = t*t*(3.f-2.f*t);
    const Fvector to_camera = eyes[destination+1];
    const Fvector to_target = targets[destination+1];
    camera.lerp(from_camera,to_camera,blend); target.lerp(from_target,to_target,blend);
    if (t >= 1.f) moving = false;
}
void focus(int object)
{
    if (object < -1 || object > 4 || object == destination) return;
    update(); from_camera=camera; from_target=target;
    destination=object; start=Device.dwTimeContinual; moving=true;
}
void reset()
{
    load_config(); destination=-1; moving=false; camera=eyes[0]; target=targets[0];
    room_presented=false; room_draw_frame=u32(-1);
}
bool ready() { update(); return !moving; }
bool visible() { return room_presented && Device.b_is_Active; }
void drawn() { room_draw_frame=Device.dwFrame; }
void presented()
{
    if (!room_presented && room_draw_frame==Device.dwFrame)
    {
        room_presented=true;
        Msg("[Lost Zone] first 3D menu frame presented");
    }
}
void matrices(Fmatrix& view,Fmatrix& projection)
{
    update();
    Fvector direction; direction.sub(target,camera).normalize_safe();
    const Fvector up=_abs(direction.y)>.99f ? Fvector().set(0,0,1) : Fvector().set(0,1,0);
    view.build_camera(camera,target,up);
    projection.build_projection(deg2rad(52.f),float(Device.dwHeight)/float(Device.dwWidth),.08f,100.f);
}
Fvector interaction(int object)
{
    load_config(); return targets[_max(0,_min(4,object))+1];
}
Fvector lamp_position() { load_config(); return lamp; }
Fvector seat_position() { load_config(); return seat; }
float seat_heading() { load_config(); return seat_yaw; }
int pick(float x, float y)
{
    load_config();
    Fmatrix view, projection;
    matrices(view,projection);
    if(_abs(projection._11)<EPS_S || _abs(projection._22)<EPS_S) return -1;
    // UI space spans the whole screen; NDC -> view ray -> world ray.
    const float nx=x/512.f-1.f, ny=1.f-y/384.f;
    Fvector local=Fvector().set(nx/projection._11,ny/projection._22,1.f);
    Fmatrix inverse; inverse.invert(view);
    Fvector origin=inverse.c, direction;
    inverse.transform_dir(direction,local); direction.normalize_safe();
    int best=-1; float nearest=flt_max;
    for(int i=0;i<5;++i)
    {
        if(!pick_valid[i]) continue;
        float t0=0.f, t1=flt_max; bool hit=true;
        for(int axis=0;axis<3 && hit;++axis)
        {
            const float o=origin[axis], d=direction[axis];
            const float lo=pick_boxes[i].min[axis], hi=pick_boxes[i].max[axis];
            if(_abs(d)<1e-6f) { if(o<lo || o>hi) hit=false; continue; }
            float a=(lo-o)/d, b=(hi-o)/d;
            if(a>b) { const float swap=a; a=b; b=swap; }
            t0=_max(t0,a); t1=_min(t1,b);
            if(t0>t1) hit=false;
        }
        if(hit && t0<nearest) { nearest=t0; best=i; }
    }
    return best;
}
void hover(int object)
{
    hover_target=object>=0 && object<5 ? object : -1;
}
Fvector2 hover_state()
{
    const u32 now=Device.dwTimeContinual;
    const float dt=hover_time ? _min(.1f,float(now-hover_time)/1000.f) : 0.f;
    hover_time=now;
    if(hover_target>=0 && hover_target!=hover_shown) { hover_shown=hover_target; hover_strength=0.f; }
    hover_strength=hover_target>=0 ? _min(1.f,hover_strength+dt*8.f) : _max(0.f,hover_strength-dt*8.f);
    if(hover_strength<=0.f && hover_target<0) hover_shown=-1;
    return Fvector2().set(float(hover_shown+1),hover_strength);
}
}
