#include "stdafx.h"
#include "netcoop.h"

#include "xrNetServer/NET_Client.h"
#include "xrMessages.h"
#include "game_base.h"
#include "actor_defs.h"

// NetAnomaly load test (doc 38, target 128 players per server).
//
// Each bot is a real network client of its own: it connects over the same
// transport, logs in with an account, receives the world like a player's
// client does and sends 30 Hz input and movement for its Actor. The bots do
// not load a level, so one extra game process can run a hundred of them and
// the server sees the same traffic and work as from real players.
//
// Handshake (as CLevel does it): connect result -> M_NETCOOP_AUTH and
// M_CREATE_PLAYER_STATE -> M_CLIENT_REQUEST_CONNECTION_DATA -> world spawn
// messages and M_SV_CONFIG_FINISHED -> M_CLIENTREADY -> the server spawns the
// Actor and names it with the script message "you <id> <x> <y> <z>".

namespace netcoop
{
namespace
{
const u32 bot_send_interval = 33; // ms, the player client's update rate
const u32 bot_connect_timeout = 30000;
const u32 bot_actor_timeout = 300000; // joining sends the whole world
const float bot_speed = 3.f; // m/s, walking
LPCSTR const bot_password = "netcoop-bot";

// The engine's global timer is paused in the main menu, where the bots run:
// their clock (server time estimate, send rate) uses a timer of their own.
CTimer& bot_timer()
{
	static CTimer timer;
	static bool started = false;
	if (!started)
	{
		timer.Start();
		started = true;
	}
	return timer;
}

u32 bot_now() { return bot_timer().GetElapsed_ms(); }

class NetcoopBot : public IPureClient
{
public:
	enum State
	{
		st_connecting,
		st_joining,
		st_waiting_actor,
		st_playing,
		st_failed,
	};

	NetcoopBot(u32 index) : IPureClient(&bot_timer()), m_index(index)
	{
		xr_sprintf(m_login, "nbot_%03u", index);
	}

	bool start(LPCSTR address, u32 now)
	{
		string512 options;
		xr_sprintf(options, "%s/name=%s", address, m_login);
		// ParseConnectionOptions writes the player's name into Core.UserName.
		string64 user_name;
		xr_strcpy(user_name, Core.UserName);
		const bool ok = Connect(options);
		xr_strcpy(Core.UserName, user_name);
		m_state_time = now; // the frame's time: later reads would be ahead of it
		if (!ok)
			fail("cannot create the connection");
		return ok;
	}

	void stop()
	{
		if (!m_stopped)
			Disconnect();
		m_stopped = true;
	}

	void update(u32 now)
	{
		if (m_state == st_failed && !m_stopped)
			stop(); // outside the message queue lock
		if (m_state == st_failed || m_stopped)
			return;
		if (m_state == st_connecting)
		{
			if (net_isFails_Connect())
			{
				fail("connection failed");
				return;
			}
			if (!net_isCompleted_Connect())
			{
				if (now - m_state_time > bot_connect_timeout)
					fail("connection timed out");
				return;
			}
			net_Syncronize();
			set_state(st_joining, now);
		}
		if (net_isDisconnected())
		{
			fail("disconnected");
			return;
		}

		receive(now);
		if (m_state == st_failed)
			return;

		if (m_state != st_playing && now - m_state_time > bot_actor_timeout)
		{
			fail("no Actor from the server");
			return;
		}

		if (m_state == st_playing && now - m_last_send >= bot_send_interval)
		{
			m_last_send = now;
			send_movement(now);
		}
		Flush_Send_Buffer();
	}

	State state() const { return m_state; }
	u32 take_bytes()
	{
		const u32 b = m_rx_bytes;
		m_rx_bytes = 0;
		return b;
	}
	u32 take_max_update_gap()
	{
		const u32 g = m_max_update_gap;
		m_max_update_gap = 0;
		return g;
	}
	u32 ping()
	{
		UpdateStatistic();
		return GetStatistic().getPing();
	}

private:
	void set_state(State s, u32 now)
	{
		m_state = s;
		m_state_time = now;
	}

	void fail(LPCSTR why)
	{
		if (m_state != st_failed)
			Msg("! [NetAnomaly][bots] %s: %s", m_login, why);
		m_state = st_failed;
	}

	void send_reliable(NET_Packet& P) { Send(P, net_flags(TRUE, TRUE)); }

	void join()
	{
		xr_string key;
		if (!derive_client_key(m_login, bot_password, key))
		{
			fail("cannot derive the account key");
			return;
		}
		NET_Packet P;
		P.w_begin(M_NETCOOP_AUTH);
		P.w_u8(auth_auto);
		P.w_stringZ(m_login);
		P.w_stringZ(key.c_str());
		send_reliable(P);

		P.w_begin(M_CREATE_PLAYER_STATE);
		game_PlayerState state(NULL);
		state.net_Export(P, TRUE);
		send_reliable(P);

		P.w_begin(M_CLIENT_REQUEST_CONNECTION_DATA);
		send_reliable(P);
	}

	void receive(u32 now)
	{
		StartProcessQueue();
		for (NET_Packet* P = net_msg_Retreive(); P; P = net_msg_Retreive())
		{
			m_rx_bytes += P->B.count;
			if (P->B.count >= 2)
				on_message(*P, now);
			net_msg_Release();
		}
		EndProcessQueue();
	}

	void on_message(NET_Packet& P, u32 now)
	{
		u16 type;
		P.r_begin(type);
		switch (type)
		{
		case M_CLIENT_CONNECT_RESULT:
			{
				const u8 result = P.r_u8();
				P.r_u8();
				string512 text;
				if (!read_string(P, text, sizeof(text)))
					text[0] = 0;
				if (P.r_elapsed() >= sizeof(u32))
				{
					ClientID id;
					P.r_clientID(id);
					SetClientID(id);
				}
				if (!result)
				{
					fail(text[0] ? text : "connection rejected");
					return;
				}
				if (!m_joined)
				{
					m_joined = true;
					join();
				}
			}
			break;
		case M_NETCOOP_AUTH_RESULT:
			{
				const u8 ok = P.r_u8();
				P.r_u8();
				string512 text;
				if (!read_string(P, text, sizeof(text)))
					text[0] = 0;
				if (!ok)
					fail(text);
			}
			break;
		case M_SV_CONFIG_FINISHED:
			if (!m_ready_sent)
			{
				m_ready_sent = true;
				NET_Packet R;
				R.w_begin(M_CLIENTREADY);
				game_PlayerState state(NULL);
				state.net_Export(R, TRUE);
				send_reliable(R);
				set_state(st_waiting_actor, now);
			}
			break;
		case M_NETCOOP_SCRIPT:
			{
				string64 channel;
				string256 data;
				if (!read_string(P, channel, sizeof(channel)) || !read_string(P, data, sizeof(data)))
					break;
				if (xr_strcmp(channel, "you"))
					break;
				u32 id = 0xffff;
				Fvector pos;
				if (sscanf_s(data, "%u %f %f %f", &id, &pos.x, &pos.y, &pos.z) != 4 || id >= 0xffff || !_valid(pos))
					break;
				m_actor = u16(id);
				m_center = pos;
				m_phase = float(m_index) * 0.7f;
				m_radius = 4.f + float(m_index % 12) * 2.5f;
				m_last_move = now;
				Msg("[NetAnomaly][bots] %s plays Actor %u", m_login, id);
				set_state(st_playing, now);
			}
			break;
		case M_UPDATE:
		case M_UPDATE_OBJECTS:
			if (m_last_update)
				m_max_update_gap = _max(m_max_update_gap, now - m_last_update);
			m_last_update = now;
			break;
		}
	}

	void send_movement(u32 now)
	{
		const float dt = float(now - m_last_move) * 0.001f;
		m_last_move = now;
		m_phase += dt * bot_speed / m_radius;

		Fvector pos;
		pos.set(m_center.x + m_radius * _cos(m_phase), m_center.y, m_center.z + m_radius * _sin(m_phase));
		Fvector vel;
		vel.set(-_sin(m_phase), 0.f, _cos(m_phase));
		const float yaw = angle_normalize(-vel.getH());
		vel.mul(bot_speed);

		NET_Packet P;
		P.w_begin(M_CL_INPUT);
		P.w_u32(m_input_sequence++);
		P.w_u16(u16(ACTOR_DEFS::mcFwd));
		P.w_float(angle_normalize_signed(yaw));
		P.w_float(0.f);
		send_reliable(P);

		// CActor::net_Export layout including equipment identities and visual.
		P.w_begin(M_CL_UPDATE);
		P.w_u16(m_actor);
		P.w_u32(0); // ping, filled in by the server
		P.w_float(1.f); // health
		P.w_u32(now); // the owner's real-time clock; the server maps it
		P.w_u8(0); // flags
		P.w_vec3(pos);
		P.w_float(yaw); // model yaw
		P.w_float(yaw); // torso yaw
		P.w_float(0.f); // torso pitch
		P.w_float(0.f); // torso roll
		P.w_u8(0); // team
		P.w_u8(0); // squad
		P.w_u8(0); // group
		P.w_u16(u16(ACTOR_DEFS::mcFwd));
		P.w_sdir(Fvector().set(0.f, 0.f, 0.f)); // acceleration
		P.w_sdir(vel);
		P.w_float(0.f); // radiation
		P.w_u8(0); // active slot
		P.w_u16(u16(-1)); // hands
		P.w_u16(u16(-1)); // outfit
		P.w_u16(u16(-1)); // helmet
		P.w_stringZ("actors\\stalker_neutral\\stalker_neutral_1.ogf");
		P.w_u16(0); // physics items
		Send(P, net_flags(FALSE));
	}

	u32 m_index;
	string64 m_login;
	State m_state = st_connecting;
	u32 m_state_time = 0;
	bool m_stopped = false;
	bool m_joined = false;
	bool m_ready_sent = false;

	u16 m_actor = 0xffff;
	Fvector m_center{};
	float m_phase = 0.f;
	float m_radius = 5.f;
	u32 m_last_move = 0;
	u32 m_last_send = 0;
	u32 m_input_sequence = 1;

	u32 m_rx_bytes = 0;
	u32 m_last_update = 0;
	u32 m_max_update_gap = 0;
};

struct DeadBot
{
	NetcoopBot* bot;
	u32 since;
};

xr_vector<NetcoopBot*> s_bots;
xr_vector<DeadBot> s_dead; // deleted a few seconds later: their sync thread may still run
u32 s_wanted = 0;
u32 s_last_start = 0;
u32 s_last_report = 0;
string256 s_address = "127.0.0.1";
bool s_command_line_checked = false;

void check_command_line()
{
	if (s_command_line_checked)
		return;
	s_command_line_checked = true;
	LPCSTR p = strstr(Core.Params, "-netcoop_bots ");
	if (!p)
		return;
	u32 count = 0;
	if (sscanf_s(p + xr_strlen("-netcoop_bots "), "%u", &count) != 1)
		return;
	string256 address = "127.0.0.1";
	LPCSTR a = strstr(Core.Params, "-netcoop_bots_addr ");
	if (a)
		sscanf_s(a + xr_strlen("-netcoop_bots_addr "), "%255s", address, (unsigned)sizeof(address));
	bots_set(count, address);
}

void report(u32 now)
{
	if (now - s_last_report < 10000)
		return;
	const float seconds = s_last_report ? float(now - s_last_report) * 0.001f : 10.f;
	s_last_report = now;
	if (s_bots.empty())
		return;
	u32 counts[NetcoopBot::st_failed + 1] = {};
	u64 bytes = 0;
	u32 max_gap = 0, gaps = 0, gap_sum = 0, ping_sum = 0, pinged = 0;
	for (NetcoopBot* b : s_bots)
	{
		counts[b->state()]++;
		bytes += b->take_bytes();
		const u32 gap = b->take_max_update_gap();
		if (b->state() == NetcoopBot::st_playing)
		{
			if (gap)
			{
				max_gap = _max(max_gap, gap);
				gap_sum += gap;
				++gaps;
			}
			ping_sum += b->ping();
			++pinged;
		}
	}
	Msg("[NetAnomaly][bots] %u wanted: %u playing, %u joining, %u connecting, %u failed; rx %.1f KB/s per playing bot, "
	    "worst update gap avg %u ms max %u ms, ping avg %u ms",
	    s_wanted, counts[NetcoopBot::st_playing], counts[NetcoopBot::st_joining] + counts[NetcoopBot::st_waiting_actor],
	    counts[NetcoopBot::st_connecting], counts[NetcoopBot::st_failed],
	    counts[NetcoopBot::st_playing] ? float(bytes) / 1024.f / seconds / float(counts[NetcoopBot::st_playing]) : 0.f,
	    gaps ? gap_sum / gaps : 0, max_gap, pinged ? ping_sum / pinged : 0);
	FlushLog();
}
} // namespace

void bots_set(u32 count, LPCSTR address)
{
	clamp(count, u32(0), u32(256));
	if (address && address[0])
		xr_strcpy(s_address, address);
	s_wanted = count;
	while (s_bots.size() > s_wanted)
	{
		NetcoopBot* b = s_bots.back();
		s_bots.pop_back();
		b->stop();
		s_dead.push_back({b, bot_now()});
	}
	Msg("[NetAnomaly][bots] target %u bot(s) on %s", s_wanted, s_address);
}

void bots_frame()
{
	check_command_line();
	const u32 now = bot_now();

	for (u32 i = 0; i < s_dead.size();)
	{
		if (now - s_dead[i].since > 5000)
		{
			xr_delete(s_dead[i].bot);
			s_dead[i] = s_dead.back();
			s_dead.pop_back();
		}
		else
			++i;
	}

	// One new connection every 250 ms, like players arriving; a join makes
	// the server send the whole world, so a burst would measure only that.
	if (s_bots.size() < s_wanted && now - s_last_start >= 250)
	{
		s_last_start = now;
		NetcoopBot* b = xr_new<NetcoopBot>(u32(s_bots.size()) + 1);
		s_bots.push_back(b);
		b->start(s_address, now);
	}

	for (NetcoopBot* b : s_bots)
		b->update(now);
	report(now);
}
} // namespace netcoop
