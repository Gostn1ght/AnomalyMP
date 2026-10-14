# M2a: durable native checkpoint transport

Status: backend protocol implemented and verified without a game. M2b native runtime adapter and activation remain OPEN. Existing native .bin recovery and the live account/character workflow are not switched by this change. Do not call this primary game persistence already integrated.

## Bounded upload and atomic commit

Schema6 transactionally adds complete native_player_save checkpoints and transient native_player_upload/part tables, preserving schema5 migration archives. Upload requires a CHARACTER with stable WorldID/seed/account/slot ID, ACTIVE owned player session, current location lease/fence, session fence, entity version and expected checkpoint revision. Location credentials and runtime instance scope are checked by the existing loopback transport; observers and administrator credentials cannot call native save operations.

native_save_begin reserves at most20MiB for one slot, max32 simultaneous uploads and64MiB total. TTL120s; restart/new epoch, expired uploads and fenced owners release staging reservations on the next begin. native_save_append accepts exactly ordered30720-byte chunks except the final remainder, canonical base64, idempotent command IDs and bounded JSON under64KiB. Incomplete/corrupt/out-of-order/wrong-world/wrong-session/stale-writer data never replace the previous complete record.

native_save_finish assembles and validates bounded NCH3..9 bytes and CRC/SHA outside the world lock, then repeats authority/version checks and atomically commits the exact bytes, revision, protected character reference and journal hash under SQLite WAL/FULL. Durable acknowledgement comes after COMMIT. Retried finish returns its committed result while still enforcing current ownership/session. Two latest complete revisions are retained per character; consumers must not regress their cached head on an old command reply. Snapshots include complete saves within the existing128MiB budget, but omit transient uploads.

Generic entity-state updates and disconnect preserve the master-owned native_save reference and reject a forged reference. An unfinished upload blocks disconnect and transfer preparation until finish or explicit cancellation. Transfer's immutable entity state already captures the complete revision/SHA reference. The claimed destination can GET bounded chunks before activation, under target lease/fence and FROZEN session fence; this read does not grant writer rights. Commit grants the destination writer; source and old claims then fail. These operations do not fabricate runtime positions, task targets or item UID projections from opaque packets.

GET /v1/player-save takes character_id, fence, session_fence, revision, offset and optional claimed transfer_id. Responses are below64KiB, credential-free, owner scoped. Native engine must verify the complete returned SHA/format, restore a hidden actor, and keep it hidden until the transfer commits. Current C++ writer transport is still a prototype; M2b must integrate capture/chunks/read/lease renewal/recovery and coordinate native inventory/world commits. Account auth/admin/bans remain the existing engine responsibility. Runtime body death/respawn must not permanently kill the stable master character entity.

## Evidence and limits

317 backend tests pass locally, including actual HTTP chunk upload/read, SQLite durability/idempotence, slot/world/account scopes, wrong session/fence/version, partial/corrupt data, stale writer takeover, restart, metadata retention, bounded history, snapshot inclusion, reservation limits and claimed handoff read before activation. Native .bin/player worlds and private installed master DBs are unchanged. New CI/package still needs to pass after this batch. Real GAMMA quests/traders and cross-location reward-once remain M3; abstract/protocol tests do not close those stages.

## Additional common-input/source fixes in this batch

Ctrl+Left at column0 or an all-space field read m_edit_str[-1]. Guarded before access; real editor regression runs with AddressSanitizer/UBSan in Linux CI. Edit repeat is reset on mouse/programmatic focus, focus loss, commit/tab/cancel while draft text stays intact. Inventory configuration is read once per process, rather than during every UI/pickup/trade check; edits require a process restart. Lua inventory slots return a primitive LPCSTR instead of xr_string with a custom allocator, and the helper refuses non-string responses. No game window is launched for verification.
