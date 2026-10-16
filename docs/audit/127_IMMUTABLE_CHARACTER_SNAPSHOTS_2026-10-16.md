# Immutable NCH snapshots and background file IO

The production autosave path previously opened, serialized, flushed and closed its temporary NCH file on the simulation thread. The worker only reopened it for fsync/rename. Moving the durable completion alone therefore left ordinary filesystem stalls in the game/AI loop.

`character_snapshot` now creates a complete owned NCH9 byte image without filesystem calls. Its first pass validates/counts before allocating one image; the second fills it and calculates the original CPU-portable packet/progress checksums. Metadata limits, embedded NUL rejection, backward-only inventory parents, packet/state/progress limits and the20MiB transport budget are checked before admission. Oversized item state is refused rather than silently truncated to512 bytes. NCH3..9 loading and valid NCH9 output bytes are unchanged.

The actual existing commit queue now owns these images. Autosave performs no file open/write/flush/delete. The worker creates the process/sequence-specific temporary file, writes the image, fsyncs and atomically replaces the previous durable save. Failed open/short write/flush/rename cannot replace the prior file. Queue admission is still bounded to256 pending entries and32MiB of payload including in-flight work, plus one producer image bounded to20MiB. A queued same-character image may be superseded only as a whole; in-flight data cannot be replaced. Payload buffers are transferred instead of copied: default emplacement plus swap avoids the legacy engine allocator's copy-only `construct(const T&)` trap.

Synchronous character operations still wait for their own path's earlier writes and then require durable file success. Account admission/global shutdown barriers retain their existing scopes. Background admission is pending work, not a durable acknowledgement. Existing background write-error logging/policy remains; this batch does not introduce durable crash-recovery of queued memory or remove required logout/handoff waits.

The unchanged fixtures are expanded in their existing CI workflow steps:

- Actual NCH serializer/save/reader against independent Python golden byte images for upgrades from all seven supported versions, both CPU CRC paths and the actual master decoder.
- Producer-side file-open trap, immutable queued actor/item/progress/profile bytes after source mutation, refused admission without a false save timestamp, malformed/oversized state rejection and preservation of the existing durable file.
- Actual bounded queue with an allocator that has the engine's copy-only construction behavior; pointer ownership across enqueue/take, replacement/in-flight accounting, per-character barriers, byte/count exhaustion and real producer/consumer contention.
- Actual Windows commit bodies with failed open, short write without ferror, failed fsync/rename, successful completion and cleanup while retaining the previous durable file.

Only fixture generation and Python decoding run locally; native fixtures and the full engine compile run exclusively in GitHub Actions. No existing game save/config/database is used as a test input or rewritten.

This makes the live local autosave path independent of producer filesystem writes and provides the immutable snapshot boundary needed by the existing master checkpoint uploader. M2b master-primary activation is **not** enabled: a writable location/session lifecycle, durable checkpoint queue and acknowledgment, admission/hydration, recovery and handoff coordination remain required. M3 and H09/H11 remain open. Game/TPS acceptance is separate; no game/location server is launched.

Verified: complete DX11 run38858420380 succeeded for70d5f1721a9b24ab0ce36897b43430e29459fe14, including both expanded actual native fixtures and full engine compilation/artifact upload. Initial run38858089278 stopped on the inventory-capacity fixture's old assertion for direct `fwrite`; it was updated to track the same capacity field in the memory serializer, then the entire workflow was rerun. Installed binary hashes, backup and complete6872-file verification are in doc128.
