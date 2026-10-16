# Checkpoint response loss and idle expiry

Two defects found while reviewing M2b recovery prerequisites. Neither change activates native master-primary persistence or closes M2b.

## Native transport

`writer_request` used to retain HTTP status200 when a later body read timed out or failed. `CheckpointUpload`/`CheckpointDownload` classified that false result as Rejected instead of Retry. A complete but malformed response could also throw from `bridge_json` outside the checkpoint state machine's acknowledgement validation.

The writer now requires the master's bounded Content-Length, detects early EOF even when WinHTTP reports a successful zero-byte read, and returns transport status0 for interrupted/deadline reads. Repeated steps retain the exact begin/append/finish command ID. Complete malformed JSON, wrong envelope and oversized length are refused with status200 and no result; JSON validation exceptions do not escape the transport. Authority/version HTTP errors retain their original status and remain final refusals. No credentials or error bodies are exposed.

The existing CI-only actual C++ fixture now uses a real loopback socket proxy against the real HTTP master/SQLite. It truncates successful begin, append and finish replies after upstream commit. The previous artificial lost-response wrapper has been removed for uploads. The fixture reconstructs the cursor after a lost append, completes with exactly two total save revisions/events, and tests actual short response, receive timeout, malformed JSON, invalid envelope, over-budget declaration and subsequent successful response. Native compilation remains GitHub Actions only.

## Master staging expiry

Uploads previously expired120000ms after Begin irrespective of useful progress. A legitimate large upload scheduled between lease renewals and other players could fail despite every new chunk arriving within the idle allowance.

Only a newly accepted chunk now renews the120000ms staging idle deadline inside the same SQLite transaction. Begin/append idempotent replay and refused chunks cannot refresh it. Size/count/global staging limits, live location/session fencing and epoch checks are unchanged. Expired uploads cannot be resurrected by retry; a fresh authorized Begin reclaims their staging budget while retaining the last complete save.

Two new real SQLite tests cover a complete multi-chunk transfer lasting longer than its initial deadline with a continuously renewed location lease, and replay/refusal/idle expiry/reclamation with the previous durable checkpoint unchanged. All321 backend tests, including17 checkpoint tests, passed locally and in CI on Linux/Windows. [Master CI38862496180](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38862496180) completed successfully for97ae0069c04f4585249c6bd012361a6ddbba52fa, including the packaged EXE/SQLite and actual hoster lifecycle checks. [DX11 CI38862496224](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38862496224) also completed successfully: actual Windows WinHTTP response faults/upload recovery, all other native fixtures, full engine compilation and artifact upload. World Foundation CI38862496199 passed too. No local native compilation was performed.

## Remaining

Bounded durable native worker spool, generation ordering, lease/session lifecycle, actual native admission/hydration and world/inventory/quest coordination remain OPEN. Old-epoch partial uploads still reject on master restart. Installed worlds, accounts, characters, private configuration, resources and owner binaries have not been changed by source verification. No game or location server was launched.

## Verified master installation

Master artifact source97ae0069c04f4585249c6bd012361a6ddbba52fa / CI38862496180, SHA256 `5013d13b54d9f146f88c26405b403dfd6648163354678a32c5b0d6314ee04c86`. Downloaded three artifact entries checked against archive CRC/length, exact built-from and checksum metadata. Independent local packaged EXE test uploaded/read an existing read-only NCH8 checkpoint2142bytes in a temporary isolated world, replayed Finish once, disconnected/resumed and checked exact SQLite bytes; the source checkpoint was unchanged. The isolated process stopped cleanly; no installed world was launched.

Installed EXE/metadata and exact fallback Python sources to friend addon and srvtest. Backup `J:\LostZone_Work\_work\before_master_97ae0069c_20261016_094445`, nine changed files including manifest. Installer now preflights existing patch/master pins before mutation and updates both master source fields consistently. Post-install independent verifier matched all6872 public files,66 existing native copies and50 fallback source copies against their exact artifact/commit; retained native70d5f1721 and resource patch000020 at this intermediate point. Private data and all owner binaries were fingerprinted unchanged, publication false, game/location/installed-master process count0, distribution HTTP8787 status200.

## Verified native installation

Downloaded45 deployable entries from the successful exact-source DX11 artifact, checked archive CRC/length and built-from receipt. Client/server EXEs independently match SHA256 `deee21a087c59668654da036a1f8cad2ced6378d62fd50a34865e1e049e72827`. Artifact directory `J:\LostZone_Work\_work\ci_97ae0069c`. Installed addon bin/dedicated and srvtest dedicated; four changed files including manifest, backup `J:\LostZone_Work\_work\before_native_97ae0069c_20261016_100503`. Existing destination files were moved before copy to preserve hardlink peers. All owner binaries/private runtime/account/character/world files remain unchanged. Retained master97ae0069c and patch000020; no new resource patch is needed for these transport/backend-only changes.

Final independent verification with both native/master pinned to full97ae0069c04f4585249c6bd012361a6ddbba52fa passed: all6872 public file sizes/SHA256/exact file set,66 native artifact copies,50 exact fallback source copies, master artifact/receipt hash, both master source fields, engine/CI/resource pins and all four installed patch20 archives. Public manifest contains no private runtime/key/account/world files; launcher publication remains false. Owner client EXE remains absent after the earlier quarantine and was not restored. Game/location/installed-master process count0, distribution HTTP8787 returned200. M2b/M3/H09/H11 and full DCP/helicopter adaptation remain OPEN; no game acceptance is claimed.
