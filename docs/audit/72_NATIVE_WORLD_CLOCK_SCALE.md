# 72. Native WorldClock positive-scale continuity

2026-10-08, Codex. B01 accepted for its original portable local core contract.
Distributed ClockSync, location follower adoption and global scale barriers
remain separate requirements; this does not close B02/B09/B10/B12/B13.

Same validated GHA171 executable/package as doc71. Foundation37759512127
passes actual WorldClock/ALife adapter fixtures on GCC/sanitizers and MSVC;
DX1137759512199 SUCCESS. Those core fixtures cover continuous scale mutation,
monotonic-read regression rejection, restore fencing and bounded overflow.
No local native compilation.

Actual dedicated server restores the retained PRIVATE authority-test world;
owner/primary data never used. GUID-correlated native Lua calls use existing
`level.set_time_factor` and `game.get_game_time` APIs, which feed the actual
ALife-backed WorldClock. Positive scales6→12→3→1→6 are observed at runtime.
Each immediate calendar delta before/after the setter is zero, without a
backward step. Each independent delayed sample measures both the device
monotonic interval and the resulting game-calendar interval:

- Factor6:8006ms real,48.035999s game; expected48.036s.
- Factor12:8013ms real,96.120003s game; expected96.156s.
- Factor3:8258ms real,24.771000s game; expected24.774s.
- Factor1:8012ms real,8.012000s game; expected8.012s.
- Restored factor6:8011ms real,48.071999s game; expected48.066s.

All five current native scale reads match the selected factor. Greatest
observed discrepancy from device interval*scale is about36ms. This is a
sampled native integration result, not a claimed perfect packet-clock
measurement; deterministic core/overflow continuity remains covered by
actual native fixtures. Dates converted to absolute milliseconds progress
1540541731146→1540541952251, far beyond32-bit range. No pause/zero factor,
calendar jump, player speed change, AI-cadence change or visible NPC claim.
Factor6 is restored before shutdown. Test changes only a private world.

`_build/live/authority-native-171473a99/clock-acceptance.json` retains all
observations/source and sealed pre-stop log SHA256
`807580c094d048169da2db5186c0b6a3470f4f2af5bd0da0a755eda1ce6d5b4c`.
The controller rejects actual native exit/exception, SCRIPT ERROR, failed
handlers and caught debug-command errors. None occur. Existing NPC-loadout
diagnostics remain separate and must not be described as a clean modpack.
Server stopped, shared debug empty, all88 primary fingerprints unchanged.

Current188 counters:26 accepted,34 code/fixtures,69 partial,59 untouched;
162 remain not fully closed. B01 is the local portable core, not a claim
that a distributed World Service/clock network adapter is complete.
