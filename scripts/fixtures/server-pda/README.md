# GAMMA PDA regression reference

Copied 2026-10-07 from the owner's prepared GAMMA server runtime:
`server/scripts/pda.script` (`discover_spots`, line 654 to EOF) and
`server/scripts/_g.script` (`local ev_queue` through `ProcessEventQueue`).
No rewritten simulation of the timer: the test executes these original
functions with Lua 5.1 and substitutes only engine APIs. LF normalization;
hashes are pinned in the test. These references reproduce the empty-server
nil-actor exception before applying the actual PowerShell installer helper.

Scope: PDA spots are a local-player action. This change does not disable
world timers, mutate population or change discovery when an actor exists.
