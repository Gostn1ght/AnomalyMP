# Native checkpoint transport and patch 000017

Owner steering: continue without starting the game or location servers.

## Verified build and deployment

DX11 CI 38598502459 / source 356e5b4bd6226f6c12aac6952fc461e41280ebfe succeeded, including actual keyboard/editor regressions, native inventory capacity/map checks and matching client/server build. World backend CI 38598502488 succeeded: 317 tests on Linux/Windows and packaged standalone master checks. Downloaded Master EXE SHA256 f2201afed085c2501672285d56c58424fd10cfeaec852b147ff30f918a436e3c also passed three actual local EXE tests. None of these results certify graphical/game acceptance.

Patch 000017 pins source 356e5b4bd, includes the prior fixes plus input, mutual-friend map display, late trader profile refresh, New Way PDA resources, binocular grip and gear-dependent inventory cells. Do not rebuild or reuse this number. Owner binary quarantined by Malwarebytes remains absent; deployment must skip all owner binaries. Private installed config/world/account data must remain byte-identical.

## M2b preparation, not activation

The private C++ WinHTTP writer now allows the four native_save operations, session disconnect/resume and player-save reads. Checkpoint reads require the same-request world/seed/authority-epoch header. Payloads are bounded to the HTTP master's actual 64KiB body limit. Existing loopback-only/no-redirect/no-proxy transport, credential isolation, current-writer/session checks and 2-second per-request deadline remain.

CI-only actual C++ writer regression sends a valid multi-chunk NCH9 fixture through the real Python HTTP master: cancel/restart upload, stale-instance rejection, incomplete finish rejection, disconnect blocked during upload, durable finish/replay, exact chunk reads, disconnect/resume fence changes and claimed-destination read before transfer commit. It verifies unchanged bytes in SQLite, and rejection of the old source after commit. Administrative commands remain unavailable to the native location writer.

CI38764210368 succeeded completely for53791bfac: native Windows fixtures including the actual WinHTTP regression, full DX11 engine build and artifact packaging/upload. World backend CI38764210620 also succeeded. Native537 transport remains preparation, not live primary-save activation; installed game binaries remain verified356 with patch19 resources. The next source push was held until this build completed, so it was not cancelled.

Patch000017 and verified native356 were installed into the friend overlay and srvtest without launching them. Owner received resources only; every owner binary remained unchanged and the quarantined client EXE remained absent. Native client/server SHA256133c501108032a0051188fbac2e6d61120236754a614975315f6ff7a784954c9. Master356 and exact committed fallback Python sources installed together. All pre-existing account/appdata/key/private-runtime files were fingerprinted before/after and remained byte-identical. Changed files50; public addon manifest6866 entries. Backup `J:\LostZone_Work\_work\before_remote_fixes_000017_20261015_190752`. Both encrypted archives passed authenticated verification. Distribution HTTP8787 was restarted and returned200; its existing published release was unchanged.

No live character capture/restore/session adapter is enabled by this header change. Stable native identity, admission/hydration, queued worker lifecycle, recovery and inventory/quest commit coordination remain required before M2b can close. M3 actual GAMMA tasks/reward-once remains OPEN. Launcher publication is unchanged and still requires owner approval.
