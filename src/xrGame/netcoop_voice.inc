// Included inside namespace netcoop in netcoop.cpp.
// Voice chat and walkie-talkies (owner 2026-10-10; ported from NEAREST-STAGE's
// VoiceChat/VoiceSender/WalkieTalkie and reworked for the netcoop server).
//
// Talking: the "voice near" key (Controls) speaks to people around; three
// loudness levels (whisper 4 m, normal 16 m, shout 45 m; "voice range" key).
// Radio: the "voice radio" key speaks into the walkie-talkie. It works while
// a walkie-talkie is anywhere in the inventory (no slot, no hands), switched
// on, on a frequency. As in Lost Zone the walkie can also be taken into the
// left hand (detector slot): with nothing in the right hand, holding fire
// talks into it (it is raised to the face, others see the pose) and zoom
// opens its settings. Everybody on that frequency within radio range hears
// it in the ear with a radio voice, and people standing next to a receiver
// hear its speaker too; people around the talker hear him directly.
//
// The server decides who hears what (positions, radio items and frequencies
// are the server's), so a client cannot listen in on other frequencies or
// far conversations. Client -> server M_NETCOOP_VOICE:
//   u8 mode (0 near, 1 radio), u8 loudness (0..2), u16 first seq, u8 n, n x (u16 len, bytes)
// Server -> client M_NETCOOP_VOICE:
//   u16 speaker, u8 mode (0 near, 1 radio in the ear, 2 a receiver's speaker),
//   u8 loudness, u16 source (where it sounds: speaker or receiver), u16 first seq, u8 n, frames.

static const float voice_range_m[3] = {4.f, 16.f, 45.f};
static const float voice_speaker_m = 12.f;   // a receiver's loudspeaker
static const u32 voice_max_frames = 4, voice_max_bytes = 1400;

static float voice_radio_range()
{
	return READ_IF_EXISTS(pSettings, r_float, "netcoop_voice", "radio_range", 2000.f);
}
static bool voice_radio_section(LPCSTR section)
{
	static xr_vector<shared_str> sections;
	static bool loaded = false;
	if (!loaded)
	{
		loaded = true;
		LPCSTR list = READ_IF_EXISTS(pSettings, r_string, "netcoop_voice", "radio_items", "walkie");
		string128 item;
		for (int i = 0, n = _GetItemCount(list); i < n; ++i) sections.push_back(_GetItem(list, i, item));
	}
	for (const shared_str& s : sections) if (!xr_strcmp(s, section)) return true;
	return false;
}

//----------------------------------------------------------------------
// Client
//----------------------------------------------------------------------
struct VoiceUplink : public IVoiceSink
{
	u8 mode = 0, loudness = 1, frames = 0;
	u16 first = 0;
	u32 size = 0;
	u8 data[voice_max_bytes];

	void flush()
	{
		if (!frames || !g_pGameLevel) return;
		NET_Packet P;
		P.w_begin(M_NETCOOP_VOICE);
		P.w_u8(mode); P.w_u8(loudness); P.w_u16(first); P.w_u8(frames);
		P.w(data, size);
		Level().Send(P, net_flags(FALSE, TRUE, TRUE, TRUE));
		frames = 0; size = 0;
	}
	void OnVoiceFrame(const u8* bytes, u32 length, u16 seq) override
	{
		if (length > VOICE_MAX_PACKET) return;
		if (size + 2 + length > sizeof(data) || frames >= voice_max_frames) flush();
		if (!frames) first = seq;
		data[size] = u8(length); data[size + 1] = u8(length >> 8);
		CopyMemory(data + size + 2, bytes, length);
		size += 2 + length;
		if (++frames >= 2) flush(); // 80 ms per packet
	}
};

struct VoicePlayback
{
	IVoicePlayer* player = nullptr;
	u16 source = 0xffff;
	u8 mode = 0, loudness = 1;
	u32 last = 0, occlusion_at = 0;
	float muffle = 0.f;
};

static VoiceUplink s_voice_up;
static bool s_voice_key_near = false, s_voice_key_radio = false, s_voice_capture_tried = false;
static bool s_voice_open = false; // "voice toggle": microphone on, sends while the player speaks
static bool s_voice_hand_talk = false; // fire held with the walkie-talkie in the hand
static bool s_voice_radio_was = false; // talking into the radio last frame (press/release clicks)
static u32 s_voice_capture_at = 0;
static u8 s_voice_loudness = 1;
static bool s_voice_radio_on = false, s_voice_radio_have = false;
static u16 s_voice_radio_freq = 0;
static xr_map<u32, VoicePlayback> s_voice_players;   // speaker << 2 | mode
static xr_map<u16, u32> s_voice_heard;               // speaker -> last near frame (head icon)
static ui_shader s_voice_icon;

static ISoundVoice* voice_audio() { return ::Sound ? ::Sound->voice() : nullptr; }

static void voice_tip(LPCSTR id)
{
	::luabind::functor<void> tip;
	if (ai().script_engine().functor("netcoop_voice_ui.tip", tip)) tip(id);
}

static void voice_play(LPCSTR name)
{
	::luabind::functor<void> play;
	if (ai().script_engine().functor("netcoop_voice_ui.play", play)) play(name);
}

// The walkie-talkie shown in the left hand while the right hand is empty.
static CCustomDevice* voice_hand_walkie()
{
	CActor* actor = Actor();
	if (!actor || !actor->g_Alive() || actor->inventory().ActiveItem()) return nullptr;
	CCustomDevice* device = smart_cast<CCustomDevice*>(actor->inventory().ItemFromSlot(DETECTOR_SLOT));
	if (!device || !voice_radio_section(device->cNameSect().c_str())) return nullptr;
	const u32 state = device->GetState();
	if (state != CHUDState::eIdle && state != CHUDState::eBore && state != CCustomDevice::eIdleZoom &&
		state != CCustomDevice::eIdleZoomIn && state != CCustomDevice::eIdleZoomOut)
		return nullptr;
	return device;
}

// CCustomDevice: raise this device to the face (its zoom pose) while talking into it.
bool client_device_talking(CCustomDevice* device)
{
	return device && pure_client() && s_voice_radio_have && s_voice_radio_on &&
		(s_voice_hand_talk || s_voice_key_radio) && device == voice_hand_walkie();
}

// Controls: voice_near / voice_radio held = talking; voice_range cycles loudness.
// With the walkie-talkie in the hand: fire held = talking into it, zoom = settings.
bool client_voice_key(int action, bool pressed)
{
	if (!pure_client()) return false;
	const bool hand = action == kWPN_FIRE || action == kWPN_ZOOM;
	if (!hand && action != kVOICE_NEAR && action != kVOICE_RADIO && action != kVOICE_RANGE && action != kVOICE_TOGGLE) return false;
	if (pressed && CurrentGameUI() && CurrentGameUI()->TopInputReceiver() && CurrentGameUI()->TopInputReceiver()->NeedCursor())
		return false;
	if (hand)
	{
		if (!pressed)
		{
			if (action != kWPN_FIRE || !s_voice_hand_talk) return false;
			s_voice_hand_talk = false;
			return true;
		}
		if (!voice_hand_walkie()) return false;
		if (action == kWPN_ZOOM)
		{
			::luabind::functor<void> open;
			if (ai().script_engine().functor("netcoop_voice_ui.open_radio", open)) open();
			return true;
		}
		if (!s_voice_radio_on) voice_tip("st_voice_radio_off");
		s_voice_hand_talk = true;
		return true;
	}
	if (action == kVOICE_NEAR) { s_voice_key_near = pressed; return true; }
	if (action == kVOICE_RADIO)
	{
		if (pressed && !(s_voice_radio_have && s_voice_radio_on))
			voice_tip(s_voice_radio_have ? "st_voice_radio_off" : "st_voice_no_radio");
		s_voice_key_radio = pressed;
		return true;
	}
	if (action == kVOICE_TOGGLE)
	{
		if (pressed)
		{
			s_voice_open = !s_voice_open;
			voice_tip(s_voice_open ? "st_voice_mic_on" : "st_voice_mic_off");
		}
		return true;
	}
	if (action == kVOICE_RANGE)
	{
		if (pressed)
		{
			s_voice_loudness = u8((s_voice_loudness + 1) % 3);
			static LPCSTR names[3] = {"st_voice_whisper", "st_voice_normal", "st_voice_shout"};
			voice_tip(names[s_voice_loudness]);
		}
		return true;
	}
	return false;
}

// Lua (the radio window and the server's answer): this player's own walkie-talkie.
void script_voice_radio_local(int freq, bool on, bool have)
{
	s_voice_radio_freq = u16(_max(0, freq));
	s_voice_radio_on = on;
	s_voice_radio_have = have;
}

// Lua (HUD): "talking|mode|loudness|mic level" for the indicator.
LPCSTR script_voice_status()
{
	static string64 out;
	ISoundVoice* voice = voice_audio();
	const bool talking = voice && voice->Transmitting();
	xr_sprintf(out, "%d|%d|%d|%.2f|%d", talking ? 1 : 0, s_voice_up.mode, s_voice_loudness, voice ? voice->InputLevel() : 0.f,
		s_voice_open ? 1 : 0);
	return out;
}

static void voice_release_players()
{
	ISoundVoice* voice = voice_audio();
	for (auto& it : s_voice_players)
		if (voice && it.second.player) voice->DestroyPlayer(it.second.player);
	s_voice_players.clear();
	s_voice_heard.clear();
}

void client_voice_update()
{
	ISoundVoice* voice = voice_audio();
	if (!pure_client() || !voice || !g_pGameLevel) return;
	CActor* actor = Actor();
	const u32 now = Device.dwTimeGlobal;
	if (actor && !voice->Capturing() && (!s_voice_capture_tried || now - s_voice_capture_at > 15000))
	{
		s_voice_capture_tried = true;
		s_voice_capture_at = now;
		voice->StartCapture(&s_voice_up);
	}
	if (s_voice_hand_talk && !voice_hand_walkie()) s_voice_hand_talk = false; // put away, took a weapon, died
	const bool alive = actor && actor->g_Alive();
	const bool radio = alive && (s_voice_key_radio || s_voice_hand_talk) && s_voice_radio_have && s_voice_radio_on;
	const bool talk = alive && (radio || s_voice_key_near);
	if (radio != s_voice_radio_was)
	{
		s_voice_radio_was = radio;
		voice_play(radio ? "radio_active" : "radio_deactive"); // the walkie's own press/release clicks
	}
	const u8 mode = radio ? 1 : 0;
	if (s_voice_up.mode != mode || s_voice_up.loudness != s_voice_loudness) s_voice_up.flush();
	s_voice_up.mode = mode;
	s_voice_up.loudness = s_voice_loudness;
	voice->SetTransmit(talk);
	voice->SetOpenMic(alive && s_voice_open); // near voice, sent while speaking
	if (!talk && !voice->Transmitting()) s_voice_up.flush();
	voice_record_update();

	// Speakers: follow their bodies; walls muffle; forget the silent ones.
	const Fvector& ear = Device.vCameraPosition;
	for (auto it = s_voice_players.begin(); it != s_voice_players.end();)
	{
		VoicePlayback& p = it->second;
		CObject* source = Level().Objects.net_Find(p.source);
		if (!p.player || now - p.last > 20000 || (p.mode != 1 && !source))
		{
			if (p.player) voice->DestroyPlayer(p.player);
			it = s_voice_players.erase(it);
			continue;
		}
		if (p.mode != 1 && source)
		{
			Fvector pos = source->Position();
			pos.y += 1.6f;
			p.player->SetPosition(pos);
			if (now - p.occlusion_at > 250)
			{
				p.occlusion_at = now;
				Fvector dir; dir.sub(pos, ear);
				const float dist = dir.magnitude();
				bool blocked = false;
				if (dist > 1.f && dist < 120.f)
				{
					dir.div(dist);
					collide::rq_result hit;
					blocked = Level().ObjectSpace.RayPick(ear, dir, dist - 0.5f, collide::rqtStatic, hit, nullptr) != FALSE;
				}
				p.muffle = blocked ? 0.7f : 0.f;
				p.player->SetMuffle(p.muffle);
			}
		}
		++it;
	}
}

void client_on_voice(NET_Packet& P)
{
	ISoundVoice* voice = voice_audio();
	if (!pure_client() || !voice || P.r_elapsed() < 9) return;
	const u16 speaker = P.r_u16();
	const u8 mode = P.r_u8(), loudness = P.r_u8();
	const u16 source = P.r_u16(), first = P.r_u16();
	const u8 frames = P.r_u8();
	if (mode > 2 || loudness > 2 || frames > voice_max_frames) return;
	if (Actor() && Actor()->ID() == speaker) return;
	VoicePlayback& p = s_voice_players[u32(speaker) << 2 | mode];
	if (!p.player) p.player = voice->CreatePlayer();
	if (!p.player) return;
	p.mode = mode; p.loudness = loudness; p.source = source; p.last = Device.dwTimeGlobal;
	p.player->SetMode(mode != 0, mode != 1);
	p.player->SetRange(mode == 0 ? voice_range_m[loudness] : voice_speaker_m);
	Fvector pos;
	bool placed = false;
	if (mode != 1)
	{
		if (CObject* obj = Level().Objects.net_Find(source))
		{
			pos = obj->Position();
			pos.y += 1.6f;
			p.player->SetPosition(pos);
			placed = true;
		}
	}
	for (u8 i = 0; i < frames && P.r_elapsed() >= 2; ++i)
	{
		const u16 length = P.r_u16();
		if (!length || length > VOICE_MAX_PACKET || P.r_elapsed() < length) return;
		u8 bytes[VOICE_MAX_PACKET];
		P.r(bytes, length);
		p.player->Push(bytes, length, u16(first + i));
		// the dictaphone hears it too: nearby voices, the radio, receivers' speakers
		voice_record_heard(speaker, mode, placed ? &pos : nullptr, u16(first + i), bytes, length);
	}
	if (mode == 0) s_voice_heard[speaker] = Device.dwTimeGlobal;
}

// The icon above the heads of players talking nearby.
void client_voice_render()
{
	if (!pure_client() || s_voice_heard.empty()) return;
	if (!s_voice_icon->inited()) s_voice_icon->create("friendly_indicator", "ui\\ui_voice");
	const u32 now = Device.dwTimeGlobal;
	for (auto it = s_voice_heard.begin(); it != s_voice_heard.end();)
	{
		if (now - it->second > 400) { it = s_voice_heard.erase(it); continue; }
		CActor* speaker = smart_cast<CActor*>(Level().Objects.net_Find(it->first));
		if (speaker && speaker->g_Alive()) speaker->RenderIndicator(Fvector().set(0.f, 0.5f, 0.f), 0.12f, 0.12f, s_voice_icon);
		++it;
	}
}

void client_voice_reset() { voice_record_reset(); voice_release_players(); s_voice_key_near = s_voice_key_radio = s_voice_hand_talk = s_voice_radio_was = false; }

//----------------------------------------------------------------------
// Server
//----------------------------------------------------------------------
struct ServerRadio { u16 freq = 0; bool on = false; u32 checked = 0; bool has = false; };
static xr_map<u16, ServerRadio> s_server_radio;          // player Actor -> walkie-talkie
static xr_map<u32, std::pair<u32, u32>> s_voice_budget;   // client -> (second, packets)

// Lua (the player's radio settings, kept with the character).
void script_voice_radio_set(u16 actor, int freq, bool on)
{
	ServerRadio& r = s_server_radio[actor];
	r.freq = u16(_max(0, freq));
	r.on = on;
}

static bool voice_has_radio(CActor* actor)
{
	ServerRadio& r = s_server_radio[actor->ID()];
	const u32 now = Device.dwTimeGlobal;
	if (!r.checked || now - r.checked > 1000)
	{
		r.checked = now;
		r.has = false;
		for (PIItem item : actor->inventory().m_all)
			if (item && voice_radio_section(item->object().cNameSect().c_str())) { r.has = true; break; }
	}
	return r.has;
}

static bool voice_radio_tuned(CActor* actor, u16 freq)
{
	auto it = s_server_radio.find(actor->ID());
	return it != s_server_radio.end() && it->second.on && it->second.freq == freq && voice_has_radio(actor);
}

void server_on_voice(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!CL || !CL->owner || CL->netcoop_role == role_none || P.r_elapsed() < 5) return;
	CActor* speaker = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	if (!speaker || !speaker->g_Alive()) return;
	// At most 30 packets a second (12.5 are sent while talking).
	auto& budget = s_voice_budget[CL->ID.value()];
	const u32 second = Device.dwTimeGlobal / 1000;
	if (budget.first != second) budget = std::make_pair(second, 0u);
	if (++budget.second > 30) return;
	const u8 mode = P.r_u8(), loudness = _min(P.r_u8(), u8(2));
	const u16 first = P.r_u16();
	const u8 frames = P.r_u8();
	const u32 size = P.r_elapsed();
	if (mode > 1 || !frames || frames > voice_max_frames || size > voice_max_bytes) return;
	u8 payload[voice_max_bytes];
	P.r(payload, size);
	// Frames must fill the payload exactly.
	u32 at = 0;
	for (u8 i = 0; i < frames; ++i)
	{
		if (at + 2 > size) return;
		const u32 len = payload[at] | (u32(payload[at + 1]) << 8);
		if (!len || len > VOICE_MAX_PACKET || at + 2 + len > size) return;
		at += 2 + len;
	}
	if (at != size) return;

	struct Listener { xrClientData* client; CActor* actor; bool sent; };
	xr_vector<Listener> listeners;
	struct Collect
	{
		xrServer* server; xrClientData* from; xr_vector<Listener>* out;
		void operator()(IClient* client)
		{
			xrClientData* C = static_cast<xrClientData*>(client);
			if (C == from || C == server->GetServerClient() || !C->flags.bConnected || !C->gamma_snapshot_ready || !C->owner) return;
			CActor* a = smart_cast<CActor*>(Level().Objects.net_Find(C->owner->ID));
			if (a && a->g_Alive()) out->push_back(Listener{C, a, false});
		}
	} collect = {server, CL, &listeners};
	server->ForEachClientDo(collect);

	auto relay = [&](Listener& l, u8 out_mode, u16 source)
	{
		NET_Packet R;
		R.w_begin(M_NETCOOP_VOICE);
		R.w_u16(speaker->ID()); R.w_u8(out_mode); R.w_u8(loudness); R.w_u16(source);
		R.w_u16(first); R.w_u8(frames); R.w(payload, size);
		server->SendTo(l.client->ID, R, net_flags(FALSE, TRUE, TRUE, TRUE));
		l.sent = true;
	};
	const Fvector& at_speaker = speaker->Position();
	// Into the radio the talker still speaks aloud, at a normal voice.
	const float near_range = voice_range_m[mode == 1 ? _max(loudness, u8(1)) : loudness] + 2.f;
	for (Listener& l : listeners)
		if (l.actor->Position().distance_to(at_speaker) <= near_range) relay(l, 0, speaker->ID());
	if (mode != 1) return;
	auto own = s_server_radio.find(speaker->ID());
	if (own == s_server_radio.end() || !own->second.on || !voice_has_radio(speaker)) return;
	const u16 freq = own->second.freq;
	const float range = voice_radio_range();
	xr_vector<CActor*> receivers;
	for (Listener& l : listeners)
		if (!l.sent && l.actor->Position().distance_to(at_speaker) <= range && voice_radio_tuned(l.actor, freq))
		{
			relay(l, 1, speaker->ID());
			receivers.push_back(l.actor);
		}
	// A receiver's loudspeaker is heard around it.
	for (CActor* receiver : receivers)
		for (Listener& l : listeners)
			if (!l.sent && l.actor->Position().distance_to(receiver->Position()) <= voice_speaker_m)
				relay(l, 2, receiver->ID());
}

void server_voice_forget(u16 actor) { s_server_radio.erase(actor); }
