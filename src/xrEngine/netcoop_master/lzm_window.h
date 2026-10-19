// The master's own window (owner 2026-10-19: "a full application with its
// own look"): Win32, dark like the location panel. Calendar, weather,
// emission and psi storm cards, the maps of the plan with their leases, the
// players (master sessions + the rosters the maps write), the journal and the
// operator console, with buttons for the usual commands.
#pragma once
#include "lzm_service.h"

namespace lzm
{
struct WindowOptions
{
    Service::Options service;
    std::wstring roster_folder;  // <root>\appdata\server\netcoop_cluster
    std::wstring log_folder;     // opened by "Журналы"
    std::wstring selftest;       // CI: result JSON, then close
};

int run_window(const WindowOptions& options);
// A journal line for the open window (no-op without one).
void window_journal(const std::string& line);

// Calendar text of engine game milliseconds since 01.01.0001 (GAMMA: 26.10.2018 08:00).
std::string calendar_text(double world_ms);
} // namespace lzm
