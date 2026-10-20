// Included in netcoop.cpp (namespace netcoop) - client: the task list from the server.
// Split out of netcoop.cpp in the same order (doc 151); see the file list there.

// ---------------------------------------------------------------------------
// client: task list from the server
// ---------------------------------------------------------------------------
static void notify_task(LPCSTR id, LPCSTR kind)
{
	::luabind::functor<void> f;
	if (!ai().script_engine().functor("netcoop_client_compat.on_task", f))
		return;
	try
	{
		f(id, kind);
	}
	catch (...)
	{
	}
}

void client_on_tasks(NET_Packet& P)
{
	if (!pure_client() || !Level().GameTaskManagerPtr())
		return;
	CGameTaskManager& manager = Level().GameTaskManager();

	xr_map<shared_str, ETaskState> previous;
	{
		vGameTasks& tasks = manager.GetGameTasks();
		for (u32 i = 0; i < tasks.size(); ++i)
			if (tasks[i].game_task)
				previous[tasks[i].task_id] = tasks[i].game_task->GetTaskState();
	}
	clear_tasks(&manager);

	if (P.r_elapsed() < sizeof(u16))
		return;
	const u16 count = P.r_u16();
	xr_vector<std::pair<shared_str, LPCSTR>> news;
	for (u16 i = 0; i < count; ++i)
	{
		string256 id;
		if (!read_string(P, id, sizeof(id)) || P.r_elapsed() < sizeof(u16))
			break;
		const u16 size = P.r_u16();
		if (P.r_elapsed() < size)
			break;
		IReader reader(P.B.data + P.r_tell(), size);
		P.r_advance(size);

		CGameTask* t = xr_new<CGameTask>();
		t->m_ID = id;
		t->load_task_remote(reader);
		vGameTasks& tasks = manager.GetGameTasks();
		tasks.push_back(SGameTaskKey(t->m_ID));
		tasks.back().game_task = t;

		xr_map<shared_str, ETaskState>::iterator old = previous.find(t->m_ID);
		const ETaskState state = t->GetTaskState();
		const bool was_active = old != previous.end() && old->second == eTaskStateInProgress;
		if (state == eTaskStateInProgress && !was_active)
			news.push_back(std::make_pair(t->m_ID, "new"));
		else if (was_active && state == eTaskStateCompleted)
			news.push_back(std::make_pair(t->m_ID, "complete"));
		else if (was_active && state == eTaskStateFail)
			news.push_back(std::make_pair(t->m_ID, "fail"));
	}

	if (!manager.ActiveTask())
	{
		CGameTask* first = manager.IterateGet(NULL, eTaskStateInProgress, true);
		if (first)
			manager.SetActiveTask(first);
	}
	manager.MarkChanged();
	if (CurrentGameUI())
		CurrentGameUI()->UpdatePda();

	for (u32 i = 0; i < news.size(); ++i)
		notify_task(news[i].first.c_str(), news[i].second);
}
