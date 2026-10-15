# Native checkpoint client, M2b preparation

Owner: continue without launching game/location servers. Previous installed version remains native356/master356 + encrypted patch000019. No private installed world, account or character files changed by this source batch.

## Implemented boundary

Private exception-enabled worker header netcoop_player_checkpoint.h builds on the existing loopback WinHTTP writer. It contains no engine pointers, Lua API, private config or gameplay activation. Native caller integration and primary persistence switch remain OPEN.

- Stable player ID exactly matches Python UUID5(namespace URL, WorldID/seed/lowercase ASCII account/slot). World/seed span uint64; account3..20 ASCII letters/digits/_.-; slot1..10. Windows CNG supplies SHA1 UUID5 and SHA256, with hash object storage retained until its handle is destroyed.
- Canonical binary-safe base64, strict padding bits/length/budgets. Snapshot limit20MiB, wire chunks30720 bytes, serialized request under64KiB.
- Upload takes an immutable serialized NCH3..9 snapshot, stable character ID, current location/session fences, entity CAS version, expected save revision, slot and caller-persisted128-bit transaction ID. One HTTP request per step leaves scheduling/lease renewal to the worker. Begin/append/finish command IDs are derived from that transaction, operation and byte offset; lost successful replies retry the same command instead of creating another write.
- Only an exact durable acknowledgement for character/revision/version/size/SHA completes upload. Timeout/408/429/5xx are retryable; authority/version/admission failures reject. No implicit takeover, new entity or inventory mutation.
- Cursor binds the immutable snapshot SHA/size, character, slot, location/session fences, versions and transaction. Wrong-snapshot cursors and impossible offsets/phases reject before mutation. Restoring even a completed cursor replays Finish under current server authority; local cursor bytes never count as proof of commit. Caller must persist snapshot/transaction/cursor atomically and preserve instance/epoch rules; this header does not implement that disk queue.
- Download pins protected revision/SHA/size and optional immutable transfer claim, verifies every page's offsets/length/metadata/canonical encoding and the final complete SHA. Partial/corrupt data cannot be accessed through bytes(). Complete checksum failure seals the read as rejected. Actual native CSE/UID/quest restore validation remains mandatory after download.

## Verification

Extended existing CI-only actual C++ writer fixture, without local compilation: Python UUID/hash reference vectors including max uint64 and uppercase account; binary codec/padding budgets; valid complete NCH9 against actual HTTP master/SQLite; lost successful begin/append/finish replies; cursor serialization/reconstruction after lost append; forged cursor rejection; completed cursor replay; exact download after a lost response; altered metadata and final-byte corruption; two complete revisions and exactly two commit events. Native compilation and actual WinHTTP checks await CI for this batch.

This closes no live M2b acceptance criterion yet. Remaining work: bounded durable per-player worker queue and lease/session lifecycle, actual native capture/admission/hydration, inventory/world/quest commit coordination, shutdown/restart recovery and primary-source activation. M3 actual GAMMA quest handoff/reward-once also remains OPEN. No new resource patch is needed for this private transport source alone.

A committed retry proves that transaction's immutable snapshot, not that it is still the latest head. The integrating worker must publish heads monotonically and associate handoff/release with the newest captured generation. Old successful responses must never regress a newer durable revision. No disk cursor, entity activation, lease takeover or head publication is implemented by this helper itself.
