# Server-approved observer consumption animations

Native implementation, with game acceptance pending under the owner's no-game constraint.

`CInventory::Eat` already invokes `server_item_used` only after successful authoritative `UseBy` and before deleting an emptied item. That hook now emits a small server-to-client presentation message. Classification uses the actual resolved GAMMA item kind: medical/bandage/antirad, drink/alcohol, food/raw/cooked meat. Tools, money/bolts and unrelated item kinds do not become eating actions.

`netcoop_consumption.h` contains a fixed six-motion vocabulary, bounded numeric parser and classification. Script messages carry actorID, action kind and exact runtime actor name; a missing/mismatched object is ignored. No client-selected motion name, item action, new wire opcode, generic animation request or additional item use is added. Existing clients ignore the previously unknown channel.

On observing clients `CActor::netcoop_play_consumption` plays an actual existing `banka_anim_use_*` clip, once, restricted to the model's named torso partition. Legs/head retain their existing animation handling. The owner's first-person scripts/effects, gameplay input, inventory and consumption result remain independent. Missing clips/models/partitions, invalid kinds, server execution, owner actor, occupied vehicle seats and active whole-body RP actions are safely ignored; seat/RP visuals keep priority. Visible medical/food props are not newly attached by this batch.

The existing torso-animation latch holds the one-shot through normal actor animation updates. A guarded callback clears only its current blend; a bounded deadline also releases it after a missing callback, death, seating or RP interruption, including timer wrap. Spawn resets the transient field; it is not saved as player state.

`check-native-consumption-animation.py` parses the real shipped merged OMF before compilation and confirms all six clips and legs/torso/head partitions. In GitHub Actions it executes the actual observer methods against renderer boundaries, checking server/owner exclusion, finite-speed validation, one-shot torso routing, callbacks, expiry/wrap, missing assets, action classification and malformed payloads. It also verifies that the server notification remains after successful use and before item removal. No native compilation runs locally.

Exact timing, hand attachment visuals, all actor outfit skeletons and multiplayer gameplay still require game acceptance. This implementation does not close those checks from fixtures alone.

Verified2026-10-16: combined run38853207613 for3eb197b79 succeeded completely: shipped OMF parsing, real native observer methods and bounded vocabulary, Linux checks, full DX11 engine build and artifact upload. This supersedes the preceding failed compilation in doc124. Distribution waits for the additional skeleton history build; game acceptance remains open.
