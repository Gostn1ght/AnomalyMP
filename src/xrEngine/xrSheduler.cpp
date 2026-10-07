#include "stdafx.h"
#include "xrSheduler.h"
#include "xr_object.h"
#include "xrSchedulerRegistration.h"

// IX-Ray scheduler adaptation: pinned sources/license in docs/audit/50_IXRAY_SCHEDULER_ADAPTATION.md.
// Keep the legacy cadence/budget; callbacks remain on the existing game thread.

//#define DEBUG_SCHEDULER

float psShedulerCurrent = 10.f;
float psShedulerTarget = 10.f;
const float psShedulerReaction = 0.1f;
BOOL g_bSheduleInProgress = FALSE;

//-------------------------------------------------------------------------------------
void CSheduler::Initialize()
{
	m_current_step_obj = NULL;
	m_processing_now = false;
	m_next_generation = 0;
	ActiveItems.clear();
	OrderChanges.clear();
}

void CSheduler::Destroy()
{
	internal_Registration();

	Items.erase(std::remove_if(Items.begin(), Items.end(),
		[this](const Item& item) { return !active(item); }), Items.end());
#ifdef DEBUG
    if (!Items.empty())
    {
        string1024 _objects;
        _objects[0] = 0;

        Msg("! Sheduler work-list is not empty");
        for (u32 it = 0; it < Items.size(); it++)
            Msg("%s", Items[it].Object->shedule_Name().c_str());
    }
#endif // DEBUG
	ItemsRT.clear();
	Items.clear();
	ItemsProcessed.clear();
	Registration.clear();
	ActiveItems.clear();
	OrderChanges.clear();
}

void CSheduler::internal_Registration()
{
    xr_vector<ItemReg> work;
    while (!Registration.empty())
    {
        work.clear();
        work.swap(Registration);
        const auto skipped = xr_scheduler::registration_pairs(work);
        for (size_t i = 0; i < work.size(); ++i)
        {
            if (skipped[i]) continue;
            const ItemReg R = work[i];
            if (R.OP) internal_Register(R.Object, R.RT);
            else internal_Unregister(R.Object, R.RT, false);
        }
        work.clear();
    }
    // Keep the larger registration allocation for the next spawn/load batch.
    if (Registration.capacity() < work.capacity()) Registration.swap(work);
}

bool CSheduler::active(const Item& item) const
{
    const auto found = ActiveItems.find(item.Object);
    return found != ActiveItems.end() && found->second.generation == item.generation;
}

void CSheduler::internal_Register(ISheduled* O, BOOL RT)
{
	VERIFY(!O->shedule.b_locked);
	R_ASSERT(ActiveItems.find(O) == ActiveItems.end());
	R_ASSERT(m_next_generation != u64(-1));
	const u64 generation = ++m_next_generation;
	ActiveItems.emplace(O, ActiveItem{generation, RT});
	if (RT)
	{
		// Fill item structure
		Item TNext;
		TNext.dwTimeForExecute = Device.dwTimeGlobal;
		TNext.dwTimeOfLastExecute = Device.dwTimeGlobal;
		TNext.Object = O;
		TNext.generation = generation;
		TNext.scheduled_name = O->shedule_Name();
		O->shedule.b_RT = TRUE;

		ItemsRT.push_back(TNext);
	}
	else
	{
		// Fill item structure
		Item TNext;
		TNext.dwTimeForExecute = Device.dwTimeGlobal;
		TNext.dwTimeOfLastExecute = Device.dwTimeGlobal;
		TNext.Object = O;
		TNext.generation = generation;
		TNext.scheduled_name = O->shedule_Name();
		O->shedule.b_RT = FALSE;

		// Insert into priority Queue
		Push(TNext);
	}
}

bool CSheduler::internal_Unregister(ISheduled* O, BOOL RT, bool warn_on_not_found)
{
    (void)RT;
    (void)warn_on_not_found;
    const auto found = ActiveItems.find(O);
    if (found == ActiveItems.end()) return false;
    // Do not erase a vector or touch O: this can run from O's destructor,
    // from its callback, or after a different callback destroyed O.
    const bool realtime = found->second.realtime != FALSE;
    ActiveItems.erase(found);
    if (m_current_step_obj == O) m_current_step_obj = NULL;
    if (realtime && !m_processing_now)
        ItemsRT.erase(std::remove_if(ItemsRT.begin(), ItemsRT.end(),
            [this](const Item& item) { return !active(item); }), ItemsRT.end());
    return true;
}

#ifdef DEBUG
bool CSheduler::Registered(ISheduled* object) const
{
    bool registered = ActiveItems.find(object) != ActiveItems.end();
    for (const ItemReg& R : Registration)
        if (R.Object == object) registered = R.OP != FALSE;
    return registered;
}
#endif

void CSheduler::Register(ISheduled* A, BOOL RT)
{
#ifdef DEBUG
	VERIFY(!Registered(A));
#endif
	ItemReg R;
	R.OP = TRUE;
	R.RT = RT;
	R.Object = A;
	R.Object->shedule.b_RT = RT;

#ifdef DEBUG_SCHEDULER
    Msg("SCHEDULER: register [%s][%x]", *A->shedule_Name(), A);
#endif // DEBUG_SCHEDULER

	Registration.push_back(R);
}

void CSheduler::Unregister(ISheduled* A)
{
#ifdef DEBUG
	// IX-Ray tolerates a duplicate unregister in debug, as release already does.
	if (!Registered(A)) return;
#endif
#ifdef DEBUG_SCHEDULER
    Msg("SCHEDULER: unregister [%s][%x]", *A->shedule_Name(), A);
#endif // DEBUG_SCHEDULER

	if (m_processing_now)
	{
		if (internal_Unregister(A, A->shedule.b_RT, false))
			return;
	}

	ItemReg R;
	R.OP = FALSE;
	R.RT = A->shedule.b_RT;
	R.Object = A;

	Registration.push_back(R);
}

void CSheduler::EnsureOrder(ISheduled* Before, ISheduled* After)
{
    VERIFY(Before->shedule.b_RT && After->shedule.b_RT);
    if (m_processing_now)
    {
        const auto found = ActiveItems.find(After);
        if (found != ActiveItems.end()) OrderChanges.push_back(OrderChange{After, found->second.generation});
        return;
    }
    internal_EnsureOrder(After);
}

void CSheduler::internal_EnsureOrder(ISheduled* After)
{
    for (size_t i = 0; i < ItemsRT.size(); ++i)
        if (ItemsRT[i].Object == After && active(ItemsRT[i]))
        {
            const Item item = ItemsRT[i];
            ItemsRT.erase(ItemsRT.begin() + i);
            ItemsRT.push_back(item);
            return;
        }
}

void CSheduler::Push(Item& I)
{
	Items.push_back(I);
	std::push_heap(Items.begin(), Items.end());
}

void CSheduler::Pop()
{
	std::pop_heap(Items.begin(), Items.end());
	Items.pop_back();
}

void CSheduler::ProcessStep()
{
	// Normal priority
	u32 dwTime = Device.dwTimeGlobal;
	CTimer eTimer;
	for (int i = 0; !Items.empty() && Top().dwTimeForExecute < dwTime; ++i)
	{
		u32 delta_ms = dwTime - Top().dwTimeForExecute;

		// Update
		Item T = Top();
#ifdef DEBUG_SCHEDULER
        Msg("SCHEDULER: process step [%s][%x][false]", *T.scheduled_name, T.Object);
#endif // DEBUG_SCHEDULER
		u32 Elapsed = dwTime - T.dwTimeOfLastExecute;
		bool condition;

		condition = !active(T);
		if (!condition)
		{
			condition = !T.Object->shedule_Needed();
			condition = condition || !active(T);
		}
		if (condition)
		{
			// Erase element
			if (active(T)) ActiveItems.erase(T.Object);
#ifdef DEBUG_SCHEDULER
            Msg("SCHEDULER: process unregister [%s][%x][%s]", *T.scheduled_name, T.Object, "false");
#endif // DEBUG_SCHEDULER
			// if (T.Object)
			// Msg ("0x%08x UNREGISTERS because shedule_Needed() returned false",T.Object);
			// else
			// Msg ("UNREGISTERS unknown object");
			Pop();
			continue;
		}

		// Insert into priority Queue
		Pop();

		// Real update call
		// Msg ("------- %d:",Device.dwFrame);
#ifdef DEBUG
        T.Object->dbg_startframe = Device.dwFrame;
        eTimer.Start();
        // LPCSTR _obj_name = T.Object->shedule_Name().c_str();
#endif // DEBUG

		// Calc next update interval
		u32 dwMin = _max(u32(30), T.Object->shedule.t_min);
		u32 dwMax = (1000 + T.Object->shedule.t_max) / 2;
		m_current_step_obj = T.Object;
		float scale = T.Object->shedule_Scale();
		if (!active(T)) { m_current_step_obj = NULL; continue; }
		// Scale may change t_max: use its current value, as the original scheduler did.
		const u32 maximum_interval = T.Object->shedule.t_max;
		u32 dwUpdate = dwMin + iFloor(float(dwMax - dwMin) * scale);
		clamp(dwUpdate, u32(_max(dwMin, u32(20))), dwMax);


		m_current_step_obj = T.Object;
		// try {
		T.Object->shedule_Update(clampr(Elapsed, u32(1), u32(_max(maximum_interval, u32(1000)))));
		if (!m_current_step_obj || !active(T))
		{
#ifdef DEBUG_SCHEDULER
            Msg("SCHEDULER: process unregister (self unregistering) [%s][%x][%s]", *T.scheduled_name, T.Object, "false");
#endif // DEBUG_SCHEDULER
			continue;
		}
		// } catch (...) {
#ifdef DEBUG
		// Msg ("! xrSheduler: object '%s' raised an exception", _obj_name);
		// throw ;
#endif // DEBUG
		// }
		m_current_step_obj = NULL;

#ifdef DEBUG
		// u32 execTime = eTimer.GetElapsed_ms ();
#endif // DEBUG

		// Fill item structure
		Item TNext;
		TNext.dwTimeForExecute = dwTime + dwUpdate;
		TNext.dwTimeOfLastExecute = dwTime;
		TNext.Object = T.Object;
		TNext.generation = T.generation;
		TNext.scheduled_name = T.Object->shedule_Name();
		ItemsProcessed.push_back(TNext);


#ifdef DEBUG
		// u32 execTime = eTimer.GetElapsed_ms ();
        // VERIFY3 (T.Object->dbg_update_shedule == T.Object->dbg_startframe, "Broken sequence of calls to 'shedule_Update'", _obj_name );
        if (delta_ms > 3 * dwUpdate)
        {
            //Msg ("! xrSheduler: failed to shedule object [%s] (%dms)", _obj_name, delta_ms );
        }
        // if (execTime> 15) {
		// Msg ("* xrSheduler: too much time consumed by object [%s] (%dms)", _obj_name, execTime );
		// }
#endif // DEBUG

		//
		if ((i % 3) != (3 - 1))
			continue;

		if (Device.dwPrecacheFrame == 0 && CPU::QPC() > cycles_limit)
		{
			// we have maxed out the load - increase heap
			psShedulerTarget += (psShedulerReaction * 3);
			break;
		}
	}

	// Push "processed" back
	while (ItemsProcessed.size())
	{
		Push(ItemsProcessed.back());
		ItemsProcessed.pop_back();
	}

	// always try to decrease target
	psShedulerTarget -= psShedulerReaction;
}

/*
void CSheduler::Switch ()
{
if (fibered)
{
fibered = FALSE;
SwitchToFiber (fiber_main);
}
}
*/
void CSheduler::Update()
{
	PROF_EVENT("CSheduler: Update");
	R_ASSERT(Device.Statistic);
	// Initialize
	Device.Statistic->Sheduler.Begin();
	cycles_start = CPU::QPC();
	cycles_limit = CPU::qpc_freq * u64(iCeil(psShedulerCurrent)) / 1000LL + cycles_start;
	internal_Registration();
	g_bSheduleInProgress = TRUE;

#ifdef DEBUG_SCHEDULER
    Msg("SCHEDULER: PROCESS STEP %d", Device.dwFrame);
#endif // DEBUG_SCHEDULER
	// Realtime priority
	m_processing_now = true;
	u32 dwTime = Device.dwTimeGlobal;
    for (size_t it = 0; it < ItemsRT.size(); ++it)
    {
        const Item& T = ItemsRT[it]; // vector mutations are deferred during callbacks
        if (!active(T)) continue;
        const bool needed = T.Object->shedule_Needed();
        if (!active(T)) continue;
        const u32 Elapsed = dwTime - T.dwTimeOfLastExecute;
        ItemsRT[it].dwTimeOfLastExecute = dwTime;
        if (!needed) continue;
#ifdef DEBUG
        VERIFY(T.Object->dbg_startframe != Device.dwFrame);
        T.Object->dbg_startframe = Device.dwFrame;
#endif
        m_current_step_obj = T.Object;
        T.Object->shedule_Update(Elapsed); // IX-Ray: profile, not parallelize live callbacks
        m_current_step_obj = NULL;
        // Never dereference T after this callback: self-unregister/delete is legal.
    }
    ItemsRT.erase(std::remove_if(ItemsRT.begin(), ItemsRT.end(),
        [this](const Item& item) { return !active(item); }), ItemsRT.end());

	// Normal (sheduled)
	ProcessStep();
	m_processing_now = false;
#ifdef DEBUG_SCHEDULER
    Msg("SCHEDULER: PROCESS STEP FINISHED %d", Device.dwFrame);
#endif // DEBUG_SCHEDULER
	clamp(psShedulerTarget, 3.f, 66.f);
	psShedulerCurrent = 0.9f * psShedulerCurrent + 0.1f * psShedulerTarget;
	Device.Statistic->fShedulerLoad = psShedulerCurrent;

	// Finalize
	g_bSheduleInProgress = FALSE;
	internal_Registration();
	for (const auto& order : OrderChanges)
	{
		const auto found = ActiveItems.find(order.after);
		if (found != ActiveItems.end() && found->second.generation == order.generation) internal_EnsureOrder(order.after);
	}
	OrderChanges.clear();
	Device.Statistic->Sheduler.End();
}
