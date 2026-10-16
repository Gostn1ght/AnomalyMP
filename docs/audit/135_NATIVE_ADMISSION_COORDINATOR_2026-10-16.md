# Native admission coordinator — M2b live path

Owner 2026-10-16: finish M2b (master-primary player persistence and admission), then M3, H09/H11 and DCP/helicopters, then publish. This document covers M2b.

## What runs now

`netcoop_admission.{h,cpp}` (exception-enabled, no engine headers) is the coordinator between a location server and the world master. `netcoop_admission.inc` connects it to the engine.

- **Start.** When the master is required (authority bridge or cluster plan) and the panel has written `netcoop_world_writer_<map>.json`, the coordinator reads `/v1/clock`, then claims the location lease (`location_claim`, retried until a previous owner's lease expires). It then adopts the location's records with `location_recover` and starts the existing `CheckpointWorker`, which renews the lease. Without a writer config nothing changes: local character files only.
- **Login.** `finish_auth` keeps the login pending (role none, player state deferred) while the coordinator inspects the slot. Outcomes:
  - **ABSENT:** `entity_create` CHARACTER. The local file becomes the first checkpoint through an immediate capture.
  - **DISCONNECTED:** `session_resume`.
  - **ACTIVE:** after this location's own restart and recovery, continue with the master's versions.
  - **Refused:** a 409 from inspect (active elsewhere, in transit, unfinished upload) or a failed command refuses the login with a reason.
  - **STAGED** and a master that never answered fall back to local-only admission with a log line. The world-master gate still refuses players while the master is unavailable.

  If the master's durable checkpoint SHA-256 differs from the local file, its bytes are downloaded (`CheckpointDownload`). They replace the local file atomically; the old one is kept as `.before_master`. The file is re-read before spawning. If it is unreadable here, the old file is restored and the login is refused.
- **Saves.** `character_save` passes every complete NCH image of an admitted character to `capture` (the same bytes as the local file). Captures chain entity version and revision by one each, as `CheckpointOutbox` requires. The coordinator releases each durable capture; the worker sends one character's captures in order and keeps a durable one until it is released.
- **Logout.** After the final local save, `leave` waits until the newest capture is durable, then sends `session_disconnect`.
- **Level changer.** `cluster_move` saves the destination image as before, then `depart` waits until it is durable and calls `transfer_prepare`. The redirect is sent only after the master returns the token. The token goes to `cluster/mtoken_<login>_<slot>`. The target's login reads it, runs `transfer_claim` and `transfer_commit`, inspects the slot (now ACTIVE there) and downloads the image if it differs. A refused departure undoes the passage: the ticket is deleted, the player is unfrozen and saved in place, and the player sees the reason.
- **Spool.** Each run uses its own folder `netcoop_checkpoint_spool_<map>\run_<fence>_<instance>`, and older run folders are deleted at start. The outbox is bound to its process instance, so an old folder could never be reopened. Every capture is a complete image of the newer local file, so nothing is lost.

## Master change

`location_recover` deletes `native_player_upload` rows of that location written under an older fence. Such an upload can never be appended or finished (each step checks the current fence). Left behind by a crashed server, it blocked the character's inspection, disconnect and handoff forever. A live upload of the current owner survives a repeated recovery. There is a new backend test, and the full backend suite passed locally with 339 tests.

## Verification

`scripts/check-native-admission.py` (Windows CI, DX11 and World Foundation native steps) compiles the actual coordinator and checkpoint worker and runs them against a real in-process master with two location writers. The scenario:

1. Register a character.
2. Make two durable captures.
3. Leave.
4. Resume with a stale local file: the master's newer image comes back.
5. Resume with an identical file: no download.
6. Log in at another location while ACTIVE: refused.
7. Capture, then depart, get the token, and claim it at the target: the newest image arrives.
8. The source refuses the character afterwards; leave the target.

The database then holds one character, at Garbage, DISCONNECTED, with no pending upload; the newest checkpoint equals the last capture and there is one TransferCommitted event. This passed locally against the real master. Updated fixtures:

- `check-native-open-registration.py`: `finish_auth` is now bool.
- `check-netcoop-character-checksum.py` and `check-netcoop-character-commits.py`: capture hook stub.
- `check-netcoop-player-transfer.py`: admission stubs; the departure state is unused without a writer.

All four passed locally.

## Not yet accepted

- No live game run yet: two locations on the srvtest cluster, the owner's and a friend's client, a level changer, server restart and crash recovery.
- A capture rejected by the master (version conflict) leaves later captures rejected until the next login. The local file stays correct and the next admission resumes from the master's durable head.
- A crash with an upload in flight under the same fence still needs the old upload to expire; the master's `native_save_begin` cleans it.
- Characters transferred across machines need the token file in a shared cluster folder. The current cluster runs on one machine.

## Live stand, installation, release (2026-10-16 evening)

- Stand `J:\LostZone_Work\_work\m2btest` (own master, own appdata; owner data untouched): DX11 `c3acff438` (CI 38938209969) Cordon + Garbage with `-netcoop_cluster_selftest`, 4 headless bots for 6 min. Both locations took their leases. 16 logins admitted by the master, 12 handoffs through master tokens in both directions, 0 refusals, no errors. Master DB: 4 characters, 12 COMMITTED transfers. The hard stop left one PREPARED transfer, which the new master aborts on the source's next renewal (`e3fcbf1f1`, test added).
- Installed: native `c3acff438` into the friend kit and srvtest (backup `before_native_c3acff438_20261016_205933`) and the owner's client exe (same SHA). Master `e3fcbf1f1` (backend CI 38943768059, packaged checkpoint QA on an existing NCH8 passed) into the kit and srvtest (backup `before_master_e3fcbf1f1_20261016_210306`). Independent verification: 6872 manifest files, 66 native and 50 master copies, pins agree.
- Published to the launcher: client `2026.10.16.1` (55.7 MB new data), owner-approved. Distribution server running.
- Still open for M2b: a live game with real clients (owner/friend), server crash/restart during play.
