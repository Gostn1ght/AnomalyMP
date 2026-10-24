# The world master in the engine, in C++ (owner 2026-10-19)

Owner: "the master server must be a full application with its own look" and
then "the master must be part of the game engine itself, in C++". A Python
window (tkinter) was started and dropped the same hour.

## What it is

`LostZoneServerDX11.exe -netcoop_master` is the master. `x_ray.cpp` WinMain
hands the command line to `netcoop_master_entry()` before any engine
subsystem starts (no xrCore, no level, no render). Sources:
`src/xrEngine/netcoop_master/lzm_*.cpp` (compiled without the PCH, `/utf-8`).

| Python (backend/lostzone) | C++ |
| --- | --- |
| store.py (schema 6, migrations, lock file, idempotent commands, journal, snapshot) | lzm_store |
| world.py (calendar, frozen while down, leases/fences, world state, scale) | lzm_world |
| scheduler.py, timelines.py, director.py (+ Python's Mersenne Twister) | lzm_timelines |
| ownership.py, transfers.py, player_saves.py, native_save.py | lzm_ownership, lzm_transfers, lzm_player_saves |
| http.py (credentials, runtime principal, world binding, rate limit, routes) | lzm_service, lzm_http |
| console.py (+ `psi`) | lzm_console |
| gateway.py (players' TCP entry) | lzm_service (handle_entry) |
| __main__.py init / writer-config / bridge-config / add-location | lzm_config, lzm_main |
| — | lzm_window: the master window |

The same `hoster\master\runtime\config.json`, the same `world.sqlite` and the
same HTTP contract on 127.0.0.1:38477 (and the entry on TCP 1267): the maps'
bridge and writers are unchanged, an existing world opens as it is (its
epoch advances, the calendar continues). SQLite is `sqlite3.dll` beside the
server executable (the DX11 package copies the one of the build's Python).

Not ported (no map calls them; admin-only in the Python service): offline
simulation (routes, encounters, hazards, scavenging, planner), quests,
trade, `/v1/location-bootstrap` captures, `player-migration`. A world that
holds quest/route/offline rows or other pending event types is refused with
the counts in the window, so nothing is silently dropped.

## The window

Header with the state (works / restores the world / stopped, WorldID, epoch,
uptime), five cards (Zone calendar, weather, emission, psi storm, world:
maps online and players), buttons (emission now, psi storm now, change
weather, time speed ×1..×50, journals, stop/start), tabs Locations (plan +
leases: online / not answering / off, address, players), Players (master
sessions merged with the maps' rosters: character, map, faction, role, ping,
in transit), Journal (coloured), Console (the operator commands). Closing
asks before stopping the master.

## Hoster

`netcoop_master_control.ps1`: when `dedicated\LostZoneServerDX11.exe` and
`dedicated\sqlite3.dll` exist, init/writer-config/bridge-config run through
the engine and Start-Master opens the master window
(`-netcoop_master window --config runtime\config.json --initialized
--cluster <plan> --gateway-port <entry> --log-file <master_stamp.log>`);
`-InitMaster` prepares the files for a start from the exe alone. The panel
finds the engine master among its processes, its "master console" button
brings the window to the front, its console tab tails the same journal.
`Start Master.cmd` opens the engine master directly.

## Verification

`.github/workflows/lostzone-master-cpp.yml` (branch master-cpp): the sources
compiled alone (MultiByte, like the engine) into a console test program,
then `scripts/check-master-cpp-parity.py`: the Python service and the C++
master get one configuration (director off) and the same 83 requests the
maps send (claims, renewals, entities, items, stash policy, native save
upload/finish/read, disconnect/resume, admission ABSENT/ACTIVE/ELSEWHERE,
transfer prepare/claim/read/commit, death, corpse cleanup, recovery, the
console, error contracts); answers are compared after normalising random IDs
and clock readings, canonical JSON through the journal's payload hashes. The
C++ master then reopens its DB (epoch 2) and the Python service reads the DB
the C++ master wrote. Last, the window opens, serves, answers `status`,
refuses `quit` and closes (`--selftest`).
