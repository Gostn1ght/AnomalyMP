# Native player slot lookup — M2b subtask

The future native admission coordinator needs current character/session/entity/checkpoint versions for one account and slot before deciding which explicit operation to perform. A bounded read-only `GET /v1/player-admission` endpoint supplies that observation without fetching the entire location registry or an opaque NCH payload.

## Contract and limits

Only authenticated location authorities may call it. Both runtime-instance and expected world/seed/master-epoch headers are mandatory on this endpoint. Exactly five single-valued query fields are accepted: `account`, `slot`, `location`, `fence`, `epoch`. Query length is at most 1024 characters; canonical positive integer syntax, native account/slot bounds and the server credential's map allowlist are checked. The requested location must have a live lease under the exact requesting runtime actor/fence, including for a missing character. The query epoch must still match the current master.

`PlayerSaves.inspect` holds the existing store lock through all reads, so concurrent commands cannot mix entity/session/head versions. Native account names are canonicalized to lower case and IDs use the existing WorldID/seed/account/slot identity. Another ACTIVE/FROZEN character of the same account blocks the observation, including mixed-case older registry accounts.

The compact schema1 result contains scope, canonical account/slot/character ID, entity version, session fence and the latest durable checkpoint's revision/SHA256/byte count. It never returns arbitrary entity state, behavior, tasks, inventory packets, credentials, transfer tickets or checkpoint payloads. Entity JSON is read with a bound and checked against the durable head; malformed/dangling/mismatched references fail closed. The endpoint does not decode or revalidate the complete NCH payload; actual hydration must read exact revision bytes through the existing authorized checkpoint protocol and verify them before instantiation.

Statuses are `ABSENT` (no live entity or staged slot), `STAGED` (offline import exists but no live entity), `ACTIVE` and `DISCONNECTED`. STAGED is never offered as a new empty slot. Dead, frozen, transit, stale-owner, incomplete-upload and unactivated-import states refuse inspection. Even an expired upload requires explicit reconciliation/cancellation: GET never erases it or silently selects an older checkpoint. A committed live head takes precedence over the old import archive's location after a legitimate transfer. Foreign/inconsistent archive identity refuses lookup.

This is an observation, not admission, a reservation or authority to spawn. Repeating GET cannot create/resume/disconnect/move a character, change a lease, cancel an upload or mint item IDs. Future commands must still verify their own current fences/CAS and coordinator generation barriers. ACTIVE is not permission to attach a second connection. ABSENT is not permission to reroll an unresolved local character. Production native admission/hydration and primary persistence remain disabled and M2b remains OPEN.

## Verification

Actual SQLite tests cover no mutations, native identity/case, compact exact field set, no payload SQL/decoding, newest durable head, disconnect/resume, other active/frozen slots, incomplete/expired uploads, dead characters, staged archive distinction and identity errors, malformed/reference corruption, stale authority, takeover/recovery and transfer before/after commit. A concurrent upload is blocked while inspection holds one coherent read cut.

Actual HTTP tests cover the lifecycle, missing runtime/world binding, wrong instance/world/epoch/fence/map, role/auth checks, readiness, extra/missing/duplicate/oversized/malformed query fields and refusal without mutation. The master entry test runs this HTTP/save/disconnect/resume/replay flow against a separately launched master in a temporary private world. The backend CI also reruns it against the actual packaged standalone Windows EXE. No game client/location server or installed private world is used.

Local complete backend suite: 338 tests passed, including 14 new SQLite slot tests, two new HTTP tests and one new master-entry test. [Backend CI38918042806](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38918042806) fully succeeded for `3b3dead2386d08698cd3c2f17bd3635047bde110`: 338 tests on Linux, 338 on Windows, standalone master packaging, four master-entry tests against the actual packaged EXE (including the new admission lifecycle) and hoster/private-config/process lifecycle checks. Native engine compilation and standalone EXE packaging are not run locally.

## Reviewed master release

Downloaded and CRC/length/source-receipt verified all three packaged entries to `J:\LostZone_Work\_work\ci_master_3b3dead23`. Master EXE SHA256: `29c2f6369f983a4ccb958d6eeb090955ee3446b08cc6454c5d89e838b4c21a0a`.

The downloaded EXE passed the new admission HTTP test locally in a separate temporary private world: ABSENT, pending-upload refusal, durable commit/replay, exact native read, DISCONNECTED, resume and wrong runtime/world refusal. SQLite verified one character/session/save, exact native bytes, entity version4/session fence3 and only seven actual mutating command results despite repeated GETs. Separately, the existing-checkpoint QA read an actual existing NCH8 image (2142 bytes) without modifying its source, uploaded/read/replayed it through this EXE, disconnected/resumed and verified exact SQLite bytes with one commit. No game or location server was launched.

Installed the verified EXE/metadata and exact fallback sources to friend addon `J:\LostZone_Work\Lost Zone Server` and srvtest: 11 changed files including the public manifest. Backup: `J:\LostZone_Work\_work\before_master_3b3dead23_20261016_174813`. Existing destinations were moved before copying. Installer fingerprints confirmed private configuration, appdata, keys, worlds, accounts, character files and every owner binary unchanged. Owner client EXE remains absent after its earlier quarantine and was not restored.

Independent verification passed for all 6872 public file sizes/SHA256/exact file set, 66 unchanged native artifact copies and 50 exact fallback source copies. Both master source fields/run/receipt/hash agree with the installed EXE. Native engine `e474d398167c636f535fea5359cc3e5761a9c171` and resource patch000020 are retained. Launcher publication remains false; distribution HTTP8787 returned200; final game/location/installed-master process count0. The engine does not yet call the new endpoint; this completes the read-only lookup component, not native admission/hydration or primary-save activation.

Full DCP cars/physics and helicopter adaptation T2–T9, M3 actual GAMMA quest/reward coordination and H09/H11 native NPC/item transfer remain OPEN.
