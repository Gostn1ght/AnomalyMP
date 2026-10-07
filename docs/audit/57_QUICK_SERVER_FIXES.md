# 57. Quick server fixes (2026-10-07)

Owner priority: easy/quick work first, then medium, then complex. The 64-player
frame-time and maximum-view NPC smoothness acceptance remains open.

## Implemented and locally checked

- Dedicated PDA discovery: patch GAMMA `discover_spots` immediately after its
  existing timer reset and actor lookup. Without a local actor it returns;
  the original three-second timer remains alive. With an actor all original
  discovery, rank and UI behavior remains. The overlay installer applies the
  focused helper to server scripts only, byte preserving and idempotent.
- Load driver: remove PowerShell's case-insensitive `$botArgs`/`$BotArgs`
  collision. Four processes now receive independent bot ranges and exactly
  one copy of custom flags. Hidden windows and waits of at most ten seconds.
- Load acceptance: snapshot bot states before shutdown, count unique login
  identities rather than repeated Actor messages, require every load bot
  playing and no terminal failures. Missing logs/reports, zero joins,
  inconsistent reports, shader/fatal/Lua/save errors fail the command.
  Recovered admission retries are reported separately. Cluster mode permits
  transfers still in flight after all requested bots have joined; this gate
  does not certify every transition path or duration. Cleanup refuses paths
  outside the private appdata area and junctions.

Local checks PASS:

- `check-netcoop-server-pda.py`: actual PowerShell patch plus pinned GAMMA
  Lua 5.1 timer/discovery functions. Reproduces the old exception; verifies
  timer reset, another world callback, unchanged discovery with actor,
  leave/rejoin, CP1251 bytes, LF/CRLF, idempotency, unsupported-input rejection.
- `check-netcoop-load-harness.ps1`: actual launch loop with a fake process
  launcher; split ranges/custom flags; production result evaluator with
  healthy/retry/missing/zero/duplicate/incomplete/terminal/shader/Lua/save and
  in-flight transfer cases. No games are launched by this fixture.

Both checks are wired into GitHub Actions on Windows before native build.
Native verification and CI results are recorded below when available.

## Native and CI evidence

Source `765a708b0446d6ae5e878742c767191e568e57d7`:
Foundation `37636526831` SUCCESS on Linux/Windows; the new actual PS/Lua
step also passed in DX11 `37636526929` (native build pending at this entry).

Private `_build/live/quick-pda-765a708b0` ran the previously verified GHA
`fa5edb5f2` server exe, SHA256
`794316757B231F71467194E358084588DB93963E0B0225346C412686AE212113`.
Only private scripts/appdata differed. Debug probe armed the actual patched
`pda.discover_spots` in the real `ScanForSpots` queue with no local actor.
Ten consecutive timer resets and a second probe timer succeeded; zero
time-event, fatal or debug errors. Native bootstrap world save succeeded.
There was still one caught `itms_manager.save_state` error; this run certifies
the PDA fix, not a completely error-free dedicated server. Probe stopped,
debug file empty. `summary.json`, `probe.lua` and native log retained there.

The strict evaluator also re-read archived `fa5edb5f2` live16/live64 logs:
16/64 unique joins and final playing, zero terminal failures, 3/8 retries,
21 caught Lua records each. Both correctly FAIL the new clean-run gate.

Focused primary installation is limited to backed-up `server/scripts/pda.script`
in both prepared runtimes; executable promotion still remains gated by the
open 64-player/max-view acceptance. Installation results are appended after
checking the byte-preserving change.

Installed focused PDA patch in `gamma-runtime` and `LostZone-3D-Hideout` after
stopping the private probe. Both original files SHA256
`12A5D397F7D0C31632AAED6BB768633594C37EF3A7DB183511F5F85FA478D821`;
both installed files SHA256
`B5D9D08E3EE20E1551621A55977D559A8F5867DED2788098CF11BD81A543AF85`.
Removing the inserted guard reproduced every original byte. Backups and
`installed.json` retained under the private probe's `primary-backup/`.
No full overlay installer or native executable replacement was performed.

## Remaining limits

Before the continuation below, live logs also contained `itms_manager.save_state`
nil-actor errors; that separate hook needed its own guard. The strict gate
correctly refuses those old runs. Logged caught-error totals
may be capped by the compatibility module and are not exact occurrence counts.
No measured FPS claim, no new completed marks in the historical 188-item
audit, no primary executable promotion from these script fixes.

## Autonomous continuation: item save and reliable private probes

The previous source765a708b0 DX11 run37636526929 completed SUCCESS, including
full engine/package/upload. It was allowed to finish before the next code push.

Implemented focused `itms_manager.save_state` guard: without `db.actor`,
return before touching state. This single-player hook stores personal bolts;
an empty world has no player's inventory to enumerate. With an actor every
original statement remains. No anchor actor substituted, no errors swallowed.

Local `check-netcoop-server-item-save.py` PASS on the actual PowerShell patch
and pinned GAMMA Lua5.1 function: reproduced old nil actor failure; preserved
existing/empty state with no actor; differential inventory/bolt count and
slot checks, leave/rebind, API errors still visible, CP1251/LF/CRLF/idempotency,
unsupported and duplicate-function rejection. Source excerpt attribution and
CC BY-NC-SA3.0 recorded with the reference. This does not by itself prove
whole character inventory persistence through restart.

The real load harness now refreshes process states before reading final bot
reports and rejects early exits even if a log has an older healthy report.
An optional GAMMA working directory allows isolated exe/appdata probes;
private fsltx paths remain explicit so a changed cwd cannot select a main
runtime's selftest files. The existing engine parser cannot handle spaces in
an explicit fsltx token; that unsupported combination fails before cleanup.
Default same-runtime relative config names still support runtime paths with
spaces. Actual launch-loop tests cover both private configs and working dir;
cleanup tests cover traversal and ancestor/subtree junctions.

Native verification uses `_build/live/quick-item-save`, private scripts/world,
two bot processes/four bots, and the already GHA-built fa5edb5f2 executable.
Results and CI evidence will follow after the run.

Continuation evidence: source81ae903c1 Foundation37639441808 SUCCESS and
DX1137639441890 SUCCESS (23m9s, full engine/package/upload). Status verified
on public Actions because local api.github.com connections were reset;
package has not been downloaded/validated locally yet.

Native quick-item-save: four unique bots, final4/4playing, zero terminal,
Lua/fatal/shader/save/admission errors, production harness exit0. Native
quick-transitions: both bootstrap saves, periodic saves8/4 and last-player-left
saves3/3 on Marsh/Cordon, zero Lua/save/fatal/shader errors. The latter run
failed for a test bot reconnect problem; doc58 tracks that separately.
These native tests used the existing verified fa5edb5f2 exe and newly patched
private scripts, not an unvalidated new package.

Focused item-save guard installed in both prepared runtimes, with byte-preserving
inverse comparison and backups under `_build/live/quick-item-save/primary-backup`.
Original SHA256 `83E113D2C9F3FE2A230C7DE0E2425A2A0A5D33DFB2F7E539420C545EA7D51867`;
installed `364F6BE9060DF649ACD686FF0C833ECBADEF329C0E0F0F0D5762A4ADBC9737BF`.
No executable promotion. The strict evaluator also rejects world snapshot,
pointer, character commit/refusal and incomplete inventory restore failures.

Source81ae artifact11491544969 subsequently downloaded and validated at
`_build/gha/item-save-81ae903c1`: ZIP SHA256
`f13edaebb59db959d6be347274a1d14c2b850e1eb8993ee466e0ed247d05edb6`;
both exe SHA256
`D132C8EAB7C0EB747D0BC958B94118B5B4FB7E920F0733160051BA1948E5858C`.
Built-from/manifest/ZIP digest checked; no primary exe installation.
