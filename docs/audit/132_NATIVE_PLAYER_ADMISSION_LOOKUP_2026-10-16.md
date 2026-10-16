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

Local complete backend suite: 338 tests passed, including 14 new SQLite slot tests, two new HTTP tests and one new master-entry test. Native engine compilation and standalone EXE packaging are not run locally. Linux/Windows CI and the packaged Windows master verification are pending for this source batch.

Full DCP cars/physics and helicopter adaptation T2–T9, M3 actual GAMMA quest/reward coordination and H09/H11 native NPC/item transfer remain OPEN.
