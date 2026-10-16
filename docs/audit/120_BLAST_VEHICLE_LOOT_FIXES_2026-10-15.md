# Blast safety, vehicle hands and mutant interaction, 2026-10-15

Implementation batch; native CI and actual game acceptance are not implied by this document.

`Explosive.cpp`: the old upward-impulse formula used a displacement in metres where its derivation assumed a unit vector. A target10m below a blast with up-throw2 evaluated sqrt(5-40). The new actual helper normalizes the radial direction, adds the upward component and normalizes again, with finite/zero/cancellation guards. Hit power/radius, fragments, occlusion, wave budget and authoritative dispatch remain in place. This demonstrates an invalid-hit bug, not yet the reported TPS-zero root cause.

`Level_Bullet_Manager.cpp`: both binary trajectory searches now stop when the midpoint cannot advance between adjacent floating-point endpoints, with a64-iteration bound. At flight time1024s the next representable float is farther apart than the existing absolute comparison epsilon, so the former loops could stall indefinitely. Corrupt/nonfinite flight state is rejected before ray/trajectory work. Normal intervals retain existing math. `check-native-blast-ballistics.py` executes actual native functions, normal30Hz flight, targets above/below/coincident, invalid vectors and adjacent-float cases in CI only.

`Inventory.cpp/.h`, `netcoop_vehicles.inc`, `Weapon.cpp`, `netcoop.cpp`, `netcoop_items.inc`: every vehicle seat admission/replica holsters hands. Inventory activation (including force/UI/Lua), deferred/previous slot update and the server's shot/remote HUD/activate gate cannot re-equip or fire while seated. Server menu item actions are rejected while seated; `Eat` consumption remains independent of held-slot activation. Native hand/shot fixtures cover seated, exit, NPC and freeplay cases. Third-person consumption animations are still OPEN.

`netcoop_storage.inc`, `netcoop_transfer.inc`: the transfer reply now separates inventory cell overflow (used+needed/capacity), the lossless512-item limit, and incomplete/cyclic inventory state. Existing admission limits are preserved; invalid state is never silently accepted or saved partially. This removes the false universal diagnosis `no free inventory slots`. The screenshot's actual triggering inventory has not been captured, so pickup acceptance stays OPEN.

`ActorInput.cpp`, `netcoop_mutant_loot_view.script`: pure-client F first offers the object to a dead-mutant/crow adapter, which requests the server's parts list and avoids the SP use callback. Non-mutants/living objects continue normal handling. The adapter supports existing numeric-ID callers instead of silently dropping them. Actual Lua adapter tests pass for these paths and the existing server-backed window. Live binder/window/knife/creation behavior remains OPEN.

No player/account/world file is modified by these checks. No game client/location server launched. DCP and helicopters are being audited independently; no foreign binaries or protected PBO payloads are installed.

Follow-up: server mutant takes now decrement persisted body loot and wear the knife only after ItemProcessor returns a real created entity. Nil/partial creation keeps the remaining parts on the corpse; actual Lua failure/retry checks pass without rerolling or reissuing already created parts. This is not a crash-durable world/inventory transaction.

First batch a09d9cc14: Linux checks and all Windows native fixtures passed in CI38783097051; full engine build is still pending at this recording. Follow-up observer animations and source-audit decoder checks await their own CI.

2026-10-16 verification update: run38783097051 completed with a successful full engine build. Combined run38853207613 for3eb197b79 also fully passed, including the nil/partial mutant creation Lua paths, real observer consumption motions, DCP wheel suspension and HUD light helpers. Observer animations are implemented (doc122); their actual multiplayer game acceptance remains open. The subsequent skeleton history fix is tracked separately in doc125. No game was launched for these checks.
