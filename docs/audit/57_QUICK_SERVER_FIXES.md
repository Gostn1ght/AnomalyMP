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

## Remaining limits

Previous live logs also contain `itms_manager.save_state` nil-actor errors;
this separate player-inventory callback is not fixed by the PDA guard.
The new strict gate correctly refuses those runs. Logged caught-error totals
may be capped by the compatibility module and are not exact occurrence counts.
No measured FPS claim, no new completed marks in the historical 188-item
audit, no primary executable promotion from these script fixes.
