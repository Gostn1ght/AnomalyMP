#pragma once
// Voice chat audio (ported from NEAREST-STAGE's SoundVoiceChat and extended
// for Lost Zone): microphone capture through OpenAL, noise suppression,
// automatic gain and voice detection (SpeexDSP), Opus coding with in-band
// FEC and loss concealment, and playback streams: positional speech that
// fades with distance and is muffled behind walls, and walkie-talkie
// reception with a radio voice (band-pass, overdrive, hiss, squelch at the
// start and the end of a transmission). Who hears whom is decided in xrGame
// (netcoop voice); this module only makes and plays the sound.

// Frames: 24 kHz mono, 960 samples (40 ms), one Opus packet each.
static constexpr u32 VOICE_SAMPLE_RATE = 24000;
static constexpr u32 VOICE_FRAME_SAMPLES = 960;
static constexpr u32 VOICE_MAX_PACKET = 400;

// Settings (console: voice_*), shared by capture and playback.
extern float psVoiceMicGain;     // manual microphone gain when AGC is off
extern float psVoiceVolume;      // other players' speech
extern float psVoiceRadioVolume; // radio reception
extern int psVoiceAGC;           // automatic gain control
extern int psVoiceDenoise;       // noise suppression
extern int psVoiceActivation;    // 1: talk by voice activity instead of push-to-talk

// The microphone's encoded frames go to the game's network sender.
class IVoiceSink
{
public:
	virtual ~IVoiceSink() {}
	virtual void OnVoiceFrame(const u8* data, u32 length, u16 seq) = 0;
};

// One speaker heard by this listener.
class IVoicePlayer
{
public:
	virtual ~IVoicePlayer() {}
	virtual void Push(const u8* data, u32 length, u16 seq) = 0;
	virtual void SetPosition(const Fvector& pos) = 0;
	// radio: walkie-talkie voice; positional: a source in the world (else in the ear)
	virtual void SetMode(bool radio, bool positional) = 0;
	virtual void SetRange(float max_distance) = 0;
	virtual void SetMuffle(float amount) = 0; // 0 clear .. 1 behind thick walls
	virtual bool IsActive() const = 0;
	virtual float Loudness() const = 0;        // 0..1, for the speaking indicator
};

class ISoundVoice
{
public:
	virtual ~ISoundVoice() {}
	virtual bool StartCapture(IVoiceSink* sink) = 0; // false: no microphone
	virtual void StopCapture() = 0;
	virtual bool Capturing() const = 0;
	virtual void SetTransmit(bool on) = 0;           // push-to-talk held
	virtual bool Transmitting() const = 0;           // sending frames now
	virtual float InputLevel() const = 0;            // microphone level 0..1
	virtual IVoicePlayer* CreatePlayer() = 0;
	virtual void DestroyPlayer(IVoicePlayer* player) = 0;
	virtual void Update() = 0;
};

ISoundVoice* create_sound_voice();
