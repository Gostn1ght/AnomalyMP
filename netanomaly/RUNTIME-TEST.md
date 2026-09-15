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
