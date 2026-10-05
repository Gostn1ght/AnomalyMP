////////////////////////////////////////////////////////////////////////////
//	Module 		: alife_time_manager_inline.h
//	Created 	: 05.01.2003
//  Modified 	: 12.05.2004
//	Author		: Dmitriy Iassenev
//	Description : ALife time manager class inline functions
////////////////////////////////////////////////////////////////////////////

#pragma once

IC ALife::_TIME_ID CALifeTimeManager::start_game_time() const
{
	return m_start_game_time;
}

IC float CALifeTimeManager::normal_time_factor() const
{
	return (m_normal_time_factor);
}
