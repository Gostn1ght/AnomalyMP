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
- `_g.start_game_callback` (-> every script's `on_game_start`) now runs once
  per level before the first server spawn (`Level_network_spawn.cpp`; during
  level load the client `game` does not exist yet and GAMMA reads game time). It only ran when an ALife simulator was
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

## Verified at runtime (builds 7bbc6d8 .. 14b8373, 2026-09-28)

- Server: NPC logic runs (walker/animpoint schemes, ~16 of 47 NPCs moving),
  time events (ZCP mutant respawns), weather chosen and sent (w_partly3,
  w_rain4 seen on the client).
- Client: GAMMA HUD and on_game_start handlers work; admin debug menu (F7);
  admin `srv spawn` puts items into the inventory; pistol drawn into hands and
  holstered; 3D PDA opens through activate_slot(8) with the map on screen; PDA
  is auto-equipped in slot 8.
- NPC puppets sit and work at animpoints (technician at his bench) instead of
  T-posing.
- Dialogue: trader/technician dialogue window with GAMMA phrases, choices go
  through the server (e.g. "work?" -> "nothing"), "trade" opens the NPC trade
  window on the client with the trader's goods (trade profile sent by server).
- Two clients: tester (admin) and tester2 (player) on one server; player 2
  sees player 1's third-person model; both can talk to the same NPC.
- Admin server Lua console: `srv lua <code>` (admin only) runs on the server
  and prints the result, e.g. `srv lua return tostring(hide_hud_inventory())`.

## Open issues (next)

- The PDA key (P) does not reach CInventory::Action; Lua sees it
  (on_before_key_press ret_value=true). Build 14b8373 logs the path:
  `[NetAnomaly] key 51 taken by the game UI` / `key 51 to entity ...` /
  `actor key 51: remote=.. talking=..`. Read those lines after pressing P.
- Buying/selling in the trade window not yet exercised (needs mouse input;
  the game cursor ignores synthetic absolute mouse positions).
- PDA tab captions overlap at 960x540 (test profiles p1/p2 run windowed at
  960x540); normal at larger resolutions.

## Test helpers (runtime only, not in the repo)

`gamma-runtime/client/scripts/zz_netcoop_test.script`:
F10 walk to the nearest trader/technician (else stalker) and talk; F9 list
actors; F11 walk to 3 m from the other player; F8 admin spawn pistol + ammo;
F7 is the GAMMA debug menu (do not use for tests); F6 activate the PDA slot
and print slot state; P is watched and logged.

Scratchpad `win.ps1`: -Keys (scancodes, WAITn, HOLDk:ms, TURNdx for relative
mouse), -Text (ASCII typing, set WIN_EN_LAYOUT=1), -Shot (set
WIN_SCREEN_CAPTURE=1 for DX11 windows). After loading GAMMA waits for a key:
send SPACE after the bar is full, or the level stays paused.

## Known gaps

- Emissions / psi storms: client managers are created with a far timer so the
  client does not start its own; server emissions are not sent to clients yet.
- Remote players see weapon states through relayed events; third-person
  animation quality not checked.
- Map spots added by server scripts are not replicated.
