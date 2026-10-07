# 58. Bot cluster reconnect regression (2026-10-07)

## Native reproduction (FAIL, retained)

Private `_build/live/quick-transitions`, verified GHA fa5edb5f2 exe,
Marsh1367/Cordon1377, four bots in two dedicated bot processes, three minutes
after both maps loaded. Focused PDA/personal item-save guards in private
server scripts. Test-only world save period30s; normal default stays300s.

All four joined initially.20leaves,19arrivals,3redirects; final3playing/1failed,
three admission retries. Zero Lua, fatal, shader, character/world-save,
refusal or lease-reject records. Strict production harness exit1.

Bot001 timed out after transfer to Cordon. Its recreation used global
`s_address` (initial Marsh) instead of the current Cordon address. Marsh
correctly responded `redirect|127.0.0.1|1377|l01_escape`; the bot treated it
as failed authentication and exhausted its three retries. This is a load
driver bug. The graphical player's authentication has separate redirect
handling; this reproduction does not demonstrate the same bug there.

## Fix prepared

- Retain each bot's last connection target even if Connect fails; retry that
  target, keeping the existing three-retry bound and stable-playing failure rule.
- Valid server auth redirects queue a transfer, just like the normal script
  transfer message. Disconnect/recreation stays in bots_frame, outside the
  receive queue lock.
- One strict host/port/level decoder for both bot paths; reject malformed,
  overflowing, empty or trailing fields without changing a pending target.
- Actions-only native fixture extracts actual start/auth/queue methods and
  the actual retry/transfer loop, exercising the reproduced failure chain,
  deferral, immediate Connect failure, name restoration, rejected auth,
  retry exhaustion and malformed/fuzzed targets under GCC sanitizers/MSVC.

Native compile/fixture results and fixed two-map acceptance remain pending.
No NPC, real player protocol, cadence or quantity changes. Current previous
DX1137639441890 completed before the fix's next code push.

## Inventory probe limitations

Late debug seeding reached bots002/003/004 (two bandages + one bread each),
after001 failed. Final native NCH7 files002/003 contain those sections and
nonzero item UIDs;004 contains only its PDA. Seeding may have raced an already
frozen outgoing actor; no early inventory snapshot was captured. Do not mark
loot preservation PASS or infer a normal-player item-loss bug from this
late injected fixture. Repeat with seeding before the first handoff and
compare all four inventories/UIDs after round trips and restart.

Analysis of the retained files uses the actual host's raw CRC32C branch,
not Python's ordinary CRC32. The current xrCore crc32 has hardware-dependent
SSE4.2 vs fallback polynomials; cross-hardware persistence compatibility is
a separate open investigation requiring migration-aware treatment. It was
not changed globally as a quick fix.

No new completed marks in the historical188 audit;64/max-view smoothness
and full cluster512 remain open.

## Publication/validation status

Local source commit `8ef6a25f5`: prepared fix/actual fixture plus save-error
gate; local PowerShell regression and Python syntax check PASS. No local
C++ compilation. GitHub rejected three pushes with Internal Server Error,
including a per-command HTTP1.1 retry; remote branch remains81ae903c1.
The public status page reported operational, so a global outage is not
confirmed. This fix has no Actions/native result yet and is not installed
as a new executable. All probe processes stopped; debug file empty.

Publication recovered on retry: source8ef6a25f5 and docs c6525f885 pushed.
Foundation37642993485 SUCCESS on GCC sanitizers/MSVC, including the actual
bot methods/loop fixture. DX1137642993484 full build pending. The next native
probe is staged with early seed arming before bot launch; acceptance still open.
