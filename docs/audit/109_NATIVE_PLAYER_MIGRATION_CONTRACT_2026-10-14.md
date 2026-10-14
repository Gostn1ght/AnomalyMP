# M1: native player save contract and staged master import

## Identity and authority boundary

A character is bound by explicit WorldID + world seed + normalized authenticated account + slot (1..10). Stable ID is UUID5 of that tuple. The NCH file contains none of WorldID, seed, account, slot, location lease, session fence or complete player commit revision. The operator supplies the world/location binding; filenames supply account/slot. Storage revision applies to the inventory/safe transaction only, never to a full player commit. Multiple location copies with different contents cause a conflict rather than guessing which is newest.

The staging table is not a live character, inventory ledger or player session. Existing native .bin files remain the live recovery source. M2 must integrate authoritative native capture/restore, trusted location lease and session fencing, an idempotent complete commit revision, transfer checkpoints and durable acknowledgement. No client sends saves to this importer.

## Exact byte contract

Native NCH3..8: bounded zero-terminated CP1251 metadata (name63/faction32/loadout4096, description512/history1536 since5), economy byte, initialized/respawn bool bytes; actor NET_Packet; up to512 hierarchical inventory items; progress since4; safe/storage transaction metadata since6; item state since7. Parent is one-based previous-item index, 0=root. Version3 omits place and progress. Each packet has LE u32 length + checksum + payload, max16384 bytes (src/xrCore/net_utils.h). Progress max1MiB. Item state LE u16 length, max512 bytes. Strict EOF.

Native CRC32C uses polynomial82f63b78, initialffffffff, no final XOR (SSE4.2 convention). NCH3..7 also permit legacy IEEE CRC32 with final XOR. NCH8 permits only CRC32C, independently of CPU. Opaque actor/progress/spawn/item-state packets are preserved exactly, including native UID, cartridge sequence, condition/upgrades and task/info/Lua/origin data. Their semantic layout is validated by the future matching native adapter, not fabricated by the importer. Optional known-section validation is available to callers; the CLI stages bytes without claiming engine section/restore compatibility.

## Offline import

`LostZoneMaster.exe player-migration --config <private config.json> --source <stopped location appdata> --location <configured location> --world-id <id> --seed <seed>` defaults to read-only validation. It never opens/creates SQLite in dry-run. `--commit-import` requires an already initialized offline master DB, acquires its exclusive process lock and atomically archives the entire validated batch in schema5 native_player_import. Existing identical slots are idempotent; changed slots/world/location refuse the entire batch. No source file/config/token/account/world is deleted or replaced. Live authority and world epoch are unchanged.

Exact original bytes are stored as base64 plus SHA256 and bounded structural summary. The verified read checks checksum/format/identity/summary. Backend snapshots include the archive under their existing byte budget. Schema4→5 is a transactional additive migration preserving world/entities/items/quests. No production DB is migrated during this task; tests use private temporary DBs.

Admission is bounded per file20MiB, batch64MiB,1024 slots. Only final top-level netcoop_character_*.bin files are read; temporary saves are excluded. Changes observed during scan fail closed. Native locations must be stopped before a committed migration; the OS DB lock alone cannot stop native .bin writers.

## Verification

Read-only validation of four existing local test/server NCH8 files succeeded without printing names, raw state or credentials. Tests cover all six legacy versions and checksum conventions, every truncation boundary, corrupt CRC, forward/cyclic parents, unsupported formats, empty/bounded opaque packets, exact bytes, identity scopes, unavailable sections, idempotence, whole-batch rollback after a conflicting second slot, source preservation, running-master exclusion, schema upgrade, snapshot inclusion, archive corruption and dry-run secrecy. Packaged EXE regression performs dry-run + SQLite staging + byte-for-byte verification without external Python. CI results are recorded after the new artifact is built.

M1 staging is implemented. M2 primary player persistence and M3 actual GAMMA quest integration remain open.
