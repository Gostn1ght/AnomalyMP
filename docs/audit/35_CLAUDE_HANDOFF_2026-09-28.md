# 35 — Claude handoff, 2026-09-28

Branch `all-in-one-vs2022-wpo`, CI only (GitHub Actions `MSBuild`, job
`build-job (DX11)`; the `M1 Windows Build` workflow always fails on the
deprecated upload-artifact v3 and does not matter).

Install a build: download `DX11_dedicated_client` and `DX11_pdb`, copy the two
exes, and copy the PDB as **all four** of `bin/AnomalyDX11.pdb`,
`bin/AnomalyGammaNetClientDX11.pdb`, `dedicated/AnomalyDX11.pdb`,
`dedicated/AnomalyGammaNetServerDX11.pdb`. The exe names `AnomalyDX11.pdb` in its
debug directory; a stale file with that name gives garbage stacks.

## What changed since doc 33

Server (dedicated, netcoop):
- Remote client packets are queued and handled on the main thread
  (`xrServer::netcoop_process_packets`). They used to run on the DirectPlay
  thread and call Lua concurrently (player spawn -> ALife register -> Lua).
- Script binders are created on the dedicated server for every object except
  player Actors (`GameObject.cpp script_binders_enabled`). Before this no GAMMA
  NPC/smart/monster script ran on the server.
- db.actor / `Actor()` / the level task list point at the nearest player for a
  whole NPC or monster update and its events (`netcoop::ServerActorScope` in
  stalker and CCustomMonster shedule_Update/UpdateCL/OnEvent), binder
  lifecycle, dialogues and task updates. Binds nest.
- Lua errors and result cast failures are logged, not fatal, in every netcoop
  process (`script_engine.cpp netcoop_server_tolerant`).
- The story Actor (id 0) stays the ALife actor; player Actors no longer
  replace it (dangling `alife():actor()` after a disconnect).
- Per-player tasks: one `CGameTaskManager` per player Actor (ALife registry
  under its id), GAMMA `task_manager` per player, a task in progress for one
  player cannot be given to another, task list sent to the owner every 0.5 s
  when it changes (`M_NETCOOP_TASKS`). PDA news of a player's Actor are
  forwarded to that client (`M_NETCOOP_NEWS`).
- Time events (`CreateTimeEvent`) are processed on the server
  (overlay `server_event_queue`); `on_game_load` is sent once a player is
  present; death_manager drop settings are initialised; `IsActor` defined.
- GAMMA weather manager runs on the server; the preset is broadcast
  (`netcoop_broadcast("weather", ...)`, message `M_NETCOOP_SCRIPT`).

Client:
- `_g.start_game_callback` (-> every script's `on_game_start`) now runs while
  the level loads (`Level_load.cpp`). It only ran when an ALife simulator was
  created, i.e. never on a client: item animations, HUD, input, PDA and our own
  client hooks were not registered.
- The owning client activates/hides its own slots and HUD items and sends every
  state change to the server, which relays it (`Inventory.cpp`, `HudItem.cpp`,
  `Weapon.cpp`). The server copy of a player's weapon fires the authoritative
  shots.
- Owner-driven movement: the server Actor follows the owner's M_CL_UPDATE
  position (steps > 8 m ignored), ACK corrections only above 8 m.
- Stalker puppets play the server's animations (mode + MotionIDs in the
  stalker update; `CStalkerAnimationManager::play_netcoop_puppet`) and the body
  heading taken from the server XFORM.
- Item use: `CInventory__eat` runs on the client (GAMMA use animations), the
  eat is applied on the server.
- Ogg sources up to 48 kHz are accepted (GAMMA music).

## Verified at runtime

- Server loads, login works, NPC logic runs on the server: diagnostic shows
  ~47 NPCs updating, ~16 moving (walker/animpoint schemes).
- PDA opens on the client (it then hit SIMBOARD nil, fixed in 6630f67).

## Not yet verified (next test)

Build 9ead87b / 7d1b51c:
- dialogue window with traders (server/client log lines
  `[NetAnomaly] talk ...` show the reason if it closes);
- items in hand, weapon fire damage on NPCs, PDA tabs layout (likely fixed by
  the start callback), NPC animations/heading, weather sync, tasks in PDA;
- two clients (`session.ps1 -Second` in the Claude scratchpad starts both).

Test helper (runtime only): `gamma-runtime/client/scripts/zz_netcoop_test.script`,
F10 walks to the nearest stalker and starts a dialogue, F9 lists stalkers.

## Known gaps

- Emissions / psi storms: client managers are created with a far timer so the
  client does not start its own; server emissions are not sent to clients yet.
- Remote players see weapon states through relayed events; third-person
  animation quality not checked.
- Map spots added by server scripts are not replicated.
