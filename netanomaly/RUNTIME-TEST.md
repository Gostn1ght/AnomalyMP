# Local GAMMA test, 2026-09-15

GitHub run 34930600132 successfully built commit
`f7c25f7a6d8a52896bfdabaed7aeb71c557f46cf`.
Installed EXE SHA256:
`c0be9fe61a18ec259474ba42110735eea1642baf731017f8944e1616c98a0a2e`.

The isolated runtime uses the installed GAMMA archives and enabled GAMMA loose
content. An explicit native `$fs_root$` fixed archive lookup failures caused by
inconsistent separators and initialization order. Base configs/scripts were
extracted into the separate role trees without replacing GAMMA overrides.

The rendered host reached `fake_start` and logged its internal client connection
(`gamma_server13`). This is not evidence of two external players or a playable
GAMMA world. No external client acceptance has passed.

Dedicated run `gamma_dedicated14` crashed before flushing its log. A debugger
captured the first access violation at EXE RVA `0x1ed749`, in `full_memory_stats`:
`ai().script_engine().lua()` accesses a null script engine. The legacy dedicated
branch skips all of `CAI_Space::init`. Its error handler then also accesses Lua,
masking the first failure with a second crash at RVA `0x1ff652`.

The next patch enables AI/Lua initialization and patrol storage for netcoop
dedicated mode, makes memory diagnostics tolerate absent Lua, and guards the
error stack callback. Runtime confirmation requires the next GitHub build.
Disconnect cleanup also uses an explicit internal destruction path after the
transport peer has been removed; packet-driven calls retain ownership checks.

Remaining acceptance includes dedicated startup, two account-authenticated
external clients, real GAMMA world initialization, movement, disconnect/rejoin,
server inventory transactions and persistence, per-player quests, role enforcement
in gameplay, and load testing with actual clients. The standalone SQLite bridge
is not yet connected to native engine state. A 128-slot setting is not load-test
evidence. Server/client filenames currently contain the same EXE.

## Follow-up build and console startup

Run 34981063850 successfully built `7a66c23ce6d4234a93d3c7b8d9749b850ba34177`.
Installed EXE SHA256:
`048fd2711282716639ca462612df27c2f721018f37dd387f8b612c7872f0ec67`.
Dedicated startup passed the old Lua crash, then failed at RVA `0xd275be`.
Matching PDB symbols identify `dxUIRender::SetShader`, dxUIRender.cpp:30.
The runtime dedicated switch selected graphical `CConsole` despite skipping
shader creation. The next patch selects native `CTextConsole` and skips graphical
Begin/End/Clear, precaching, and scene rendering in dedicated mode.

The user explicitly requires server console startup and verified readiness
**before** launching either client. All rendered-host experiments are stopped.
`server/console.py --start-server --runtime PATH` owns only the dedicated process,
prints its logs, and provides account role management. Native engine commands
remain in its dedicated text window. `quit` in the account supervisor terminates
its child process; native graceful shutdown/persistence acceptance is still pending.

GAMMA script fixes in the role adapter defer ledge setup until the actor's first
update and finish UBGL cosmetic menu callbacks when there is no actor/item.
Both failures were observed before actor creation in the rendered-host experiments.

## Dedicated GAMMA Lua/UI boundary

Run 34991767392 successfully built `635983a6f8fe855383778712056851a21cb44cca`.
Installed EXE SHA256:
`abea30bf73933412f81480241de4e92ca524a6bc0db4887e9bbdb1d450d99d84`.
The dedicated process advanced through GAMMA Lua initialization, then crashed at
`0x140B46AC5`. Matching symbols resolve this to `GetFontSmall`,
`src/xrGame/ui/UIWindow_script.cpp:54`. `dotmarks_main.script` caches font handles
at module scope, but dedicated mode intentionally has no UI font manager. The next
patch makes every Lua font getter return nil in dedicated mode instead of touching
the absent manager. No external clients were started before the server failed.

Run 34997548335 successfully built `da82e3a4e3d0c6cebdaf285dc948c8e2e4408ff7`.
Dedicated startup reached a new `l06_rostok` ALife world with 18,677 spawn points;
the authority client reached `OnCL_Connected`. The first external client exposed a
missing `$game_arch_mp$` filesystem alias, which is now generated for every role.
After that runtime-only fix the client connected and synchronized, but loaded the
technical `fake_start` map while the server ran `l06_rostok`. The server's inherited
netcoop workaround had forced map synchronization success without comparing names.
The next engine patch sends the actual ALife level in the connection result and
restores map/version validation. It also guards a null token table found when the
native server console executed `help`; that crash disconnected the first client
before `M_CLIENTREADY`, account authentication, and co-op actor spawn. A second
external client was not started.

Netcoop now compares the server and client map name/version, while skipping only
the geometry checksum because single-player ALife startup does not prepare the
multiplayer checksum on the server. The `all` session token remains unchanged: it
names Anomaly's all-level spawn database rather than a playable map.
Because dedicated startup has no character-creation screen, the generated server
profile now supplies GAMMA's `csky` / `hidden_base` choices. `hidden_base` resolves
to `k00_marsh` in GAMMA's own `new_game_start_locations.ltx`.

Run 35097570010 rejected `ddc815ffd` during compilation because `level_version`
was called through `game_sv_GameState`; it is an `xrServer` member. No runtime was
published from that failed build. The follow-up patch calls the server member
directly.

Run 35099597993 successfully built `fd2c3856f`. The first dedicated session loaded
18,677 spawn points, opened port 1237, and connected its authority actor, but ALife
selected `l12_stancia_2`: GAMMA's UI-owned character creation module does not
register its start-position callback in dedicated mode. The server bootstrap now
registers an authority-only first-update callback which applies GAMMA's own
`hidden_base` coordinates and changes the active level to `k00_marsh` once.

That callback was registered but dedicated mode did not dispatch the actor's
first-update callback; a second session again became ready on `l12_stancia_2`.
The replacement engine patch teleports the ALife authority object immediately
after simulator creation and before the server publishes its level. It also makes
the native debug console a standard movable Windows window with a visible cursor
and mouse-wheel log scrolling. The Python account console no longer mirrors the
engine log.

Run 35105355666 successfully built `20dee4669`. The native console opened with its
movable debug window, the authority connected, and port 1237 opened. The log showed
the object teleport after ALife had already selected `y04_pole`; the current level
registry therefore remained unchanged and the connection result still advertised
`fake_start`. The next patch applies the same GAMMA `hidden_base` graph, level
vertex, and position inside `CALifeGraphRegistry::setup_current_level`, before the
registry and level are created.

Run 35346488863 successfully built `91c35c089`. The server loaded 18,677 spawn
points, opened UDP 1237, accepted its authority connection, advertised
`k00_marsh 1.0`, and loaded `gamedata/levels/k00_marsh`. This confirms that map
selection now happens before ALife creates the active level registry. The first
scheduled anomaly update then crashed in `CCustomZone::shedule_Update`, line 647:
dedicated mode has no `CurrentControlEntity`, but the client fast-mode calculation
dereferenced it without a null check. No external client was started. The next
patch uses the current server entity as a fallback for anomaly scheduling and
guards the client-only distance/effect calculation.

Run 35351645554 successfully built `3de7e2915`. Installed EXE SHA256:
`aa50abe20115e0baf50f758346b980ea9075c7dc7138e64b5b71de117e3f25b5`.
The anomaly null guard passed. The server again loaded 18,677 spawn points,
selected and advertised `k00_marsh`, opened UDP 1237, and connected its internal
authority peer. GAMMA then exposed three actor-ordering assumptions while ALife
was scheduling NPCs before the first actor existed: `drx_da_main.script:2823`,
`schemes_ai_gamma.script:151`, and `xr_meet.script:594`. The runtime adapter now
limits actor-dependent anomaly effects, combat checks, and meet setup until an
actor exists while preserving base anomaly, NPC, and AI updates. Lua fixtures
verify that each deferred path resumes after actor creation.

After those script fixes the next blocker is an access violation at
`CAI_Stalker::shedule_Update`, `ai_stalker.cpp:1162`. The optional NPC look-at
callback directly dereferenced `Actor()` before a player spawned. The pending
engine patch guards only that callback and continues the stalker's vision,
agent-manager, and planner updates. The first external client was launched during
diagnosis but did not reach actor spawn before the server crash; the second client
has not been started. Two-client gameplay and persistence acceptance remain open.

Run 35463287937 successfully built `ce7235811`. Installed EXE SHA256:
`ed65ea9f906ef38931cdc1641454e97bfaea1346be9a3f70444740bc7d820e35`.
The server stayed ready on `k00_marsh`, with 18,677 spawn points, its internal
authority connection, and UDP 1237 active. Two more early actor assumptions were
found in `aaaa_script_fixes_mp.script`; the role adapter now suppresses those item
callbacks until `db.actor` exists.

The first external client connected, accepted `k00_marsh 1.0`, and began receiving
server NPCs. It then crashed in `CQuadTree<moving_object>::insert`, called by
`CAI_Stalker::net_Spawn`. The joining netcoop client had skipped `CAI_Space::load`
because the legacy condition only recognized an enumerated listen-server host;
therefore its moving-object quadtree had never been initialized. The pending patch
loads level AI for every netcoop peer before network spawns. It also gates GAMMA's
central actor callback dispatcher and guards background crow, monster, trader,
task, dialogue, inventory, and map paths that can run before a local actor exists.
The second external client remains untested until the replacement build passes the
first-client spawn boundary.
