#include "stdafx.h"
#pragma hdrstop

#include <msacm.h>

#include "SoundRender_Core.h"
#include "SoundRender_Source.h"

//	SEEK_SET	0	File beginning
//	SEEK_CUR	1	Current file pointer position
//	SEEK_END	2	End-of-file
int ov_seek_func(void* datasource, s64 offset, int whence)
{
	switch (whence)
	{
	case SEEK_SET: ((IReader*)datasource)->seek((int)offset);
		break;
	case SEEK_CUR: ((IReader*)datasource)->advance((int)offset);
		break;
	case SEEK_END: ((IReader*)datasource)->seek((int)offset + ((IReader*)datasource)->length());
		break;
	}
	return 0;
}

size_t ov_read_func(void* ptr, size_t size, size_t nmemb, void* datasource)
{
	IReader* F = (IReader*)datasource;
	size_t exist_block = _max(0ul, iFloor(F->elapsed() / (float)size));
	size_t read_block = _min(exist_block, nmemb);
	F->r(ptr, (int)(read_block * size));
	return read_block;
}

int ov_close_func(void* datasource)
{
	return 0;
}

long ov_tell_func(void* datasource)
{
	return ((IReader*)datasource)->tell();
}

void CSoundRender_Source::decompress(u32 line, OggVorbis_File* ovf)
{
	VERIFY(ovf);
	// decompression of one cache-line
	u32 line_size = SoundRender->cache.get_linesize();
	char* dest = (char*)SoundRender->cache.get_dataptr(CAT, line);
	u32 buf_offs = (line * line_size) / 2 / m_wformat.nChannels;
	u32 left_file = dwBytesTotal - buf_offs;
	u32 left = (u32)_min(left_file, line_size);

	// seek
	u32 cur_pos = u32(ov_pcm_tell(ovf));
	if (cur_pos != buf_offs)
		ov_pcm_seek(ovf, buf_offs);

	// decompress
	i_decompress_fr(ovf, dest, left);
}

namespace
{
// Sound descriptions (format, length, distances, AI type) by file. LoadWave
// read the whole .ogg (decrypting and unpacking it) for these few numbers:
// script, material and level sounds took seconds of every start (doc 151).
// A file is known by its path and the index's CRC, size and time, so a
// changed sound is read again.
struct SoundInfo
{
	u32 rate;
	u32 channels;
	u32 bytes_total;
	float base_volume, min_dist, max_dist, max_ai_dist;
	u32 game_type;
};

const u32 sound_info_magic = 0x49535a4c; // "LZSI"
const u32 sound_info_version = 1;

struct SoundInfoCache
{
	xrCriticalSection lock;
	xr_unordered_map<shared_str, SoundInfo, std::hash<shared_str>> items;
	bool loaded = false;
	u32 unsaved = 0;

	static bool path(string_path& out)
	{
		if (!FS.path_exist("$app_data_root$"))
			return false;
		FS.update_path(out, "$app_data_root$", "sound_info.bin");
		return true;
	}

	void load_locked()
	{
		loaded = true;
		string_path file;
		if (!path(file))
			return;
		FILE* f = fopen(file, "rb");
		if (!f)
			return;
		xr_vector<u8> raw;
		fseek(f, 0, SEEK_END);
		const long size = ftell(f);
		fseek(f, 0, SEEK_SET);
		if (size > 16)
		{
			raw.resize(size);
			if (fread(raw.data(), 1, raw.size(), f) != raw.size())
				raw.clear();
		}
		fclose(f);
		if (raw.size() < 16)
			return;
		const u32* head = (const u32*)raw.data();
		const u32 payload = u32(raw.size()) - 16;
		if (head[0] != sound_info_magic || head[1] != sound_info_version || crc32(raw.data() + 16, payload) != head[3])
			return;
		IReader R(raw.data() + 16, payload);
		for (u32 n = 0; n < head[2] && !R.eof(); ++n)
		{
			const u16 length = R.r_u16();
			string_path key;
			if (length >= sizeof(key) || R.elapsed() < int(length + sizeof(SoundInfo)))
				break;
			R.r(key, length);
			key[length] = 0;
			SoundInfo info;
			R.r(&info, sizeof(info));
			items.emplace(shared_str(key), info);
		}
	}

	void save_locked()
	{
		unsaved = 0;
		string_path file;
		if (!path(file))
			return;
		CMemoryWriter W;
		for (const auto& item : items)
		{
			W.w_u16(u16(item.first.size()));
			W.w(item.first.c_str(), item.first.size());
			W.w(&item.second, sizeof(item.second));
		}
		const u32 head[4] = {sound_info_magic, sound_info_version, u32(items.size()), crc32(W.pointer(), W.size())};
		string_path temp;
		xr_sprintf(temp, "%s.%u.tmp", file, GetCurrentProcessId());
		FILE* f = fopen(temp, "wb");
		if (!f)
			return;
		const bool written = fwrite(head, sizeof(head), 1, f) == 1 && fwrite(W.pointer(), 1, W.size(), f) == W.size();
		fclose(f);
		if (!written || !MoveFileExA(temp, file, MOVEFILE_REPLACE_EXISTING))
			DeleteFileA(temp);
	}
};

SoundInfoCache& sound_info_cache()
{
	static SoundInfoCache cache;
	return cache;
}

bool sound_info_key(LPCSTR file_name, string_path& key)
{
	const CLocatorAPI::file* desc = FS.exist(file_name);
	if (!desc)
		return false;
	xr_sprintf(key, "%s|%08x|%u|%u", desc->name, desc->crc, desc->size_real, desc->modif);
	return xr_strlen(key) < 0xffff;
}
}

void sound_info_cache_save()
{
	SoundInfoCache& cache = sound_info_cache();
	xrCriticalSectionGuard guard(cache.lock);
	if (cache.loaded && cache.unsaved)
		cache.save_locked();
}

bool CSoundRender_Source::LoadWave(LPCSTR pName)
{
	pname = pName;

	string_path info_key;
	const bool keyed = sound_info_key(pName, info_key);
	if (keyed)
	{
		SoundInfoCache& cache = sound_info_cache();
		xrCriticalSectionGuard guard(cache.lock);
		if (!cache.loaded)
			cache.load_locked();
		const auto found = cache.items.find(shared_str(info_key));
		if (found != cache.items.end())
		{
			const SoundInfo& info = found->second;
			ZeroMemory(&m_wformat, sizeof(WAVEFORMATEX));
			m_wformat.nSamplesPerSec = info.rate;
			m_wformat.wFormatTag = WAVE_FORMAT_PCM;
			m_wformat.nChannels = u16(info.channels);
			m_wformat.wBitsPerSample = 16;
			m_wformat.nBlockAlign = m_wformat.wBitsPerSample / 8 * m_wformat.nChannels;
			m_wformat.nAvgBytesPerSec = m_wformat.nSamplesPerSec * m_wformat.nBlockAlign;
			dwBytesTotal = info.bytes_total;
			fTimeTotal = s_f_def_source_footer + dwBytesTotal / float(m_wformat.nAvgBytesPerSec);
			m_fBaseVolume = info.base_volume;
			m_fMinDist = info.min_dist;
			m_fMaxDist = info.max_dist;
			m_fMaxAIDist = info.max_ai_dist;
			m_uGameType = info.game_type;
			return true;
		}
	}

	// Load file into memory and parse WAV-format
	OggVorbis_File ovf;
	ov_callbacks ovc = {ov_read_func, ov_seek_func, ov_close_func, ov_tell_func};
	IReader* wave = FS.r_open(pname.c_str());
	R_ASSERT3(wave&&wave->length(), "Can't open wave file:", pname.c_str());
	ov_open_callbacks(wave, &ovf,NULL, 0, ovc);

	vorbis_info* ovi = ov_info(&ovf, -1);
	// verify
	R_ASSERT3(ovi, "Invalid source info:", pname.c_str());

	// The OpenAL target plays each source at its own rate; the stream cache
	// line (SoundRender_Core) is sized for up to 48 kHz stereo 16-bit.
	if (ovi->rate < 8000 || ovi->rate > 48000)
	{
		Msg("! Warning: Invalid source rate %d: %s", int(ovi->rate), pname.c_str());
		ov_clear(&ovf);
		FS.r_close(wave);
		return false;
	}

#ifdef DEBUG
    if (ovi->channels == 2)
    {
        Msg("stereo sound source [%s]", pname.c_str());
    }
#endif // #ifdef DEBUG

	ZeroMemory(&m_wformat, sizeof( WAVEFORMATEX ));

	m_wformat.nSamplesPerSec = (ovi->rate); //44100;
	m_wformat.wFormatTag = WAVE_FORMAT_PCM;
	m_wformat.nChannels = u16(ovi->channels);
	m_wformat.wBitsPerSample = 16;

	m_wformat.nBlockAlign = m_wformat.wBitsPerSample / 8 * m_wformat.nChannels;
	m_wformat.nAvgBytesPerSec = m_wformat.nSamplesPerSec * m_wformat.nBlockAlign;

	s64 pcm_total = ov_pcm_total(&ovf, -1);
	dwBytesTotal = u32(pcm_total * m_wformat.nBlockAlign);
	fTimeTotal = s_f_def_source_footer + dwBytesTotal / float(m_wformat.nAvgBytesPerSec);

	vorbis_comment* ovm = ov_comment(&ovf, -1);
	// Ordinary Vorbis tags (TITLE, DATE, etc.) are not X-Ray's binary
	// distance metadata. GAMMA sound packs may contain many such tags and
	// the engine metadata, if present, need not be the first comment.
	for (int i = 0; ovm && i < ovm->comments; ++i)
	{
		const int length = ovm->comment_lengths[i];
		if (!ovm->user_comments[i] || length < 4)
			continue;
		IReader F(ovm->user_comments[i], length);
		u32 vers = F.r_u32();
		if (vers == 0x0001 && length >= 16)
		{
			m_fMinDist = F.r_float();
			m_fMaxDist = F.r_float();
			m_fBaseVolume = 1.0f;
			m_uGameType = F.r_u32();
			m_fMaxAIDist = m_fMaxDist;
			break;
		}
		else if (vers == 0x0002 && length >= 20)
		{
			m_fMinDist = F.r_float();
			m_fMaxDist = F.r_float();
			m_fBaseVolume = F.r_float();
			m_uGameType = F.r_u32();
			m_fMaxAIDist = m_fMaxDist;
			break;
		}
		else if (vers == OGG_COMMENT_VERSION && length >= 24)
		{
			m_fMinDist = F.r_float();
			m_fMaxDist = F.r_float();
			m_fBaseVolume = F.r_float();
			m_uGameType = F.r_u32();
			m_fMaxAIDist = F.r_float();
			break;
		}
	}
	R_ASSERT3((m_fMaxAIDist >= 0.1f) && (m_fMaxDist >= 0.1f), "Invalid max distance.", pname.c_str());

	ov_clear(&ovf);
	FS.r_close(wave);

	if (keyed)
	{
		const SoundInfo info = {m_wformat.nSamplesPerSec, m_wformat.nChannels, dwBytesTotal,
			m_fBaseVolume, m_fMinDist, m_fMaxDist, m_fMaxAIDist, m_uGameType};
		SoundInfoCache& cache = sound_info_cache();
		xrCriticalSectionGuard guard(cache.lock);
		cache.items[shared_str(info_key)] = info;
		if (++cache.unsaved >= 256)
			cache.save_locked();
	}
	return true;
}

void CSoundRender_Source::load(LPCSTR name)
{
	string_path fn, N;
	xr_strcpy(N, name);
	strlwr(N);
	if (strext(N)) *strext(N) = 0;

	fname = N;

	strconcat(sizeof(fn), fn, N, ".ogg");
	if (!FS.exist("$level$", fn))
		FS.update_path(fn, "$game_sounds$", fn);

	if (!FS.exist(fn)){ 
		{
			Msg("! Can't find sound '%s'", name);
			FS.update_path(fn, "$game_sounds$", "$no_sound.ogg");
		}
    }

	if (LoadWave(fn))
		SoundRender->cache.cat_create(CAT, dwBytesTotal);
}

void CSoundRender_Source::unload()
{
	SoundRender->cache.cat_destroy(CAT);
	fTimeTotal = 0.0f;
	dwBytesTotal = 0;
}
