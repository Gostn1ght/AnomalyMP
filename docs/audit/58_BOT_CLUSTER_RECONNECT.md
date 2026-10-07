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

## Fixed native smoke acceptance (PASS)

Native source c6525f885a7c4c5c562b65e543a1f76610686be8:
Foundation37642993485 SUCCESS GCC sanitizers/MSVC; DX1137642993484 SUCCESS
full engine/checks/package/upload. Artifact11494387347 (190063170bytes),
`_build/gha/reconnect-c6525f885`: ZIP SHA256
`06731640e6c6f4f83303fa73a621bc9575971300e43050dc9f313cb2860019fe`;
both exe SHA256
`7E616CA2282D5FCAF162B9C140FE8A0B6F03EC645CFC46DEC242BC1F7BE677A9`.
Built-from/manifest/ZIP digest validated; missing third-party DLLs supplemented
only in the private probe from the previous verified runtime.

Private `_build/live/roundtrip-c6525f885`, two map servers/four bots in two
dedicated BelowNormal bot processes. Three-minute round-trip run: final4/4
playing,0terminal failures,2recovered admission timeouts,24departure records,
22arrival records. Two departures were still in flight near shutdown; do not
call all24 completed. Zero Lua/fatal/shader/save/refusal/lease errors.

All four inventories seeded before the first departure (log order checked),
each with2bandages/1bread plus the normal PDA. Native NCH7 snapshots captured
14/15/11/10 times per bot; all four retained section/count/nonzero UID identity.
This resolves the earlier late-seed fixture ambiguity for the tested scenario.

Stopped both servers and bots, then restarted the SAME saved worlds and
character files, without cleanup or additional seeding. Distinct log names
retain original logs. Private restart driver waits for a real level clock,
since 'loading saved world' alone announces loading before readiness.
Two-minute post-restart run: final4/4playing,0terminal/admission failures,
12departures/12arrivals,4server auth redirects correctly followed. Each bot
arrived on both maps in each phase. Eight further NCH7 snapshots per bot;
all four final inventories exactly match the pre-restart section/UID multiset
(four items each). No Lua/fatal/shader/save/refusal/lease errors.

World saves: before restart Marsh/Cordon bootstrap1/1,periodic8/4,
last-player-left3/3; after restart periodic6/3,last-player-left1/2, no new
bootstrap. Both logs confirm loading saved worlds. Test-only30s save period
did not change the production300s default.

Evidence: result.txt, restart-result.txt, phase1-server-logs/, phase1-bot-logs/,
inventory-history.json, restart-inventory-history.json, inventory-checks.json,
restart-inventory-checks.json and acceptance.json retained in the private root.
An initial combined restart-preparation command was rejected by auto-review
with only 'blocked by policy'; a safer variant retaining every file and using
distinct logs was accepted and completed. No permissions or safety settings
were changed. All probe processes stopped; debug channel empty.

Scope: four bots/two maps/basic inventory identity through handoff/restart.
No full item-condition/ammunition-state, all-map512, bad-network transition,
or graphical/max-view64 smoothness acceptance claimed. Main exes remain
unpromoted; primary script guards are installed as recorded in doc57.
