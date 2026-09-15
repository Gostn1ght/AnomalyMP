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
