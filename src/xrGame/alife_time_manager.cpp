////////////////////////////////////////////////////////////////////////////
//	Module 		: alife_time_manager.cpp
//	Created 	: 05.01.2003
//  Modified 	: 12.05.2004
//	Author		: Dmitriy Iassenev
//	Description : ALfie time manager class
////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#include "alife_time_manager.h"
#include "date_time.h"

CALifeTimeManager::CALifeTimeManager(LPCSTR section)
{
	init(section);
}

CALifeTimeManager::~CALifeTimeManager()
{
}

void CALifeTimeManager::init(LPCSTR section)
{
	CHECK_OR_EXIT(!netcoop_world::local_world_authority().ready(),
		"Refusing to reset a running persistent world clock; restart through its committed snapshot");
	u32 years, months, days, hours, minutes, seconds;
	sscanf(pSettings->r_string(section, "start_time"), "%u:%u:%u", &hours, &minutes, &seconds);
	sscanf(pSettings->r_string(section, "start_date"), "%u.%u.%u", &days, &months, &years);
	m_start_game_time = generate_time(years, months, days, hours, minutes, seconds);
	m_time_factor = pSettings->r_float(section, "time_factor");
	m_normal_time_factor = pSettings->r_float(section, "normal_time_factor");
	m_game_time = m_start_game_time;
	m_start_time = Device.dwTimeGlobal;
	m_world_clock.reset();
	const auto& authority = netcoop_world::local_world_authority();
	if (authority.active())
	{
		CHECK_OR_EXIT(std::isfinite(m_time_factor) && m_time_factor > 0 &&
			m_time_factor <= netcoop_world::max_time_scale, "Invalid persistent world time factor");
		m_world_clock.reset(new netcoop_world::ALifeWorldClock(authority.identity(), m_game_time, m_time_factor));
	}
}

void CALifeTimeManager::save(IWriter& memory_stream)
{
	netcoop_world::WorldStateSnapshot checkpoint{};
	if (m_world_clock)
	{
		checkpoint = m_world_clock->checkpoint();
		m_game_time = static_cast<ALife::_TIME_ID>(checkpoint.clock.world_ms);
		m_time_factor = static_cast<float>(checkpoint.clock.time_scale);
	}
	else m_game_time = game_time();
	m_start_time = Device.dwTimeGlobal;
	memory_stream.open_chunk(GAME_TIME_CHUNK_DATA);
	memory_stream.w(&m_game_time, sizeof(m_game_time));
	memory_stream.w_float(m_time_factor);
	memory_stream.w_float(m_normal_time_factor);
	// Optional trailer in the existing time chunk: old saves stay readable,
	// and older engines still read the original 16-byte calendar prefix.
	if (m_world_clock)
	{
		memory_stream.w_u32(0x31435a4c); // LZC1
		memory_stream.w_u32(checkpoint.schema);
		memory_stream.w_u64(checkpoint.clock.world_id);
		memory_stream.w_u64(checkpoint.world_seed);
		memory_stream.w_u64(checkpoint.clock.authority_epoch);
		memory_stream.w_u64(checkpoint.clock.sequence);
		memory_stream.w_u64(checkpoint.state_revision);
	}
	memory_stream.close_chunk();
};

void CALifeTimeManager::load(IReader& file_stream)
{
	CHECK_OR_EXIT(!netcoop_world::local_world_authority().ready(),
		"Refusing live clock rollback; persistent world recovery requires a fresh authority epoch");
	const u32 chunk_size = file_stream.find_chunk(GAME_TIME_CHUNK_DATA);
	CHECK_OR_EXIT(chunk_size == 16 || chunk_size == 64, "Invalid ALife time chunk; recovery required");
	file_stream.r(&m_game_time, sizeof(m_game_time));
	m_time_factor = file_stream.r_float();
	m_normal_time_factor = file_stream.r_float();
	m_start_time = Device.dwTimeGlobal;
	const auto& authority = netcoop_world::local_world_authority();
	if (!authority.active()) { m_world_clock.reset(); return; }
	CHECK_OR_EXIT(std::isfinite(m_time_factor) && m_time_factor > 0 &&
		m_time_factor <= netcoop_world::max_time_scale &&
		double(m_game_time) <= netcoop_world::max_world_ms, "Invalid saved world clock");
	u64 revision = 1;
	if (chunk_size == 64)
	{
		netcoop_world::WorldStateSnapshot checkpoint{};
		CHECK_OR_EXIT(file_stream.r_u32() == 0x31435a4c, "Invalid world clock trailer");
		checkpoint.schema = file_stream.r_u32();
		checkpoint.clock.world_id = file_stream.r_u64();
		checkpoint.world_seed = file_stream.r_u64();
		checkpoint.clock.authority_epoch = file_stream.r_u64();
		checkpoint.clock.sequence = file_stream.r_u64();
		checkpoint.state_revision = file_stream.r_u64();
		checkpoint.clock.world_ms = double(m_game_time);
		checkpoint.clock.time_scale = m_time_factor;
		try { netcoop_world::ALifeWorldClock::validate_checkpoint(checkpoint, authority.identity()); }
		catch (const std::exception& error) { CHECK_OR_EXIT(false, error.what()); }
		revision = checkpoint.state_revision;
	}
	else Msg("[Lost Zone][world] adopting legacy ALife calendar into persistent clock");
	m_world_clock.reset(new netcoop_world::ALifeWorldClock(authority.identity(), m_game_time, m_time_factor, revision));
};

ALife::_TIME_ID CALifeTimeManager::game_time() const
{
	if (m_world_clock) return m_world_clock->now();
	return m_game_time + ALife::_TIME_ID(m_time_factor * float(Device.dwTimeGlobal - m_start_time));
}

float CALifeTimeManager::time_factor() const
{
	return m_world_clock ? m_world_clock->scale() : m_time_factor;
}

void CALifeTimeManager::set_time_factor(float factor)
{
	if (m_world_clock)
	{
		// Zero needs a world-wide simulation barrier, not a calendar-only
		// stop while physics and combat keep running. W3 will own that API.
		if (!std::isfinite(factor) || factor <= 0 || factor > netcoop_world::max_time_scale)
		{
			Msg("! [Lost Zone][world] rejected invalid/paused time factor %f", factor);
			return;
		}
		m_world_clock->set_scale(factor);
		return;
	}
	m_game_time = game_time();
	m_start_time = Device.dwTimeGlobal;
	m_time_factor = factor;
}

void CALifeTimeManager::change_game_time(u32 value)
{
	if (m_world_clock)
	{
		Msg("! [Lost Zone][world] rejected scripted calendar jump (%u ms); world catch-up is required", value);
		return;
	}
	m_game_time += value;
}

bool CALifeTimeManager::export_world_state(netcoop_world::WorldStateSnapshot& snapshot)
{
	if (!m_world_clock) return false;
	snapshot = m_world_clock->checkpoint();
	return true;
}
