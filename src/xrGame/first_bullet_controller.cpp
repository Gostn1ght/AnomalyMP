#include "stdafx.h"
#include "first_bullet_controller.h"
#include "level.h"

first_bullet_controller::first_bullet_controller()
{
	m_fire_dispertion = 0;
}

void first_bullet_controller::load(shared_str const& section)
{
	if (pSettings->r_bool(section, "use_first_bullet"))
		m_fire_dispertion = pSettings->r_float(section, "first_bullet_dispertion");
}

