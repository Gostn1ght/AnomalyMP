#include "stdafx.h"
#include "netcoop.h"

#include "xrNetServer/NET_Client.h"
#include "xrMessages.h"
#include "game_base.h"
#include "actor_defs.h"
#include "alife_space.h"

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
void firebase_frame();
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

// Account verification uses the game's transport, but never requests a world,
// player state or Actor. No network clock thread is needed for this exchange.
class FrontendAccountClient : public IPureClient
{
public:
	FrontendAccountClient() : IPureClient(&bot_timer()) {}
	bool start(LPCSTR options)
	{
		m_started = bot_now();
		string64 user_name;
		xr_strcpy(user_name, Core.UserName);
		const bool connected = Connect(options);
		xr_strcpy(Core.UserName, user_name);
		if (!connected) fail("Cannot connect to the account server");
		return connected;
	}
	bool update()
	{
		// Drain replies before checking disconnection: a successful slot-zero
		// login ends with the server closing this temporary connection.
		StartProcessQueue();
		for (NET_Packet* P = net_msg_Retreive(); P; P = net_msg_Retreive())
		{
			if (!m_done && P->B.count >= 2)
			{
				u16 type; P->r_begin(type);
				if (type == M_NETCOOP_AUTH_RESULT && P->r_elapsed() >= 3)
				{
					m_reply = *P;
					m_done = true;
				}
				else if (type == M_CLIENT_CONNECT_RESULT && P->r_elapsed() >= 3)
				{
					const u8 accepted = P->r_u8(); P->r_u8();
					string512 reason;
					if (!read_string(*P, reason, sizeof(reason))) reason[0] = 0;
					if (P->r_elapsed() >= sizeof(u32))
					{
						ClientID id; P->r_clientID(id); SetClientID(id);
					}
					if (!accepted) fail(reason[0] ? reason : "Account connection rejected");
					else if (!m_auth_sent)
					{
						m_auth_sent = true;
						NET_Packet auth; auth.w_begin(M_NETCOOP_AUTH);
						client_write_auth(auth);
						Send(auth, net_flags(TRUE, TRUE));
					}
				}
			}
			net_msg_Release();
		}
		EndProcessQueue();
		if (!m_done && (net_isDisconnected() || net_isFails_Connect())) fail("Account server disconnected");
		if (!m_done && bot_now() - m_started > bot_connect_timeout) fail("Account server did not respond");
		if (!m_done) { Flush_Send_Buffer(); return false; }
		Disconnect();
		// Lua can create the character screen here; never call it under the
		// receive queue lock or while the transport still owns callbacks.
		client_on_auth_result(m_reply);
		return true;
	}
private:
	void fail(LPCSTR reason)
	{
		m_reply.w_begin(M_NETCOOP_AUTH_RESULT);
		m_reply.w_u8(0); m_reply.w_u8(role_none); m_reply.w_stringZ(reason);
		u16 type; m_reply.r_begin(type);
		m_done = true;
	}
	u32 m_started = 0;
	bool m_done = false, m_auth_sent = false;
	NET_Packet m_reply;
};

FrontendAccountClient* s_frontend_account = nullptr;

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
		if (m_state == st_playing && m_cheat_target != 0xffff && !m_cheated && now - m_state_time > 15000)
		{
			m_cheated = true;
			send_cheats();
		}
		Flush_Send_Buffer();
	}

	State state() const { return m_state; }
	LPCSTR transfer() const { return m_transfer[0] ? m_transfer : nullptr; }
	u32 index() const { return m_index; }
	bool played() const { return m_played; }
	u32 failed_at() const { return m_failed_at; }
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
		if (s == st_playing)
			m_played = true;
	}

	void fail(LPCSTR why)
	{
		if (m_state != st_failed)
			Msg("! [Lost Zone][bots] %s: %s", m_login, why);
		if (m_state != st_failed)
			m_failed_at = bot_now();
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
				// Location cluster: the server sends the character to another
				// map; bots_frame reconnects this bot there.
				if (!xr_strcmp(channel, "netcoop_transfer"))
				{
					char host[128] = {}, level[64] = {};
					u32 port = 0;
					if (sscanf_s(data, "%127[^|]|%u|%63s", host, (unsigned)sizeof(host), &port, level, (unsigned)sizeof(level)) == 3)
					{
						xr_sprintf(m_transfer, "%s/port=%u", host, port);
						Msg("[Lost Zone][bots] %s goes to %s (%s)", m_login, level, m_transfer);
					}
					break;
				}
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
				Msg("[Lost Zone][bots] %s plays Actor %u at %.1f %.1f %.1f", m_login, id, pos.x, pos.y, pos.z);
				set_state(st_playing, now);
			}
			break;
		case M_NETCOOP_PHYSICS:
			// -netcoop_bots_watch=<id> (run-prop-test.ps1): report the poses of
			// one object the server sends to this player.
			if (m_watch != 0xffff && P.r_elapsed() >= 2 + 4 + 2 + 41)
			{
				const u16 id = P.r_u16();
				P.r_u32();
				P.r_u16();
				P.r_u8();
				Fvector position;
				P.r_vec3(position);
				if (id == m_watch && now - m_watch_log > 1000)
				{
					m_watch_log = now;
					Msg("[Lost Zone][bots] %s got the pose of %u: %.2f %.2f %.2f", m_login, id, position.x, position.y, position.z);
				}
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

	// -netcoop_bots_cheat=<id> (run-cheat-test.ps1, doc 43 A11): the first
	// bot sends what an honest client never does: a deadly hit on that
	// object, the same hit as a game event, its death, a "transfer" that
	// asserted on the server, and its destruction. The server must refuse
	// them all and stay up; the object must stay alive.
	void send_cheats()
	{
		const u16 target = m_cheat_target;
		auto header = [&](NET_Packet& P, u16 event, u16 dest)
		{
			P.w_begin(M_EVENT);
			P.w_u32(0);
			P.w_u16(event);
			P.w_u16(dest);
		};
		auto hit_body = [&](NET_Packet& P)
		{
			P.w_u16(m_actor); // who
			P.w_u16(m_actor); // weapon
			P.w_dir(Fvector().set(0.f, 0.f, 1.f));
			P.w_float(1000.f); // power
			P.w_u16(0); // bone
			P.w_vec3(Fvector().set(0.f, 0.f, 0.f));
			P.w_float(0.f); // impulse
			P.w_u16(0); // aim bullet
			P.w_u16(u16(ALife::eHitTypeWound));
			P.w_u32(0); // bullet
		};
		NET_Packet P;
		header(P, GE_HIT, target);
		hit_body(P);
		send_reliable(P);
		header(P, GE_GAME_EVENT, 0);
		P.w_u16(GAME_EVENT_ON_HIT);
		P.w_u16(target);
		hit_body(P);
		send_reliable(P);
		header(P, GE_DIE, target);
		P.w_u16(m_actor);
		send_reliable(P);
		header(P, GE_TRANSFER_AMMO, target);
		P.w_u16(target);
		send_reliable(P);
		header(P, GE_DESTROY, target);
		send_reliable(P);
		Msg("[Lost Zone][bots] %s sent forged hit, game-event hit, death, ammo transfer and destroy for %u", m_login, target);
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
	string256 m_transfer = {};
	State m_state = st_connecting;
	u32 m_state_time = 0;
	u32 m_failed_at = 0;
	bool m_played = false;
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

public:
	u16 m_cheat_target = 0xffff;
	bool m_cheated = false;
	u16 m_watch = 0xffff;
	u32 m_watch_log = 0;
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
u32 s_first = 0; // -netcoop_bots_first: several bot processes, distinct logins
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
	if (LPCSTR f = strstr(Core.Params, "-netcoop_bots_first "))
		sscanf_s(f + xr_strlen("-netcoop_bots_first "), "%u", &s_first);
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
	Msg("[Lost Zone][bots] %u wanted: %u playing, %u joining, %u connecting, %u failed; rx %.1f KB/s per playing bot, "
	    "worst update gap avg %u ms max %u ms, ping avg %u ms",
	    s_wanted, counts[NetcoopBot::st_playing], counts[NetcoopBot::st_joining] + counts[NetcoopBot::st_waiting_actor],
	    counts[NetcoopBot::st_connecting], counts[NetcoopBot::st_failed],
	    counts[NetcoopBot::st_playing] ? float(bytes) / 1024.f / seconds / float(counts[NetcoopBot::st_playing]) : 0.f,
	    gaps ? gap_sum / gaps : 0, max_gap, pinged ? ping_sum / pinged : 0);
	FlushLog();
}
} // namespace

bool script_frontend_auth(LPCSTR options)
{
	if (g_pGameLevel || s_frontend_account || !options || !options[0] || xr_strlen(options) >= 512)
		return false;
	s_frontend_account = xr_new<FrontendAccountClient>();
	s_frontend_account->start(options);
	return true; // even an immediate transport error is delivered next frame
}

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
	Msg("[Lost Zone][bots] target %u bot(s) on %s", s_wanted, s_address);
}

void bots_frame()
{
	firebase_frame();
	if (s_frontend_account && s_frontend_account->update())
		xr_delete(s_frontend_account);
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
		NetcoopBot* b = xr_new<NetcoopBot>(s_first + u32(s_bots.size()) + 1);
		if (s_bots.empty())
		{
			if (LPCSTR c = strstr(Core.Params, "-netcoop_bots_cheat="))
				b->m_cheat_target = u16(atoi(c + xr_strlen("-netcoop_bots_cheat=")));
			if (LPCSTR w = strstr(Core.Params, "-netcoop_bots_watch="))
				b->m_watch = u16(atoi(w + xr_strlen("-netcoop_bots_watch=")));
		}
		s_bots.push_back(b);
		b->start(s_address, now);
	}

	// A join that failed before playing is retried, as the player's client
	// reconnects: a handshake lost under load is not a lost player.
	static xr_map<u32, u32> retries;
	for (NetcoopBot*& b : s_bots)
	{
		if (b->state() == NetcoopBot::st_failed && !b->played() && now - b->failed_at() > 3000 && retries[b->index()] < 3)
		{
			const u32 attempt = ++retries[b->index()];
			Msg("[Lost Zone][bots] nbot_%03u retries (%u)", b->index(), attempt);
			NetcoopBot* again = xr_new<NetcoopBot>(b->index());
			b->stop();
			s_dead.push_back({b, now});
			b = again;
			b->start(s_address, now);
			continue;
		}
		b->update(now);
		if (LPCSTR target = b->transfer())
		{
			NetcoopBot* moved = xr_new<NetcoopBot>(b->index());
			string256 address; xr_strcpy(address, target);
			b->stop();
			s_dead.push_back({b, now});
			b = moved;
			b->start(address, now);
		}
	}
	report(now);
}
} // namespace netcoop
