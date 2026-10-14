# Player inventory capacity, 2026-10-14

Owner wants armor/backpack/carry weight and item dimensions to determine capacity, with cells beside weight, and less severe limits.

Live capacity = max(configured base, floor(native MaxCarryWeight * 4)), cap512. Shipped base rises60→120. The real carry-weight function includes worn armor, equipped backpack, upgrades, belt artifact condition and timed weight boosters. Safe capacity remains120 and independent. Client/server config bytes match.

Used cells are the sum of icon width*height for rucksack root items, per instance, not per stack. Equipment/belt slots occupy no rucksack cells. Pickup and complete trader purchases use the same live capacity, and separately enforce the512-object lossless save limit including equipped/nested items, repeated IDs, depth and parent consistency. Existing items are never dropped/truncated when equipment or booster changes; overflow only blocks additions and is shown in the footer.

NCH9 appends last captured authoritative capacity, old NCH3..8 load unchanged and get base fallback until next live capture. Offline safe withdrawal uses the captured value and excludes equipped inventory cells, preserving the existing atomic subtree transfer, UID/ammo/state and failed-save rollback. No old file or account is rewritten during verification. Master importer also reads/bounds the appended field.

Client helper wraps the actual GAMMA UpdateWeight rather than replacing the inventory UI script. Original current/max weight, armor/backpack/belt/booster calculations and NPC display are retained. A localized Cells used/capacity text occupies x155..255 on the same y742 footer, between Put all (ends150) and weight (starts260). The redundant total-weight caption hides only when the new native API provides valid stats. Old native/no actor/malformed stats remain compatible, widget created once per inventory instance. No game is launched for testing.

Lua regression executes the actual retained GAMMA weight function plus helper, validating original weight/gear/booster behavior, idempotent install/update, overflow color, malformed API data, absent old API, localization and XML geometry. Native CI exercises the actual native carry-weight functions, live/storage transaction include, item-tree admission and NCH3..9 read/write with legacy cross-CPU checksums. Exact shared footer/animation visuals and friend-host gameplay acceptance remain pending.

Native CI38594201617 (28f579f44) succeeded for initial capacity/NCH9 implementation. The next batch fixes the Lua primitive return type and caches the immutable capacity configuration; no initial artifact was deployed while that interface correction was pending.
