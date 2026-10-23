# Engine restructure and performance plan (owner 2026-10-20)

Owner: study the architecture problems and bugs of this engine and fix both;
cut the DX9 and DX10 renderers, keep only DX8 and DX11; cut what is not
needed; separate e.g. helicopters and cars; make the structure normal by
open documentation (find the best variant); write proper multithreading and
DX8 optimisation; remove the rectangle that opens before the game; let the
game load while alt-tabbed; start fast instead of minutes of black screen.

Work happens on branch `engine-restructure` (worktree
`NetAnomaly_Full\engine-restructure`), built by `workflow_dispatch` of the
DX11 workflow, merged into `menu-3d-hideout` stage by stage so the Codex
session never works against a moved tree for long.

## What is there (2026-10-20)

| Part | Files | Lines |
| --- | --- | --- |
| xrGame | 2741 | 470 k |
| xrRender (shared) | 242 | 56 k |
| R1 (static light, "DX8" config) | 36 | 6 k |
| R2 (DX9) | 91 | 13 k |
| R3 (DX10) | 98 | 17.5 k |
| R4 (DX11) | 114 | 22 k |
| xrRenderDX10 layer (R3+R4) | 55 | 14.5 k |
| xrEngine | 190 | 53 k |
| xrCore | 176 | 46 k |

One executable per renderer (DX8 = R1, DX9 = R2, DX10 = R3, DX11 = R4 build
configurations, statically linked). CI builds and ships only DX11.

Reference layout: OpenXRay (github.com/OpenXRay/xray-16) — renderers as
separate modules behind `xrAPI`, `xrCore`/`xrEngine`/`xrGame` split, the
task manager `xrCore/Threading/TaskManager` (work-stealing job system) used
for loading and per-frame parallel work.

## Measured start of the client (viewtest stand, warm shader cache)

| Time | Phase |
| --- | --- |
| 0–22 s | process start, file system index of 108 773 files in 135 archives (nothing in the log until "Starting engine") |
| 22–43 s | engine, configs, material pairs, textures descriptors |
| 43–86 s | **silent 40 s** after the HUD font: no log line (to find: shader creation / texture prefetch of the 3D menu room) |
| 86–92 s | 3D menu room, menu ready |

92 s here with a warm cache; the owner sees ~5 min (first start compiles
every shader; slower disk/CPU).

## Stages

1. **Start and focus (first, visible to players)**
   - Phase timings in the log (`[startup] N s: phase`), then remove what the
     timings show: the silent 40 s, the file-system scan on every start
     (cached index), log buffering.
   - Load while alt-tabbed: a lost/occluded device sleeps 33 ms per loading
     step and some steps wait for a frame; loading must not depend on focus.
   - The window/rectangle before the game (to confirm with the owner which one).
   - Shader compilation in parallel worker threads on the first start.
2. **Renderers**: remove R2 (DX9) and R3 (DX10): projects, configurations,
   menu entries, `renderer_r2*`/`renderer_r3` console values, dead shared
   code; keep R1 (DX8) and R4 (DX11); CI builds DX8 too.
3. **Structure**: split the netcoop monolith (netcoop.cpp + .inc) into
   modules (accounts/auth, characters, storage, trade, PDA, cluster/master,
   vehicles, helicopters); cars and helicopters as separate modules over a
   common vehicle base; remove dead parts (in-game editor hooks, duplicate
   `optick`/`optick-git`, old `engine.sln`, unused 3rd-party code) after a
   reference check.
4. **Multithreading**: one job system (OpenXRay-style task manager) instead
   of ad-hoc threads; parallel loading (textures, models, spawn), parallel
   per-frame work (particles, skeleton updates, AI scheduler slices),
   keeping the server's determinism.
5. **DX8 (R1) optimisation**: batching, state caching, visibility, LOD.
6. **Bug sweep**: MSVC `/analyze` in CI, crash classes from dumps (doc 150:
   single-player `Actor()` on the server), fix by class, not one by one.

## Progress 2026-10-20

Branch `engine-restructure` (dispatch builds):

- Start marks `[startup] N s: phase` in the log (phases, frames over 1 s,
  loading steps over 0.3 s, shader compilations, mods' XML files over 50 ms).
- No full listing of the 108 k archive files at start; no per-material log
  lines (1 400 per start).
- R2 (DX9) and R3 (DX10) removed; DX8 (R1) built in CI next to DX11; both
  clients reach the menu (DX11 46 s, DX8 33 s on the viewtest stand).
- Splash dialog removed.
- `CarHelicopter.cpp`; vehicle includes split by side; `netcoop.cpp` split
  into 13 section modules (checks read them through `scripts/netcoop_source.py`).
- Mods' XML callbacks (DXML) cached per setup: archives, loose scripts, MCM
  `axr_options.ltx`, `user.ltx`, build (`-no_xml_cache` turns it off).
- Dead code: `_EDITOR`/`INGAME_EDITOR` branches (147 files), OpenAutomate
  (SASH), `-batch_benchmark`, `-launcher`; the GSC logo intro is off online.
- Skinning threads: the own spinning `ttapi` helper threads replaced by
  `tbb::parallel_for` on the pool the engine already uses.
- Legacy MP modes DM/TDM/AH/CTA removed: 262 files, ~47 k lines (game
  classes, buy menu, votes, admin menus, stats, team panels, rewards,
  anticheat screenshots, the never-registered MP console commands, modules
  nobody included). Clsids `art_cta`, `mp_players_bag`, `team_base_zone`
  and the actor MP pair stay registered for configs and scripts;
  `get_rank` (stalker weapon choice) moved into `ai_stalker_alife.cpp`.
  Bug fixed on the way: `M_SV_DIGEST` from any client crashed the server
  (null `game_sv_mp`).
- Second MP cut, nothing left as a placeholder: MP demo record/playback
  (all `IsDemoPlay`/`IsDemoSave` branches), the MP actor pair, the MP items
  (`art_cta`, `mp_players_bag`, `team_base_zone`: only MP configs name
  them, single levels never spawn them, no GAMMA script uses the clsids)
  and the anticheat parameter dumps. 77 files, -3.7 k lines.
- No logo video online: the menu waited ~3 000 frames for `intro_logo`;
  now it opens on frame 2.
- The cluster folder is resolved and created once (the server frame profile
  showed `CreateDirectoryA` every frame).

Server frame profile (dedicated, 24 stalkers + 14 mutants online, 1 player):
the main thread sleeps in the frame limiter ~70 % of the time; stalker
`UpdateCL` ~11 %, Lua ~7 %. AI multithreading is not the bottleneck at this
load, so stalker vision stays synchronous (its result is read by memory in
the same update: an asynchronous vision would make NPCs react later).

Start to the 3D menu, warm, viewtest stand (i5-2500K, 4 cores), 2026-10-22:

| Phase | Before | After |
| --- | --- | --- |
| to the 3D menu | 26.8 s | 9.9 s |
| file system (135 archives, 110 k files) | 2.6 s | 0.9 s |
| render device (particles from Lost Zone archives) | 4.7 s | 1.9 s |
| specific characters (profiles) | 6.6 s | 0.3 s |
| weather | 1.2 s | 0.3 s |
| main menu object (string tables) | 2.5 s | 1.2 s |

What did it: Lost Zone archive reader (AES provider once, key per thread and
volume, last-block cache); folder chain stops at a registered folder; XML
id loader with a hash index and node pointers; XML includes expanded once
per batch (5 943 includes of 114 files); string tables walk nodes in order;
thunderbolt models shared by name; LTX item file names computed per file.
Found with `viewtest\sampler.py` (main-thread sampling from process start,
~65 samples/s) and `phases.py` (samples split by `[startup]` marks).
Dedicated server on the same build: ready in 85 s (was 106-139 s), same
online objects (24 stalkers, 14 mutants).

Dedicated server (Marsh world, 24 stalkers, 14 mutants), ready to the first
`[world] online`, 2026-10-22: 85-95 s before; 62 s on the first start of the
new build (it builds the collision cache); 35 s after. What did it:

- `smem_container` (shared motion keys and mesh data) in hash buckets
  instead of a sorted vector with middle inserts (quadratic);
- the level's OPCODE collision tree (3 077 609 triangles, ~8 s) cached in
  `appdata\cform_cache` (98 MB for this world; checked on read, 12 files at
  most, `-no_cform_cache` turns it off);
- no game-file CRC on connect online (~3.5 s, never compared by netcoop).

Still in the server start: ~30 s of GAMMA Lua scripts in the ALife
constructor (string tables, script XML, Lua pattern matching).
`optick` is not a duplicate: `optick/` is the project file, `optick-git`
the profiler's sources (a submodule); the profiler is off by default.

Later on 2026-10-22:

- `xrMemory::mem_usage` reads the OS counter (private bytes) instead of a
  `_heapwalk` over every allocation (~5 s of a server start: load stages,
  the menu and `stat_memory` call it for log lines).
- The Modded Exes unlocalizer compiles its four `std::regex` once instead of
  for every line of every unlocalized script (~1 s of a server start).
- `[startup] script NAME loaded in N ms` (over 200 ms) and
  `[startup] section_for_each ... from SCRIPT:LINE` (over 100 ms) find the
  rest of the GAMMA script time.
- The server's actor entity skips the clients' optional weapon-slot tail:
  no more `update of actor [0] left 8 trailing byte(s) unread`.
- Code analysis on demand: `gh workflow run lostzone-dx11.yml -f analyze=true`
  runs MSVC PREfast over xrGame and its projects and uploads a report
  (`scripts/report-code-analysis.py`), Lost Zone's own files first.
- Client level loading cannot be measured on the viewtest stand (the client
  signs in with Google only; without `-netcoop` the Lost Zone menu ignores
  `-start`). Loading steps over 0.3 s are logged (`[startup] loading step`),
  so players' logs from the next release give the client profile.

Known, not from these cuts: `! update of actor [0] left 8 trailing byte(s)
unread` on the dedicated server (the ALife anchor actor), also in older builds.

Measured (main loop -> menu 23 s):

| What | Time |
| --- | --- |
| mods' XML callbacks, 1 250 files | 13.3 s |
| of which `ui\map_spots.xml` | 4.2 s |
| `ui\game_tutorials.xml` | 2.5 s |
| string tables in two languages (`use_english_text_for_missing_translations`) | ~6 s |

Cold shader cache: 47–60 s to the menu here (warm 34–35 s). One cold run
hung for over 8 minutes after the main loop; six repeated runs did not; the
hunt script `J:\LostZone_Work\_work\viewtest\hunt_hang.ps1` dumps all
thread stacks (`stacks.py`) when the menu does not come within 150 s.
Focus: the menu loads while unfocused (123 s) and minimized; the owner plays
windowed; level loading after login is still to measure.

## Progress 2026-10-22 (evening)

- Sound descriptions cached by file (`appdata\sound_info.bin`: path, CRC,
  size, time -> format, length, distances): script, material and level
  sounds no longer decode every `.ogg` at start. Server ready 34-37 s (was
  35-47 s); `itms_manager` 8 s -> 1.6 s, `tasks_placeable_waypoints` gone
  from the slow list. First (cold) start builds the cache.
- `_g` names the global table: `_g.script` is no longer loaded a third time.
- Network packets: reads never leave the received bytes (strings found with
  `memchr` inside the packet, zeros past the end, logged once a second); a
  message larger than the buffer is dropped; `r_stringZ` into a raw pointer
  is gone (char arrays go through the bounded `r_stringZ_s`, which cuts).
- An event id the server does not handle is logged and dropped: any remote
  client could stop the server with one (`R_ASSERT2` in `Process_event`).
  `GE_REQUEST_PLAYERS_INFO` (every player's IP address to whoever asked) is
  gone.
- Code analysis fixes: bounded command-line and option scans, the second
  `strchr` of `M_CHANGE_LEVEL_GAME`, a failed client spawn with a null
  object, actor menu focus with a non-cell window, the hit mark matrix.
- GameSpy remnants cut (-8.4 k lines): login/account managers, profile and
  awards stores, ATLAS stats, the server browser, the CD key box and flow,
  registry helpers, `xrGameSpyServer`, the client digest exchange, patch
  download dialogs. The player state keeps only the name. Then the MP menu
  UI nothing creates (-1.5 k lines): map list/info, server list item, team
  info, MP tab button, `mm_net_*` options, the player name modifier.

- `M_GAMEMESSAGE` from a client is dropped: the server passed it to every
  client as it came, and no client sends one (game messages go from the
  server), so only a forged chat line or notice could arrive that way.
- MP chat window/log (created only for non-single game types) and the
  remote admin console (`radmins.ltx`, unlimited password tries) cut; the
  server logs high-ping warnings instead of sending a message nothing read.
- Code analysis, second pass: the item stack counter (`helper_count`
  precedence), the anomaly feel radius on the HUD (always 5 m by a `?:`
  precedence bug), five script API methods that logged a wrong object type
  and then used the null object, grenades/items on a parent that is no
  inventory owner.
- Saved packets (spawn registry, saved objects, level spawn files) load
  with their size checked (`NET_Packet::load_block`); an entity whose
  reader runs past its data is named in the log. The bot stand showed one
  `all.spawn` entity per level whose update reader is longer than its data
  (it read the spawn bytes left in the buffer before; zeros now).
- Files include what they use (45 relied on `script_engine.h` arriving
  through `player_account.h`); the GameSpy DSA/delegate helpers and the
  unused `3rd party/crypto` library are gone.
- CI: the DX8 package carries `LostZoneClientDX8.pdb`.
- Bot stand (master, Cordon, Garbage, 4 bots, 5 min) on the packet-bounds
  build: all bots played and changed level, no crash, no packet overrun on
  the network (only the spawn entity above).

## Progress 2026-10-23

- Build 39911119533 green (all GameSpy/MP cuts); bot stand: 4 bots played
  and changed level, no crash. The named short entity is `fake_actor`
  (all.spawn): with `-netcoop` the actor update reader took Lost Zone's
  equipment block (hands, outfit, helmet, visual) from the editor's item
  count and the stale bytes after it, including a garbage visual string.
  The block is now read only when its 9 bytes are there.
- MP weapon usage statistics cut: on a dedicated server a PvP grenade kill
  went to `OnExplosionKill`, which used the already destroyed grenade
  (`net_Find` without a check). GE_HIT_STATISTIC and the statistic/bullet
  check messages went with it.
- MP voting and map rotation cut (the server ran `appdata\maprot_list.ltx`
  as a console script at every start); empty server hooks and the
  `M_PLAYER_FIRE` message the host sent to itself on every shot.
