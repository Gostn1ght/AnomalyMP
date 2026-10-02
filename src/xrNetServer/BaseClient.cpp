#include "stdafx.h"
#include "BaseClient.h"

// -----------------------------------------------------------------------------

// global

static const int syncSamples = 0;

// The clock worker continues after initial synchronization. Join it before
// the connection or client is destroyed, including failed level startup.
struct ClientSyncTask { BaseClient* client; HANDLE completed; };
static xrCriticalSection s_sync_lock;
static xr_map<BaseClient*, HANDLE> s_sync_tasks;
static void join_client_sync(BaseClient* client)
{
	HANDLE completed = nullptr;
	{
		xrCriticalSection::raii lock(&s_sync_lock);
		auto found = s_sync_tasks.find(client);
		if (found == s_sync_tasks.end()) return;
		completed = found->second; s_sync_tasks.erase(found);
	}
	// Sync_Thread checks net_Disconnected in every wait; its longest sleep
	// is one second, and its transport operations are nonblocking.
	WaitForSingleObject(completed, INFINITE);
	CloseHandle(completed);
}

//------------------------------------------------------------------------------

BaseClient::BaseClient(CTimer * timer) : net_Statistic(timer)
{
	device_timer = timer;

	net_TimeDelta_User = 0;
	net_Time_LastUpdate = 0;
	net_TimeDelta = 0;
	net_TimeDelta_Calculated = 0;
}

// -----------------------------------------------------------------------------

BaseClient::~BaseClient()
{
	net_Disconnected = TRUE;
	join_client_sync(this);
	psNET_direct_connect = FALSE;
}

// -----------------------------------------------------------------------------

#pragma region connect / disconnect

void BaseClient::ParseConnectionOptions(LPCSTR options, ClientConnectionOptions& out)
{
	// SERVER NAME
	if (strchr(options, '/'))
	{
		strncpy_s(out.server_name, options, strchr(options, '/') - options);
	}
	if (strchr(out.server_name, '/'))
	{
		*strchr(out.server_name, '/') = 0;
	}

	// SERVER PASSWORD
	if (strstr(options, "psw="))
	{
		const char* PSW = strstr(options, "psw=") + 4;
		if (strchr(PSW, '/'))
			strncpy_s(out.server_pass, PSW, strchr(PSW, '/') - PSW);
		else
			xr_strcpy(out.server_pass, PSW);
	}

	// USER NAME
	if (strstr(options, "name="))
	{
		const char* NM = strstr(options, "name=") + 5;
		if (strchr(NM, '/'))
			strncpy_s(out.user_name, NM, strchr(NM, '/') - NM);
		else
			xr_strcpy(out.user_name, NM);

		xr_strcpy(Core.UserName, out.user_name);
	}

	// USER PASSWORD
	if (strstr(options, "pass="))
	{
		const char* UP = strstr(options, "pass=") + 5;
		if (strchr(UP, '/'))
			strncpy_s(out.user_pass, UP, strchr(UP, '/') - UP);
		else
			xr_strcpy(out.user_pass, UP);
	}

	// SERVER PORT
	out.sv_port = START_PORT_LAN_SV;
	if (strstr(options, "port="))
	{
		string64	portstr;
		xr_strcpy(portstr, strstr(options, "port=") + 5);
		if (strchr(portstr, '/'))	*strchr(portstr, '/') = 0;
		out.sv_port = atol(portstr);
		clamp(out.sv_port, int(START_PORT), int(END_PORT));
	};

	// CLIENT PORT
	out.bClPortWasSet = FALSE;
	out.cl_port = START_PORT_LAN_CL;
	if (strstr(options, "portcl="))
	{
		string64	portstr;
		xr_strcpy(portstr, strstr(options, "portcl=") + 7);
		if (strchr(portstr, '/'))	*strchr(portstr, '/') = 0;
		out.cl_port = atol(portstr);
		clamp(out.cl_port, int(START_PORT), int(END_PORT));
		out.bClPortWasSet = TRUE;
	};
}

bool BaseClient::Connect(LPCSTR options)
{
	R_ASSERT(options);

	net_Disconnected = FALSE;

	if (!psNET_direct_connect)
	{
		ClientConnectionOptions connectOpt;
		ParseConnectionOptions(options, connectOpt);

		net_Connected = EnmConnectionWait;
		net_Syncronised = FALSE;
		net_Disconnected = FALSE;

		bool success = CreateConnection(connectOpt);
		if (!success)
		{
			return false;
		}

	} //psNET_direct_connect

	// Sync	
	net_TimeDelta = 0;
	return TRUE;
}

void BaseClient::Disconnect()
{
	net_Disconnected = TRUE;
	join_client_sync(this);
	net_Connected = EnmConnectionWait;
	net_Syncronised = FALSE;

	DestroyConnection();
}

#pragma endregion

// -----------------------------------------------------------------------------

#pragma region recieve

void BaseClient::OnMessage(void * data, u32 size)
{
	// One of the messages - decompress it
	net_Queue.Lock();
	NET_Packet* P = net_Queue.Create();

	P->construct(data, size);
	P->timeReceive = timeServer_Async();//TimerAsync				(device_timer);	

	u16 m_type;
	P->r_begin(m_type);
	net_Queue.Unlock();
}

#pragma endregion

// -----------------------------------------------------------------------------

#pragma region send

void BaseClient::_SendTo_LL(const void* data, u32 size, u32 flags, u32 timeout)
{
	if (net_Disconnected)
		return;

	SendTo_LL(const_cast<void*>(data), size, flags, timeout);
}


void	BaseClient::Send(NET_Packet& packet, u32 dwFlags, u32 dwTimeout)
{
	MultipacketSender::SendPacket(packet.B.data, packet.B.count, dwFlags, dwTimeout);
}

void	BaseClient::Flush_Send_Buffer()
{
	MultipacketSender::FlushSendBuffer(0);
}

#pragma endregion

// -----------------------------------------------------------------------------

#pragma region time correct

/* unused */
/*
void	BaseClient::timeServer_Correct(u32 sv_time, u32 cl_time)
{
	u32		ping = net_Statistic.getPing();
	u32		delta = sv_time + ping / 2 - cl_time;
	net_DeltaArray.push(delta);
	Sync_Average();
}
*/

void client_sync_thread(void* P)
{
	SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);
	ClientSyncTask* task = static_cast<ClientSyncTask*>(P);
	task->client->Sync_Thread();
	SetEvent(task->completed);
	xr_delete(task);
}

void BaseClient::net_Syncronize()
{
	xrCriticalSection::raii lock(&s_sync_lock);
	if (s_sync_tasks.find(this) != s_sync_tasks.end()) return;
	HANDLE completed = CreateEvent(nullptr, TRUE, FALSE, nullptr);
	if (!completed) { net_Disconnected = TRUE; return; }
	auto task = xr_new<ClientSyncTask>(); task->client = this; task->completed = completed;
	s_sync_tasks[this] = completed;
	net_Syncronised = FALSE;
	net_DeltaArray.clear();
	thread_spawn(client_sync_thread, "network-time-sync", 0, task);
}

bool BaseClient::Sync_Thread()
{
	MSYS_PING			clPing;

	//***** Ping server
	net_DeltaArray.clear();
	if (!IsConnectionInit() || net_Disconnected) return false;

	for (; IsConnectionInit() && !net_Disconnected; )
	{
		// Waiting for queue empty state. Once synchronised, keep measuring
		// once a second: the first samples are taken while the level loads,
		// and a clock estimate that is never corrected leaves every client
		// showing the world at a different moment.
		if (net_Syncronised)	Sleep(1000);
		else {
			DWORD			dwPending = 0;
			do {
				GetPendingMessagesCount(dwPending);
				Sleep(1);
			} while (dwPending && !net_Disconnected);
		}

		// Construct message
		clPing.sign1 = 0x12071980;
		clPing.sign2 = 0x26111975;
		clPing.dwTime_ClientSend = TimerAsync(device_timer);

		// Send it
		__try {
			if (!IsConnectionInit() || net_Disconnected)	break;

			if (!SendPingMessage(clPing)) {
				Msg("* DirectPlayClient: SyncThread: EXIT. (failed to send - disconnected?)");
				break;
			}
		}
		__except (EXCEPTION_EXECUTE_HANDLER)
		{
			Msg("* CLIENT: SyncThread: EXIT. (failed to send - disconnected?)");
			break;
		}

		// Waiting for reply-packet to arrive
		if (!net_Syncronised) {
			u32	old_size = net_DeltaArray.size();
			u32	timeBegin = TimerAsync(device_timer);
			while (!net_Disconnected && (net_DeltaArray.size() == old_size) &&
				(TimerAsync(device_timer) - timeBegin < 5000)) Sleep(1);

			if (net_DeltaArray.size() >= syncSamples) {
				net_Syncronised = TRUE;
				net_TimeDelta = net_TimeDelta_Calculated;
				// keep running: periodic correction above
			}
		}
	}

	return false;
}

void	BaseClient::Sync_Average()
{
	//***** Analyze results: the latest samples only (older ones may date
	// from the level load).
	s64		summary_delta = 0;
	s32		size = _min(s32(net_DeltaArray.size()), 16);
	if (size <= 0)
		return;
	for (s32 i = 0; i < size; ++i)
		summary_delta += s32(net_DeltaArray.recent(u32(i)));

	s64 frac = s64(summary_delta) % s64(size);
	if (frac < 0)				frac = -frac;
	summary_delta /= s64(size);
	if (frac > s64(size / 2))	summary_delta += (summary_delta < 0) ? -1 : 1;
	net_TimeDelta_Calculated = s32(summary_delta);
	net_TimeDelta = (net_TimeDelta * 5 + net_TimeDelta_Calculated) / 6;
	//	Msg("* CLIENT: d(%d), dc(%d), s(%d)",net_TimeDelta,net_TimeDelta_Calculated,size);
}

void BaseClient::_Recieve(const void* data, u32 data_size, u32 /*param*/)
{
	MSYS_PING*    cfg = (MSYS_PING*)data;
	net_Statistic.dwBytesReceived += data_size;

	if ((data_size >= 2 * sizeof(u32))
		&& (cfg->sign1 == 0x12071980)
		&& (cfg->sign2 == 0x26111975)
		)
	{
		// Internal system message
		if ((data_size == sizeof(MSYS_PING)))
		{
			// It is reverted(server) ping
			u32		    time = TimerAsync(device_timer);
			u32		    ping = time - (cfg->dwTime_ClientSend);
			u32		    delta = cfg->dwTime_Server + ping / 2 - time;

			net_DeltaArray.push(delta);
			Sync_Average();
			return;
		}

		if (data_size == sizeof(MSYS_CONFIG))
		{
			net_Connected = EnmConnectionCompleted;
			return;
		}
		Msg("! Unknown system message");
		return;
	}
	else if (net_Connected == EnmConnectionCompleted)
	{
		// one of the messages - decompress it

		//if (psNET_Flags.test(NETFLAG_LOG_CL_PACKETS))
		//{
		//	if (!pClNetLog)
		//		pClNetLog = xr_new<INetLog>("logs\\net_cl_log.log", timeServer());
		//
		//	if (pClNetLog)
		//		pClNetLog->LogData(timeServer(), const_cast<void*>(data), data_size, TRUE);
		//}

		OnMessage(const_cast<void*>(data), data_size);
	}
}

#pragma endregion

// -----------------------------------------------------------------------------

#pragma region bandwidth

bool BaseClient::net_HasBandwidth()
{
	u32		dwTime = TimeGlobal(device_timer);
	u32		dwInterval = 0;
	if (net_Disconnected) return FALSE;

	if (psNET_ClientUpdate != 0) dwInterval = 1000 / psNET_ClientUpdate;
	if (psNET_Flags.test(NETFLAG_MINIMIZEUPDATES))	dwInterval = 1000;	// approx 3 times per second

	if (psNET_direct_connect)
	{
		if (0 != psNET_ClientUpdate && (dwTime - net_Time_LastUpdate) > dwInterval)
		{
			net_Time_LastUpdate = dwTime;
			return					TRUE;
		}
		else
			return					FALSE;

	}
	else if (0 != psNET_ClientUpdate && (dwTime - net_Time_LastUpdate) > dwInterval)
	{
		R_ASSERT(IsConnectionInit());

		// check queue for "empty" state
		DWORD dwPending = 0;
		if (!GetPendingMessagesCount(dwPending))
		{
			return FALSE;
		}

		if (dwPending > u32(psNET_ClientPending))
		{
			net_Statistic.dwTimesBlocked++;
			return FALSE;
		};

		UpdateStatistic();

		// ok
		net_Time_LastUpdate = dwTime;
		return TRUE;
	}
	return FALSE;
}

#pragma endregion
