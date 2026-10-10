// Included inside namespace netcoop in netcoop.cpp, before netcoop_voice.inc.
// The PDA dictaphone and voice messages (owner 2026-10-10, after New Way):
// a recording keeps everything the player hears while it runs - his own
// microphone, players talking nearby (where they stood), walkie-talkie
// voices in his ear and from receivers' speakers (radio voice), and the
// world's sounds (mutants, anomalies, weapons...) as "this sound, here
// around me". Playing it back puts each of them again around the listener.
//
// Recording format (base64 for Lua): "NCR1", u32 duration ms, then events
//   u32 time ms, u8 type:
//     0 voice frame: u8 track, u8 mode, u16 seq, u16 length, bytes
//       (mode: 0 near, 1 radio in the ear, 2 receiver speaker, 3 own microphone)
//     1 track position: u8 track, f32 x, y, z (listener frame: right, up, forward)
//     2 world sound: u8 head, f32 x, y, z, f32 volume, min, max, u8 length, name

static const u32 rec_limit_bytes = 6u << 20;

static void rec_put(xr_vector<u8>& b, const void* p, u32 n)
{
	const u8* s = static_cast<const u8*>(p);
	b.insert(b.end(), s, s + n);
}
template <class T> static void rec_put(xr_vector<u8>& b, T v) { rec_put(b, &v, sizeof(T)); }

static Fvector rec_to_local(const Fvector& world)
{
	Fvector rel, right, local;
	rel.sub(world, Device.vCameraPosition);
	right.crossproduct(Device.vCameraTop, Device.vCameraDirection);
	right.normalize_safe();
	local.set(rel.dotproduct(right), rel.dotproduct(Device.vCameraTop), rel.dotproduct(Device.vCameraDirection));
	return local;
}
static Fvector rec_to_world(const Fvector& local)
{
	Fvector right, world = Device.vCameraPosition;
	right.crossproduct(Device.vCameraTop, Device.vCameraDirection);
	right.normalize_safe();
	world.mad(right, local.x);
	world.mad(Device.vCameraTop, local.y);
	world.mad(Device.vCameraDirection, local.z);
	return world;
}

//----------------------------------------------------------------------
// Base64 (Lua strings from the engine stop at a zero byte)
//----------------------------------------------------------------------
static const char rec_b64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static void rec_encode(const xr_vector<u8>& in, xr_string& out)
{
	out.clear();
	out.reserve((in.size() + 2) / 3 * 4);
	for (size_t i = 0; i < in.size(); i += 3)
	{
		const u32 n = u32(in[i]) << 16 | (i + 1 < in.size() ? u32(in[i + 1]) << 8 : 0) | (i + 2 < in.size() ? in[i + 2] : 0);
		out += rec_b64[n >> 18 & 63];
		out += rec_b64[n >> 12 & 63];
		out += i + 1 < in.size() ? rec_b64[n >> 6 & 63] : '=';
		out += i + 2 < in.size() ? rec_b64[n & 63] : '=';
	}
}
static bool rec_decode(LPCSTR in, xr_vector<u8>& out)
{
	out.clear();
	if (!in) return false;
	u32 acc = 0;
	int bits = 0;
	for (LPCSTR c = in; *c; ++c)
	{
		if (*c == '=') break;
		const char* at = strchr(rec_b64, *c);
		if (!at || !*c) return false;
		acc = acc << 6 | u32(at - rec_b64);
		bits += 6;
		if (bits >= 8) { bits -= 8; out.push_back(u8(acc >> bits & 0xff)); }
		if (out.size() > rec_limit_bytes) return false;
	}
	return true;
}

//----------------------------------------------------------------------
// Recorder
//----------------------------------------------------------------------
struct VoiceRecorder : public IVoiceSink, public ISoundTap
{
	bool on = false;
	u32 start = 0, max_ms = 600000;
	xr_vector<u8> data;
	xr_map<u32, u8> tracks;          // speaker << 2 | mode -> track (0 is the own microphone)
	xr_map<u8, u32> moved;           // track -> last position event
	bool full = false;

	u32 now() const { return Device.dwTimeContinual - start; }
	bool room(u32 n) { if (data.size() + n > rec_limit_bytes || now() > max_ms) full = true; return !full; }

	void frame(u8 track, u8 mode, u16 seq, const u8* bytes, u32 length)
	{
		if (!on || !room(12 + length)) return;
		rec_put<u32>(data, now()); rec_put<u8>(data, 0);
		rec_put<u8>(data, track); rec_put<u8>(data, mode); rec_put<u16>(data, seq); rec_put<u16>(data, u16(length));
		rec_put(data, bytes, length);
	}
	void position(u8 track, const Fvector& world)
	{
		if (!on || !room(18)) return;
		u32& last = moved[track];
		if (last && now() - last < 250) return;
		last = now() ? now() : 1;
		const Fvector local = rec_to_local(world);
		rec_put<u32>(data, now()); rec_put<u8>(data, 1); rec_put<u8>(data, track);
		rec_put<float>(data, local.x); rec_put<float>(data, local.y); rec_put<float>(data, local.z);
	}
	u8 track_of(u16 speaker, u8 mode)
	{
		const u32 key = u32(speaker) << 2 | mode;
		auto it = tracks.find(key);
		if (it != tracks.end()) return it->second;
		if (tracks.size() >= 250) return 255;
		const u8 t = u8(tracks.size() + 1);
		tracks[key] = t;
		return t;
	}

	// own microphone (ISoundVoice::SetRecord)
	void OnVoiceFrame(const u8* bytes, u32 length, u16 seq) override { frame(0, 3, seq, bytes, length); }
	// world sounds (ISoundTap)
	void OnWorldSound(LPCSTR name, const Fvector& local, float volume, float min_distance, float max_distance, bool head) override
	{
		const u32 len = name ? xr_strlen(name) : 0;
		if (!on || !len || len > 200 || !room(36 + len)) return;
		rec_put<u32>(data, now()); rec_put<u8>(data, 2); rec_put<u8>(data, head ? 1 : 0);
		rec_put<float>(data, local.x); rec_put<float>(data, local.y); rec_put<float>(data, local.z);
		rec_put<float>(data, volume); rec_put<float>(data, min_distance); rec_put<float>(data, max_distance);
		rec_put<u8>(data, u8(len)); rec_put(data, name, len);
	}
};
static VoiceRecorder s_rec;

// What the speaker the player hears said (client_on_voice): recorded too.
static void voice_record_heard(u16 speaker, u8 mode, const Fvector* where, u16 seq, const u8* bytes, u32 length)
{
	if (!s_rec.on) return;
	const u8 track = s_rec.track_of(speaker, mode);
	if (track == 255) return;
	if (where) s_rec.position(track, *where);
	s_rec.frame(track, mode, seq, bytes, length);
}

static ISoundVoice* rec_audio() { return ::Sound ? ::Sound->voice() : nullptr; }

bool script_record_start(int max_seconds)
{
	ISoundVoice* voice = rec_audio();
	if (!pure_client() || !voice || s_rec.on) return false;
	s_rec.data.clear(); s_rec.tracks.clear(); s_rec.moved.clear();
	s_rec.full = false;
	s_rec.max_ms = u32(clampr(max_seconds, 1, 600)) * 1000;
	s_rec.start = Device.dwTimeContinual;
	s_rec.on = true;
	rec_put(s_rec.data, "NCR1", 4);
	rec_put<u32>(s_rec.data, 0);
	voice->SetRecord(&s_rec);
	voice->SetSoundTap(&s_rec);
	return true;
}
bool script_record_active() { return s_rec.on && !s_rec.full; }
float script_record_seconds() { return s_rec.on ? float(_min(s_rec.now(), s_rec.max_ms)) / 1000.f : 0.f; }
LPCSTR script_record_stop()
{
	static xr_string out;
	out.clear();
	if (!s_rec.on) return "";
	if (ISoundVoice* voice = rec_audio()) { voice->SetRecord(nullptr); voice->SetSoundTap(nullptr); }
	const u32 duration = _min(s_rec.now(), s_rec.max_ms);
	s_rec.on = false;
	if (s_rec.data.size() < 8) return "";
	CopyMemory(&s_rec.data[4], &duration, 4);
	rec_encode(s_rec.data, out);
	s_rec.data.clear(); s_rec.data.shrink_to_fit();
	return out.c_str();
}

//----------------------------------------------------------------------
// Player
//----------------------------------------------------------------------
struct RecEvent
{
	u32 t;
	u8 type, track, mode, head;
	u16 seq;
	Fvector pos;
	float volume, min_d, max_d;
	u32 offset, length;   // frame bytes / sound name in the blob
};
struct RecPlayer
{
	xr_vector<u8> blob;
	xr_vector<RecEvent> events;
	u32 duration = 0, next = 0, pos_ms = 0, last_tick = 0;
	bool playing = false, paused = false;
	xr_map<u8, IVoicePlayer*> players;
	xr_map<u8, Fvector> where;   // track -> listener-frame position
	xr_vector<ref_sound*> sounds;

	void release()
	{
		ISoundVoice* voice = rec_audio();
		for (auto& it : players) if (voice && it.second) voice->DestroyPlayer(it.second);
		players.clear();
		for (ref_sound* s : sounds) { s->stop(); xr_delete(s); }
		sounds.clear();
	}
	bool parse()
	{
		events.clear();
		if (blob.size() < 8 || memcmp(blob.data(), "NCR1", 4)) return false;
		CopyMemory(&duration, &blob[4], 4);
		size_t p = 8;
		auto need = [&](size_t n) { return p + n <= blob.size(); };
		auto rd = [&](void* dst, size_t n) { CopyMemory(dst, &blob[p], n); p += n; };
		while (need(5))
		{
			RecEvent e = {};
			rd(&e.t, 4); rd(&e.type, 1);
			if (e.type == 0)
			{
				if (!need(6)) return false;
				u16 len; rd(&e.track, 1); rd(&e.mode, 1); rd(&e.seq, 2); rd(&len, 2);
				if (!need(len) || len > VOICE_MAX_PACKET || e.mode > 3) return false;
				e.offset = u32(p); e.length = len; p += len;
			}
			else if (e.type == 1)
			{
				if (!need(13)) return false;
				rd(&e.track, 1); rd(&e.pos, 12);
			}
			else if (e.type == 2)
			{
				if (!need(26)) return false;
				u8 len; rd(&e.head, 1); rd(&e.pos, 12); rd(&e.volume, 4); rd(&e.min_d, 4); rd(&e.max_d, 4); rd(&len, 1);
				if (!need(len) || !len) return false;
				e.offset = u32(p); e.length = len; p += len;
			}
			else return false;
			events.push_back(e);
		}
		return true;
	}
	void seek(u32 ms)
	{
		release();
		where.clear();
		pos_ms = _min(ms, duration);
		next = 0;
		// positions before the point still apply; frames and sounds start there
		while (next < events.size() && events[next].t < pos_ms)
		{
			if (events[next].type == 1) where[events[next].track] = events[next].pos;
			++next;
		}
		last_tick = Device.dwTimeContinual;
	}
	IVoicePlayer* player_for(const RecEvent& e)
	{
		IVoicePlayer*& p = players[e.track];
		ISoundVoice* voice = rec_audio();
		if (!p && voice) p = voice->CreatePlayer();
		if (p)
		{
			// 0 near and 2 a receiver's speaker sound around; 1 radio and 3 own voice in the ear
			p->SetMode(e.mode == 1 || e.mode == 2, e.mode == 0 || e.mode == 2);
			p->SetRange(e.mode == 0 ? 45.f : 12.f);
		}
		return p;
	}
	void sound(const RecEvent& e)
	{
		if (sounds.size() >= 48) return;
		string256 name;
		strncpy_s(name, sizeof(name), (LPCSTR)&blob[e.offset], e.length);
		ref_sound* s = xr_new<ref_sound>();
		s->create(name, st_Effect, sg_SourceType);
		if (!s->_handle()) { xr_delete(s); return; }
		s->play_at_pos(nullptr, e.pos, sm_2D); // head-relative: the same place around the listener
		if (s->_feedback())
		{
			s->_feedback()->set_volume(e.volume);
			s->_feedback()->set_range(e.min_d, e.max_d);
		}
		sounds.push_back(s);
	}
	void update()
	{
		if (!playing) return;
		const u32 t = Device.dwTimeContinual;
		if (!paused) pos_ms += t - last_tick;
		last_tick = t;
		for (auto it = sounds.begin(); it != sounds.end();)
		{
			if (!(*it)->_feedback()) { xr_delete(*it); it = sounds.erase(it); } else ++it;
		}
		for (auto& w : where)
			if (players.count(w.first) && players[w.first]) players[w.first]->SetPosition(rec_to_world(w.second));
		if (paused) return;
		while (next < events.size() && events[next].t <= pos_ms + 60)
		{
			const RecEvent& e = events[next++];
			if (e.type == 0)
			{
				if (IVoicePlayer* p = player_for(e))
				{
					auto w = where.find(e.track);
					if (w != where.end()) p->SetPosition(rec_to_world(w->second));
					p->Push(&blob[e.offset], e.length, e.seq);
				}
			}
			else if (e.type == 1) where[e.track] = e.pos;
			else if (e.type == 2) sound(e);
		}
		if (pos_ms >= duration && next >= events.size())
		{
			playing = false;
			release();
		}
	}
};
static RecPlayer s_play;

// Lua: start playing a recording at a second; returns its length (0: bad data).
float script_play_start(LPCSTR data, float from_seconds)
{
	if (!pure_client() || s_rec.on) return 0.f;
	s_play.playing = false;
	s_play.release();
	if (!rec_decode(data, s_play.blob) || !s_play.parse()) { s_play.blob.clear(); return 0.f; }
	s_play.seek(u32(_max(0.f, from_seconds) * 1000.f));
	s_play.playing = true;
	s_play.paused = false;
	return float(s_play.duration) / 1000.f;
}
void script_play_seek(float seconds)
{
	if (s_play.playing) s_play.seek(u32(_max(0.f, seconds) * 1000.f));
}
void script_play_pause(bool paused) { s_play.paused = paused; }
void script_play_stop() { s_play.playing = false; s_play.release(); }
// seconds played, or -1 when nothing plays
float script_play_pos() { return s_play.playing ? float(_min(s_play.pos_ms, s_play.duration)) / 1000.f : -1.f; }
bool script_play_paused() { return s_play.playing && s_play.paused; }

// Lua: the input language of the keyboard ("RU", "EN", ...), for the PDA's "Раскладка".
LPCSTR script_keyboard_layout()
{
	const LANGID lang = LANGID(LOWORD(GetKeyboardLayout(0)));
	switch (PRIMARYLANGID(lang))
	{
	case LANG_RUSSIAN: return "RU";
	case LANG_UKRAINIAN: return "UA";
	case LANG_BELARUSIAN: return "BY";
	case LANG_ENGLISH: return "EN";
	case LANG_GERMAN: return "DE";
	case LANG_POLISH: return "PL";
	default: return "--";
	}
}

static void voice_record_update()
{
	if (s_rec.on && s_rec.full)
	{
		// limit reached: stop feeding, Lua collects it with record_stop
		if (ISoundVoice* voice = rec_audio()) { voice->SetRecord(nullptr); voice->SetSoundTap(nullptr); }
	}
	s_play.update();
}
static void voice_record_reset()
{
	if (s_rec.on) script_record_stop();
	script_play_stop();
}
