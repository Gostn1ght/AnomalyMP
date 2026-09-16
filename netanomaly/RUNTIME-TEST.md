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
