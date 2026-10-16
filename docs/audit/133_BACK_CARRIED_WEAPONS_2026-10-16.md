# Back-carried NPC and player weapons

Owner request: NPC weapons must stay attached to the back, and unequipped weapons in the player's two weapon slots must remain visible there until selected. No game is launched for this batch.

## Placement and rendering

The previous weapon transform always requested the owner's active weapon bones, then derived a hand-like basis from a pair of bones and applied a strap offset. On a strapped weapon that pair is spine bones, not hands. Outfit bone orientations and a near-parallel reference axis can turn the resulting basis; legacy per-model offsets can also differ substantially. Drawing a second inactive gun through that path would inherit the active gun's bones/strap state.

`CWeapon::netcoop_back_carried` selects only living co-op owners' actual occupied weapon slots INV_SLOT_2/3, with matching inventory/parent, a weapon magazine capacity and no separate attachment owner. The active player weapon is excluded. An AI-selected gun is included only while the NPC's actual strap mode is enabled. Rucksack, belt, destroyed/dead/non-weapon items and freeplay are excluded.

Each back model uses the current `bip01_spine2` transform with its accumulated bind orientation cancelled. This gives a stable animated torso frame independently of outfit bone axes and hand poses. The model bounding-box centre is placed at a separate left/right mount; the gun barrel points upward with a slight outward tilt. Pistols sit lower, and an equipped backpack adds clearance. Finite/bounded geometry, missing bones, invalid/singular matrices and cyclic/out-of-range bone parents refuse rendering instead of drawing an old transform at an unrelated location. Weapon transform/fire-dependency frame counters now start explicitly invalid.

The transform is refreshed for back weapons even within the same frame, including shadow/body passes, and leaving the back path bypasses its hand-pose cache. Co-op actors clear stale AI strap mode before applying a hand offset. Rendering calls the existing world-model path directly: it does not unhide inventory state, attach a HUD, play equip animations, emit muzzle lights or send state events. The owner renders inactive guns from exactly its two weapon slots; the active item is rendered once through the existing path. Per-model visual fit and all outfit/backpack combinations remain game acceptance work.

## Authoritative slot observation

Actor snapshots gain an optional eight-byte tail after the complete legacy actor/physics stream: tag/version/count and two authoritative slot object IDs. Only a server exports it; client-authored tails are not used by the server. The existing bounded per-object import prevents trailing fields from reading the following object. Existing readers can ignore the optional tail, and new readers accept a missing old tail without changing inventory.

Only a living remote player replica applies the exact-size/version tail. Both IDs must be distinct or empty and resolve to objects owned by that actor and its inventory before either slot is changed. Missing spawn/ownership defers the whole observation to the next snapshot. Both previous slots are cleared before placement so swaps work, and a selected object moved between slots remains selected. The owner's local inventory, server and corpses are excluded. Standard inventory movement events continue to provide live changes; the snapshot repairs late join/missed placement.

## Verification pending

`check-native-back-weapons.py` compiles actual weapon/owner bodies with actual xrCore affine matrix method bodies. It covers model-centre variation, animated bind orientation, world translation/rotation, separate mounts, same-frame movement, NPC strap/hand switching, player active exclusion, backpack clearance and invalid geometry/bones/ownership. `check-native-weapon-slot-tail.py` compiles the actual actor tail writer/reader and covers server-only export, old/missing tail, malformed fields/length, late join, swapping, selected-object preservation, absent/foreign IDs and owner/dead/server exclusion. Both are wired into the existing Windows native CI step. Full engine build/runtime fixture results are pending. No new resource patch or game acceptance is claimed.

Read-only local asset follow-up sampled 36 world-model/LOD OGF headers for AK74, SVD, Mosin, TOZ34 and PM families: 34 declared finite geometry within the mount's limits; two declared zero-size header bounds. These are source headers, not runtime acceptance. Existing `CPhysicItem::net_Spawn` and `CWeapon::UpdateAddonsVisibility` invalidate/recalculate the weapon skeleton; `CalculateBones_Invalidate` forces the next visibility-box rebuild from visible bone OBBs. The mount uses that runtime visual box. Particular models/outfits/backpacks still require an actual game visual check; no asset was changed or installed by the inspection.

## Build, installation and verification (2026-10-16)

- CI: DX11 `38926688813` and World Foundation `38926688809` for `f6395541d` — both success (checks, native fixtures including `check-native-back-weapons.py` and `check-native-weapon-slot-tail.py`, engine).
- `download_verified_native.py --run 38926688813 --commit f6395541d…`: every deployable entry verified; native SHA256 `e7afe8b3cc66a8951198119bf3cb5a9ecc9be45c51e86d7a571e2a445a5fb8cd` (client and dedicated identical). Artifact: `J:\LostZone_Work\_work\ci_f6395541d`.
- `install_verified_native.py --commit f6395541d…`: friend kit `J:\LostZone_Work\Lost Zone Server` and test dedicated `srvtest` updated (4 changed files, 6872 kit entries), hardlink-safe replacement; backup `J:\LostZone_Work\_work\before_native_f6395541d_20261016_192157`. Private data unchanged; master `3b3dead23` and resource patch `000020` retained. No resource patch for this batch.
- `verify_release_000020.py --native-commit f6395541d… --master-commit 3b3dead23…`: 6872 public manifest files, 66 native copies, 50 packaged master/fallback copies verified; version/hash pins agree; game/location/master processes 0.
- Owner client: `J:\LostZone\Lost Zone\bin\LostZoneClientDX11.exe` was missing (antivirus; the owner has since removed the antivirus). It was placed from the verified artifact above (not from quarantine); SHA256 matches the receipt. The client is at resource patch 000020.
- Not launched: game, locations, master. Launcher not published. Visual acceptance of back weapons (models, outfits, backpacks, NPC strap, late join) is still pending in game.
