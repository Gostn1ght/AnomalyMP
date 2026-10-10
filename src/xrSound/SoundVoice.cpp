#include "stdafx.h"
#include "SoundVoice.h"
#include <AL/al.h>
#include <AL/alc.h>
#include "opus.h"
#include <speex/speex_preprocess.h>
#include "SoundRender_Core.h"

float psVoiceMicGain = 1.f;
float psVoiceVolume = 1.f;
float psVoiceRadioVolume = 0.9f;
int psVoiceAGC = 1;
int psVoiceDenoise = 1;
int psVoiceActivation = 0;

namespace
{
constexpr u32 OPUS_BITRATE = 24000;
constexpr float PI_F = 3.14159265358979f;

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// Two-pole filter (RBJ cookbook) for the radio band.
struct Biquad
{
	float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z1 = 0, z2 = 0;
	void set(bool highpass, float freq, float q)
	{
		const float w = 2.f * PI_F * freq / float(VOICE_SAMPLE_RATE);
		const float alpha = sinf(w) / (2.f * q), c = cosf(w), a0 = 1.f + alpha;
		if (highpass) { b0 = (1.f + c) / 2.f; b1 = -(1.f + c); b2 = (1.f + c) / 2.f; }
		else { b0 = (1.f - c) / 2.f; b1 = 1.f - c; b2 = (1.f - c) / 2.f; }
		a1 = -2.f * c; a2 = 1.f - alpha;
		b0 /= a0; b1 /= a0; b2 /= a0; a1 /= a0; a2 /= a0;
	}
	float run(float x)
	{
		const float y = b0 * x + z1;
		z1 = b1 * x - a1 * y + z2;
		z2 = b2 * x - a2 * y;
		return y;
	}
};

u32 noise_state = 0x9e3779b9u;
float noise()
{
	noise_state ^= noise_state << 13; noise_state ^= noise_state >> 17; noise_state ^= noise_state << 5;
	return float(noise_state & 0xffff) / 32768.f - 1.f;
}
} // namespace

//----------------------------------------------------------------------
// Playback of one speaker
//----------------------------------------------------------------------
class CVoicePlayer : public IVoicePlayer
{
	static constexpr u32 NUM_BUFFERS = 12;
	static constexpr u32 PREBUFFER = 2 * VOICE_FRAME_SAMPLES;   // 80 ms against network jitter
	static constexpr u32 MAX_QUEUE = 25 * VOICE_FRAME_SAMPLES;  // 1 s
	static constexpr u32 SILENCE_MS = 260;                       // end of a transmission

	ALuint m_source = 0;
	ALuint m_buffers[NUM_BUFFERS] = {};
	xr_deque<ALuint> m_free;
	OpusDecoder* m_decoder = nullptr;
	xr_deque<s16> m_pcm;
	bool m_started = false, m_have_seq = false, m_talking = false;
	u16 m_next_seq = 0;
	u32 m_last_packet = 0;
	bool m_radio = false, m_positional = true;
	float m_range = 15.f, m_muffle = 0.f, m_lp = 0.f, m_loudness = 0.f;
	Fvector m_pos{0, 0, 0};
	Biquad m_hp, m_lowp;

	void create_al()
	{
		alGetError();
		alGenSources(1, &m_source);
		alGenBuffers(NUM_BUFFERS, m_buffers);
		if (alGetError() != AL_NO_ERROR) { m_source = 0; return; }
		m_free.clear();
		for (ALuint b : m_buffers) m_free.push_back(b);
		alSourcei(m_source, AL_LOOPING, AL_FALSE);
		alSourcef(m_source, AL_ROLLOFF_FACTOR, 0.f); // the game computes the distance fade
		alSourcef(m_source, AL_GAIN, 1.f);
		apply_mode();
	}
	void destroy_al()
	{
		if (m_source && alIsSource(m_source))
		{
			alSourceStop(m_source);
			alSourcei(m_source, AL_BUFFER, 0);
			alDeleteSources(1, &m_source);
			alDeleteBuffers(NUM_BUFFERS, m_buffers);
		}
		m_source = 0;
		m_free.clear();
	}
	void apply_mode()
	{
		if (!m_source) return;
		alSourcei(m_source, AL_SOURCE_RELATIVE, m_positional ? AL_FALSE : AL_TRUE);
		if (m_positional) alSource3f(m_source, AL_POSITION, m_pos.x, m_pos.y, -m_pos.z);
		else alSource3f(m_source, AL_POSITION, 0.f, 0.f, 0.f);
	}

	// Squelch: a short burst of filtered noise; the end adds a "roger" tone.
	void squelch(bool end)
	{
		const u32 noise_len = VOICE_SAMPLE_RATE * (end ? 120 : 60) / 1000;
		for (u32 i = 0; i < noise_len; ++i)
		{
			const float env = 1.f - float(i) / float(noise_len);
			m_pcm.push_back(s16(clampf(noise() * 0.22f * env, -1.f, 1.f) * 32767.f));
		}
		if (end)
		{
			const u32 tone = VOICE_SAMPLE_RATE * 70 / 1000;
			for (u32 i = 0; i < tone; ++i)
				m_pcm.push_back(s16(sinf(2.f * PI_F * 1600.f * float(i) / float(VOICE_SAMPLE_RATE)) * 0.12f * 32767.f));
		}
	}

	void process(s16* pcm, int count)
	{
		const float muffle_coef = 1.f - clampf(m_muffle, 0.f, 0.95f); // one-pole low-pass for walls
		float peak = 0.f;
		for (int i = 0; i < count; ++i)
		{
			float x = float(pcm[i]) / 32768.f;
			if (m_radio)
			{
				x = m_lowp.run(m_hp.run(x));
				x = tanhf(x * 3.2f) / tanhf(3.2f);                // overdrive of a small speaker
				x += noise() * 0.018f;                             // hiss of the channel
				x = floorf(x * 512.f) / 512.f;                     // narrow, slightly crushed
			}
			if (m_muffle > 0.01f)
			{
				m_lp += (x - m_lp) * muffle_coef;
				x = m_lp;
			}
			peak = _max(peak, fabsf(x));
			pcm[i] = s16(clampf(x, -1.f, 1.f) * 32767.f);
		}
		m_loudness = _max(peak, m_loudness * 0.85f);
	}

	void decode(const u8* data, u32 length, bool fec)
	{
		s16 pcm[VOICE_FRAME_SAMPLES * 2];
		const int n = opus_decode(m_decoder, data, opus_int32(length), pcm, VOICE_FRAME_SAMPLES, fec ? 1 : 0);
		if (n <= 0) return;
		process(pcm, n);
		for (int i = 0; i < n; ++i) m_pcm.push_back(pcm[i]);
	}

public:
	CVoicePlayer()
	{
		int error = 0;
		m_decoder = opus_decoder_create(VOICE_SAMPLE_RATE, 1, &error);
		if (error != OPUS_OK) m_decoder = nullptr;
		m_hp.set(true, 320.f, 0.707f);
		m_lowp.set(false, 3100.f, 0.9f);
		create_al();
	}
	~CVoicePlayer() override
	{
		destroy_al();
		if (m_decoder) opus_decoder_destroy(m_decoder);
	}

	void Push(const u8* data, u32 length, u16 seq) override
	{
		if (!m_decoder || !data || !length || length > VOICE_MAX_PACKET) return;
		const u32 now = GetTickCount();
		const bool new_talk = !m_talking || now - m_last_packet > SILENCE_MS;
		if (new_talk)
		{
			opus_decoder_ctl(m_decoder, OPUS_RESET_STATE);
			m_have_seq = false;
			if (m_radio) squelch(false);
		}
		m_talking = true;
		m_last_packet = now;
		if (m_have_seq)
		{
			const u16 gap = u16(seq - m_next_seq);
			if (gap >= 0x8000) return;                 // late duplicate
			if (gap == 1) decode(data, length, true);  // one lost: rebuilt from this packet's FEC
			else if (gap > 1 && gap <= 3)
				for (u16 i = 0; i < gap; ++i) decode(nullptr, 0, false); // concealment
		}
		decode(data, length, false);
		m_have_seq = true;
		m_next_seq = u16(seq + 1);
		while (m_pcm.size() > MAX_QUEUE) m_pcm.pop_front();
	}

	void SetPosition(const Fvector& pos) override
	{
		m_pos = pos;
		if (m_source && m_positional) alSource3f(m_source, AL_POSITION, pos.x, pos.y, -pos.z);
	}
	void SetMode(bool radio, bool positional) override
	{
		if (radio == m_radio && positional == m_positional) return;
		m_radio = radio; m_positional = positional;
		apply_mode();
	}
	void SetRange(float max_distance) override { m_range = clampf(max_distance, 1.f, 2000.f); }
	void SetMuffle(float amount) override { m_muffle = clampf(amount, 0.f, 1.f); }
	bool IsActive() const override { return m_talking || !m_pcm.empty(); }
	float Loudness() const override { return m_talking ? m_loudness : 0.f; }

	void Update()
	{
		if (!m_source || !alIsSource(m_source)) { destroy_al(); create_al(); if (!m_source) return; }
		const u32 now = GetTickCount();
		if (m_talking && now - m_last_packet > SILENCE_MS)
		{
			m_talking = false;
			if (m_radio) squelch(true);
		}
		ALint processed = 0, state = 0;
		alGetSourcei(m_source, AL_BUFFERS_PROCESSED, &processed);
		alGetSourcei(m_source, AL_SOURCE_STATE, &state);
		while (processed-- > 0)
		{
			ALuint b = 0;
			alSourceUnqueueBuffers(m_source, 1, &b);
			m_free.push_back(b);
		}
		if (!m_started && m_pcm.size() < PREBUFFER && m_talking) return;
		while (!m_pcm.empty() && !m_free.empty())
		{
			s16 chunk[VOICE_FRAME_SAMPLES];
			u32 n = 0;
			while (n < VOICE_FRAME_SAMPLES && !m_pcm.empty()) { chunk[n++] = m_pcm.front(); m_pcm.pop_front(); }
			const ALuint b = m_free.front();
			m_free.pop_front();
			alBufferData(b, AL_FORMAT_MONO16, chunk, ALsizei(n * sizeof(s16)), VOICE_SAMPLE_RATE);
			alSourceQueueBuffers(m_source, 1, &b);
			m_started = true;
		}
		// Catch up quietly when the queue grows (network bursts).
		alSourcef(m_source, AL_PITCH, m_pcm.size() > 10 * VOICE_FRAME_SAMPLES ? 1.04f : 1.f);
		float volume = (m_radio ? psVoiceRadioVolume : psVoiceVolume) * psSoundVFactor;
		if (m_positional && SoundRender)
		{
			// Full near the speaker, fading to silence at the range.
			const float d = SoundRender->listener_position().distance_to(m_pos);
			const float full = m_range * 0.25f;
			volume *= d <= full ? 1.f : (d >= m_range ? 0.f : powf(1.f - (d - full) / (m_range - full), 1.6f));
			volume *= 1.f - 0.45f * m_muffle;
		}
		alSourcef(m_source, AL_GAIN, clampf(volume, 0.f, 2.f));
		if (state != AL_PLAYING && m_free.size() < NUM_BUFFERS) alSourcePlay(m_source); // something is queued
		if (m_pcm.empty() && !m_talking && state != AL_PLAYING) m_started = false;
	}
};

//----------------------------------------------------------------------
// Microphone
//----------------------------------------------------------------------
class CSoundVoice : public ISoundVoice
{
	ALCdevice* m_capture = nullptr;
	IVoiceSink* m_sink = nullptr;
	OpusEncoder* m_encoder = nullptr;
	SpeexPreprocessState* m_pre = nullptr;
	bool m_ptt = false, m_open = false, m_sending = false;
	u16 m_seq = 0;
	float m_level = 0.f;
	u32 m_hang = 0; // frames sent after voice activity stops (no clipped word ends)
	xr_vector<CVoicePlayer*> m_players;

	void configure_pre()
	{
		if (!m_pre) return;
		int on = psVoiceDenoise ? 1 : 0, agc = psVoiceAGC ? 1 : 0, vad = 1;
		speex_preprocess_ctl(m_pre, SPEEX_PREPROCESS_SET_DENOISE, &on);
		speex_preprocess_ctl(m_pre, SPEEX_PREPROCESS_SET_AGC, &agc);
		speex_preprocess_ctl(m_pre, SPEEX_PREPROCESS_SET_VAD, &vad);
		int suppress = -30;
		speex_preprocess_ctl(m_pre, SPEEX_PREPROCESS_SET_NOISE_SUPPRESS, &suppress);
		float level = 24000.f;
		speex_preprocess_ctl(m_pre, SPEEX_PREPROCESS_SET_AGC_LEVEL, &level);
	}

public:
	~CSoundVoice() override
	{
		StopCapture();
		for (CVoicePlayer* p : m_players) xr_delete(p);
		m_players.clear();
	}

	bool StartCapture(IVoiceSink* sink) override
	{
		StopCapture();
		m_sink = sink;
		int error = 0;
		m_encoder = opus_encoder_create(VOICE_SAMPLE_RATE, 1, OPUS_APPLICATION_VOIP, &error);
		if (error != OPUS_OK) { m_encoder = nullptr; return false; }
		opus_encoder_ctl(m_encoder, OPUS_SET_BITRATE(OPUS_BITRATE));
		opus_encoder_ctl(m_encoder, OPUS_SET_SIGNAL(OPUS_SIGNAL_VOICE));
		opus_encoder_ctl(m_encoder, OPUS_SET_COMPLEXITY(8));
		opus_encoder_ctl(m_encoder, OPUS_SET_INBAND_FEC(1));
		opus_encoder_ctl(m_encoder, OPUS_SET_PACKET_LOSS_PERC(10));
		m_pre = speex_preprocess_state_init(VOICE_FRAME_SAMPLES, VOICE_SAMPLE_RATE);
		configure_pre();
		alcGetError(nullptr);
		m_capture = alcCaptureOpenDevice(nullptr, VOICE_SAMPLE_RATE, AL_FORMAT_MONO16, VOICE_FRAME_SAMPLES * 8);
		if (!m_capture) { Msg("! [voice] no microphone"); StopCapture(); return false; }
		alcCaptureStart(m_capture);
		Msg("[voice] microphone opened: %s", alcGetString(m_capture, ALC_CAPTURE_DEVICE_SPECIFIER));
		return true;
	}

	void StopCapture() override
	{
		if (m_capture) { alcCaptureStop(m_capture); alcCaptureCloseDevice(m_capture); m_capture = nullptr; }
		if (m_encoder) { opus_encoder_destroy(m_encoder); m_encoder = nullptr; }
		if (m_pre) { speex_preprocess_state_destroy(m_pre); m_pre = nullptr; }
		m_sink = nullptr;
		m_sending = false;
	}

	bool Capturing() const override { return m_capture != nullptr; }
	void SetTransmit(bool on) override { m_ptt = on; }
	void SetOpenMic(bool on) override { m_open = on; }
	bool Transmitting() const override { return m_sending; }
	float InputLevel() const override { return m_level; }

	IVoicePlayer* CreatePlayer() override
	{
		CVoicePlayer* p = xr_new<CVoicePlayer>();
		m_players.push_back(p);
		return p;
	}
	void DestroyPlayer(IVoicePlayer* player) override
	{
		auto it = std::find(m_players.begin(), m_players.end(), static_cast<CVoicePlayer*>(player));
		if (it == m_players.end()) return;
		xr_delete(*it);
		m_players.erase(it);
	}

	void Update() override
	{
		for (CVoicePlayer* p : m_players) p->Update();
		if (!m_capture || !m_encoder) return;
		static int agc = -1, denoise = -1;
		if (agc != psVoiceAGC || denoise != psVoiceDenoise) { agc = psVoiceAGC; denoise = psVoiceDenoise; configure_pre(); }
		ALCint available = 0;
		alcGetIntegerv(m_capture, ALC_CAPTURE_SAMPLES, 1, &available);
		while (available >= ALCint(VOICE_FRAME_SAMPLES))
		{
			s16 pcm[VOICE_FRAME_SAMPLES];
			alcCaptureSamples(m_capture, pcm, VOICE_FRAME_SAMPLES);
			available -= VOICE_FRAME_SAMPLES;
			if (!psVoiceAGC && psVoiceMicGain != 1.f)
				for (s16& s : pcm) s = s16(clampf(float(s) * psVoiceMicGain, -32768.f, 32767.f));
			const bool voice = m_pre ? speex_preprocess_run(m_pre, pcm) != 0 : true;
			float peak = 0.f;
			for (s16 s : pcm) peak = _max(peak, fabsf(float(s)) / 32768.f);
			m_level = _max(peak, m_level * 0.8f);
			bool send = m_ptt;
			if ((m_open || psVoiceActivation) && !m_ptt)
			{
				if (voice) m_hang = 8; // keep 320 ms after the last voiced frame
				send = m_hang > 0;
				if (m_hang) --m_hang;
			}
			m_sending = send;
			if (!send || !m_sink) continue;
			u8 packet[VOICE_MAX_PACKET];
			const opus_int32 bytes = opus_encode(m_encoder, pcm, VOICE_FRAME_SAMPLES, packet, VOICE_MAX_PACKET);
			if (bytes > 0) m_sink->OnVoiceFrame(packet, u32(bytes), m_seq++);
		}
	}
};

ISoundVoice* create_sound_voice() { return xr_new<CSoundVoice>(); }
