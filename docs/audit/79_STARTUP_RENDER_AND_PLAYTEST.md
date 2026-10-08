# 79. Startup rendering, watchdog and owner four-map play session

2026-10-08, Codex. Original188 counters remain27/33/69/59 (161 unclosed).
These focused startup repairs do not close unrelated AI/chunk/performance rows.

Ordinary PLAYER startup previously rejected `g_always_active on` and
`keypress_on_start off` from user.ltx. The client could retain its loading
backbuffer and wait for keyboard input after network admission. The internal
console classifier now permits only those exact local preferences, alongside
the two previously qualified screenshot commands. Keyboard/admin/gameplay
permissions remain. Actual765-case classifier differential passed GCC
ASan/UBSan and MSVC in GitHub Actions for ce633f85e.

The first eca native run exceeded its controller's ten-minute deadline; its
capture still showed loading. The ce repeat exposed a distinct startup crash:
the frame-based Lua watchdog aborted normal spawn callbacks after60 seconds
in loading frame38, followed by an inventory_box construction fatal. Both
failures and journals remain in the respective private background-render roots.

The watchdog keeps20-second diagnostics and the normal60-second gameplay
abort. Only queued loading events, or a non-dedicated client's GPU precache,
receive a bounded20-minute loading budget. Dedicated runtime does not render
End and can retain stale precache_frame=60; that value must not disable its
normal60-second protection. Actual production hook boundary fixture768 cases
passed on both GHA toolchains for21351fe49. No AI/vision/cadence/population
change. The watchdog remains frame-based during gameplay, not a universal
per-call Lua execution budget.

Both native do_exit implementations now honor the existing explicit
`-silent_error_mode` for their modal dialog only. Reason logging, FlushLog,
TerminateProcess(1) and ordinary dialogs remain. Actual method-order fixture
passed on both GHA toolchains. This is used only for unattended negative tests;
the owner's interactive launcher retains normal errors.

The bcc graphical repeat completed precache, opened native inventory with15
retained groups, closed it and captured the Cordon world. BOTH944x501 native
PNGs were viewed: actual inventory over Cordon, then actual world/HUD/NPC.
No loading artwork in these captures. Ordinary account nbot_961 remains PLAYER.
Evidence: `_build/live/background-render-bcc28d4ae/qualified-render-scope.json`,
two PNGs and sealed client/server.after-failure.log SHA hashes.
The full controller result remains FAIL: after captures a legacy GAMMA
GUI_on_show handler indexed a missing GetTalkingNpc speaker in
z_gavrilenko_tasks_fix.script:19. Launch/render scope accepted separately;
not human Firebase/first3D menu/all focus modes/64-player visual acceptance.

The owned client/server overlay override preserves G_FLAT's original header
and singleplayer task behavior. Netcoop does not register or execute this old
story autocompletion; an absent speaker is safe in singleplayer. New Lost Zone
contracts are independent. Actual Lua5.1 regression verifies missing speaker,
normal SP completion and no MP registration/completion. DX11 CI runs it.
Only the PRIVATE four-map scripts have this repair installed; primary scripts
are untouched. Byte originals and hashes: LostZone-4Maps-Test/fix-backups and
legacy-dialog-fix.json. Existing sandbox Lua regression also passes.

Latest engine package qualified from completed GitHub Actions:

- Source21351fe49aceaee8624f16515af6a47a24031b80.
- Foundation37811183846 SUCCESS both jobs, watchdog768 cases each.
- DX1137811183642 SUCCESS full engine/package; artifact11565414387.
- ZIP4fc88a0647c77e9135cac46c887ab709d2b390fee5913a12c24539cb770d8138.
- Both EXEs91FDA3F357C3694BDCF68C01A9DE69D9C854A47524EFD6781A792E8849CA4CAA.
- built-from, artifact digest, manifest and actual EXE hashes verified.

Owner explicitly requests persistent servers Cordon1477, Swamps1467,
Garbage1487, Bar1497 and an interactive test ADMIN account. Prepared separate
LostZone-4Maps-Test with clean original actor binder, separate new world/account
namespace, shared cluster routing and DPAPI automatic local test_admin login.
Random test password discarded; no credential material in launchers/logs.
Native server console must grant ADMIN before client login, then native
authentication/Actor/precache/world pixels must be checked. No cluster_selftest
or automatic bot transfers. A read-only startup observer requests one native
PNG after precache and does not change UI/AI/gameplay.

First four-map attempt failed before world creation with missing server
user.ltx and native access-violation stack, all own processes stopped. Added
qualified private server settings and fail-fast launcher preflight. Retained
all original logs/dumps and failed-start-missing-user-settings.json; no world
deletion/reseed. Second attempt exposed Empty lightning_model: the preparation
helper shortened fs_root while keeping game_data and archive paths long. X-Ray
virtual archive lookup keys no longer agreed. Server fsgame now retains the
exact qualified LONG fs_root/game_data pair. Applying that server spelling
also to the client was incorrect: its qualified game_data is SHORT, producing
the same lightning-model fatal in the first interactive client. The owner
reported that crash. Its journal is sealed as client.failed-archive-alias.log.
Client fsgame now restores its OWN exact SHORT fs_root/game_data pair. Both
launchers preflight literal agreement before starting. UTF8noBOM throughout.
Failed-start-archive-alias.json and all native journals/dumps remain. No model
replacement or weather/AI reduction. Third server attempt accepted: all four
native maps durably ready, native console grants test_admin ADMIN with GUID
4be32dcd4a6243f5ba8a6f72d4d7ca3d. Running server PIDs7732/20264/21592/14656
(Cordon/Swamps/Garbage/Bar), running-servers.json records source/paths/ports.
Repeated interactive client PID16632 is loading; final entry pending.
Primary fingerprint check after server launch: all88 protected files MATCH.
Lua source1b01b013d pushed; DX1137816511889 actual Lua checks SUCCESS,
full engine still building. User EXEs are qualified213, no intervening C++
delta; new Lua guards independently verified/installed only in private session.

Primary four EXEs remain FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88;
no primary engine rollout. Earlier installed delta14sounds/20loadoutLTX/
4client UI script files remains. The owner's requested play session is to be
LEFT RUNNING after verified entry; unrelated nine B06 cases prepared, not run,
deferred until owner play is no longer using game processes.
