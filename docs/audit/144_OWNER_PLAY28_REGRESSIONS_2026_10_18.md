# Owner test of 000028 РІР‚вЂќ 2026-10-18

Reports: disappearing sights and some unarmoured models; floor/corpse loot
refused; Buy refused; all traders offer no work; back weapons float above
the shoulders; unexplained client exception. Preserve player/world data.

## Evidence and changes

- Pickup/transfer: `xr_vector<u16>{item_id}` uses this engine container's
  **count** constructor, not an initializer-list constructor. It submits
  thousands of zero IDs; entity zero is the anchor Actor, not an item.
  Replace with an explicit push of the single item ID. Keep strict tree,
  parent, cycle, depth and 512-item persistence checks. A read-only symbol-
  guided inspection of the running server found no malformed parent links;
  bypassing inventory validation would have hidden the actual bug.
- Tasks: the live server had 891 config sections and an empty
  `axr_task_manager.CFG_CACHE`. GAMMA populates it from SP `load_state`,
  which this dedicated world does not dispatch. Initialize the static config
  cache on server game-load and before a dialogue. A live invocation of
  GAMMA's existing `generate_cache` populated all 891 sections. This does
  not grant tasks, remove prerequisites, reset cooldowns or change history.
- Trade: the reported request to Marsh bartender 20157 from player body
  27663 was rejected before item admission. Live queries confirmed a valid
  barman profile, alive and not wounded, but `relation(player)==enemy`.
  Return the precise policy reason to the existing client result handler;
  preserve hostility, distance, ownership, stock, money and dialogue checks.
  Loot admission is separately repaired above. No hostile-trade bypass.
- Opaque sights: GAMMA's `z_3dss_shader_switcher` deliberately replaces
  scope/rear-iron materials with `models\transparent_hud` on ADS. Its shipped
  defaults enable the effect at opacity step 5 (50%); the owner's active
  `shader_param_5.w` was also 0.5. Disable that optional fading only when
  netcoop is enabled. Preserve normal 3DSS optics, opaque marker normalization,
  delayed-effect cleanup, and SP options/behavior. An actual full-script Lua
  test exercises zoom in/out, zoom-type changes and option refresh for both
  co-op and SP, including stale faded-material restoration.
- Preview material reuse: `PrepareUIModel` assigned a menu shader directly
  while leaving its debug material names unchanged. Pool reset consequently
  skipped restoring the normal material. Track the temporary shader and
  texture names; recursively restore visible/hidden child materials before
  reuse. Retain deferred deletion during rendering. This fixes a concrete
  renderer defect; its contribution to every reported sight/model artifact
  still needs runtime acceptance. Shipped `shaders.xr` matches the GAMMA
  source byte for byte; no blanket graphics downgrade or alpha override.
- Back weapons: the old attachment centred the entire model at Spine2
  (shoulder height), placing half a rifle above the head. Position its upper
  rotated bounding-box extent 12 cm above that bone, closer to the back;
  retain both slots, animation-relative transform and pistol hip placement.
- Crash: matching CI PDB resolves exception `0xc0000005` at `0x1404ad800`
  in `CMemoryManager::remove_links`, `memory_manager.cpp:326`. Remote NPC
  copies do not bind AI-agent memory containers; relcase dereferenced a
  null visual-memory vector. Client replicas now keep inherited and physics
  cleanup while skipping authoritative AI memory/sight/movement/agent links.
  Server and SP paths retain their AI cleanup. Stack scans are candidates,
  not an unwound call stack. This identifies this dump, not every possible
  random crash.

Evidence copies and read-only diagnostic tools:
`J:\LostZone_Work\_work\owner_bugs_000028_20261018`.

## Validation and delivery

Actual Lua ADS switcher, task generator/config cache, trade policy and scoped speaker tests
pass locally. Native tests extract production bodies, including the engine's
actual vector constructors, remote living/dead NPC release, deferred/nested
preview restoration and back transforms over varied model bounds. Native
compilation and the full DX11 build run only in GitHub Actions.

First CI run 39122559315 stopped on a strict integer-narrowing warning in the
new pickup **test fixture**; anchor literal changed to `u16(0)`. Production
changes are identical. Replacement run 39122808094 is pinned to
`839333f2fd72d459b5326fff4c4c45ffe4af52df`. Patch 000029 was sealed before the additional sight fix and is not published.
Final patch 000030 is cumulative since patch 27, including the unchanged
client compatibility script from 28 and the new ADS overlay. Do not mark all seven
reports runtime-closed from offline checks alone; sights, models, attachment
appearance, successful live trades/task acceptance and repeated crash-free
play remain owner/hoster acceptance checks.
