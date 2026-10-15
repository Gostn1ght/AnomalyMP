# Native checkpoint transport and patch 000017

Owner steering: continue without starting the game or location servers.

## Verified build, before deployment

DX11 CI 38598502459 / source 356e5b4bd6226f6c12aac6952fc461e41280ebfe succeeded, including actual keyboard/editor regressions, native inventory capacity/map checks and matching client/server build. World backend CI 38598502488 succeeded: 317 tests on Linux/Windows and packaged standalone master checks. Downloaded Master EXE SHA256 f2201afed085c2501672285d56c58424fd10cfeaec852b147ff30f918a436e3c also passed three actual local EXE tests. None of these results certify graphical/game acceptance.

Patch 000017 pins source 356e5b4bd, includes the prior fixes plus input, mutual-friend map display, late trader profile refresh, New Way PDA resources, binocular grip and gear-dependent inventory cells. Do not rebuild or reuse this number. Owner binary quarantined by Malwarebytes remains absent; deployment must skip all owner binaries. Private installed config/world/account data must remain byte-identical.

## M2b preparation, not activation

The private C++ WinHTTP writer now allows the four native_save operations, session disconnect/resume and player-save reads. Checkpoint reads require the same-request world/seed/authority-epoch header. Payloads are bounded to the HTTP master's actual 64KiB body limit. Existing loopback-only/no-redirect/no-proxy transport, credential isolation, current-writer/session checks and 2-second per-request deadline remain.

CI-only actual C++ writer regression now sends a valid multi-chunk NCH9 fixture through the real Python HTTP master: cancel/restart upload, stale-instance rejection, incomplete finish rejection, disconnect blocked during upload, durable finish/replay, exact chunk reads, disconnect/resume fence changes and claimed-destination read before transfer commit. It verifies unchanged bytes in SQLite, and rejection of the old source after commit. Administrative commands remain unavailable to the native location writer. This is the next native CI check, not yet a pass.

No live character capture/restore/session adapter is enabled by this header change. Stable native identity, admission/hydration, queued worker lifecycle, recovery and inventory/quest commit coordination remain required before M2b can close. M3 actual GAMMA tasks/reward-once remains OPEN. Launcher publication is unchanged and still requires owner approval.
