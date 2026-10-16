# Checkpoint response loss and idle expiry

Two defects found while reviewing M2b recovery prerequisites. Neither change activates native master-primary persistence or closes M2b.

## Native transport

`writer_request` used to retain HTTP status200 when a later body read timed out or failed. `CheckpointUpload`/`CheckpointDownload` classified that false result as Rejected instead of Retry. A complete but malformed response could also throw from `bridge_json` outside the checkpoint state machine's acknowledgement validation.

The writer now requires the master's bounded Content-Length, detects early EOF even when WinHTTP reports a successful zero-byte read, and returns transport status0 for interrupted/deadline reads. Repeated steps retain the exact begin/append/finish command ID. Complete malformed JSON, wrong envelope and oversized length are refused with status200 and no result; JSON validation exceptions do not escape the transport. Authority/version HTTP errors retain their original status and remain final refusals. No credentials or error bodies are exposed.

The existing CI-only actual C++ fixture now uses a real loopback socket proxy against the real HTTP master/SQLite. It truncates successful begin, append and finish replies after upstream commit. The previous artificial lost-response wrapper has been removed for uploads. The fixture reconstructs the cursor after a lost append, completes with exactly two total save revisions/events, and tests actual short response, receive timeout, malformed JSON, invalid envelope, over-budget declaration and subsequent successful response. Native compilation remains GitHub Actions only.

## Master staging expiry

Uploads previously expired120000ms after Begin irrespective of useful progress. A legitimate large upload scheduled between lease renewals and other players could fail despite every new chunk arriving within the idle allowance.

Only a newly accepted chunk now renews the120000ms staging idle deadline inside the same SQLite transaction. Begin/append idempotent replay and refused chunks cannot refresh it. Size/count/global staging limits, live location/session fencing and epoch checks are unchanged. Expired uploads cannot be resurrected by retry; a fresh authorized Begin reclaims their staging budget while retaining the last complete save.

Two new real SQLite tests cover a complete multi-chunk transfer lasting longer than its initial deadline with a continuously renewed location lease, and replay/refusal/idle expiry/reclamation with the previous durable checkpoint unchanged. The17 checkpoint backend tests pass locally. Full backend/Windows native/packaged master verification is pending CI for this source batch.

## Remaining

Bounded durable native worker spool, generation ordering, lease/session lifecycle, actual native admission/hydration and world/inventory/quest coordination remain OPEN. Old-epoch partial uploads still reject on master restart. Installed worlds, accounts, characters, private configuration, resources and owner binaries have not been changed by source verification. No game or location server was launched.
