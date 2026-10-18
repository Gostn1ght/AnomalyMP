# Owner play32: combat, cold trade profiles and PDA input

Nine reported regressions: trade refuses normal purchases/sales, Mi-24
occupants/camera misplaced, slow movement after death, knife requirements
for butchering, no melee/crate damage, NPCs aiming at feet, passive mutants,
passive hostile factions, and no text entry in PDA fields.

## Evidence and changes

- Marsh play32 log reports `get_item_trade_status ... trading profiles
  missing info` for `items\trade\trade_generic_medic.ltx`. Read-only server
  probe confirms the saved profile exists but its ini cache does not.
  Stock `trade_load` restores profiles only; `update` returns early on a
  missing cache. `prepare_trade` now reopens the same profile through stock
  `trade_init`, preserving its stock/resupply state and all trade policy.
  Test runs the complete unmodified GAMMA trade_manager fixture.
- Server probe confirms `device().precache_frame == 60` indefinitely, while
  native relationships are enemy and Lua `xr_combat_ignore.is_enemy` returns
  false. Its loading guard rejects every enemy while precache > 1. The runtime
  headless server uses the regular DX11 executable and never calls render
  End(), which consumes these frames. `PreCache` now treats runtime dedicated
  mode like compile-time dedicated mode. No faction/safe-zone bypass added.
- `CSightManager::aim_target` recognized only `g_actor` (the hidden server
  anchor); connected actors fell back to their feet. Living remote actors
  now use the existing head-bone aiming path. Custom aim bones, stalker
  targets, dead entities and prop fallbacks remain unchanged.
- Knife impact animations never sent owner shot requests; all client bullets
  are deliberately visual-only, and server shot admission required ammo.
  Actual impact marks now submit the existing validated shot request. Only
  knife classes accept zero ammunition; the server validates the active item,
  origin, shot kind and rate, then uses KnifeStrike/MakeShot and the normal
  authoritative BulletManager. Copies do not also strike from animations.
  Network knives no longer fabricate dummy ammo, which violated inventory
  validation. SP dummy ammo behavior is retained. Knife rate floor: 250 ms;
  common seated/origin/ownership admission still applies.
- Butchering now validates the knife actually held, not a knife in a bag:
  GAMMA knife classes, minimum condition .15, basic/Type 2 knives refused for
  chimeras and pseudogiants. Successful cuts wear that held knife by GAMMA's
  existing rate; every part rechecks condition, and failed cuts preserve loot.
- Stock true_first_person_death's timer survived respawn and repeatedly set
  time factor below 1 and faded sound. Network cleanup now cancels it on
  revival/body replacement/disconnect and on first update, resets time/audio
  and removes the effect. The headless server registers no death camera;
  single-player behavior is retained.
- A captured edit in 3D PDA was skipped by CUIPdaWnd, which translated all
  raw keys to PDA item actions. Captured keyboard input now goes through
  the inherited UI route (letters, paste, delete, releases included). Normal
  unfocused PDA controls and 2D close keys remain on their existing paths.
- Mi-24 model-space geometry was inspected from the shipped OGF. Front/lower
  cockpit is approximately Z 3.5..5.0, Y 1.15..2.1; rear/upper Z 2.0..3.4,
  Y 1.5..2.75. Occupant roots moved into those cabins. Optional explicit seat
  eyes separate eye placement from the two sitting poses: front (0,1.75,4.1),
  rear (0,2.35,2.45). Walking-camera hull collision no longer pushes a seated
  first-person camera outside its own vehicle. Passenger/gun-view handling
  remains separate. These offsets still need in-game visual acceptance.
- Retained the pre-existing reload diagnostics draft in WeaponMagazined.cpp
  for this next native build; bounded its ammo section diagnostic formatting.
  It logs pending/full/no-ammo causes, without changing reload admission.

## Verification and release state

All 71 portable script checks in the CI checks job pass locally, including
the new complete stock death-camera/trade-cache tests and knife class,
condition boundary/partial-loot checks. Helicopter configs match both roles;
explicit eyes are finite and inside the measured cockpit envelopes. Overlay
Lua scope and CRLF/compilation checks pass.

New native fixtures are wired into GitHub Actions: actual runtime/compiled
dedicated PreCache, PDA raw-key routing, remote-player aim, knife impact and
validated authoritative shot/bullet dispatch. Native compilation and gameplay
acceptance are pending at this commit. No game UI was operated for these fixes.

Next patch number is 000033. Installed patch32 client and both location server
processes were still running during development; no live binaries were replaced.
The launcher distribution service remains stopped at the owner's request.
Untracked user file tools/extract-vehicle-assets.py was not edited or staged.


## Delivered patch 000033 / 2026.10.18.6

- Successful complete DX11 CI 39147853204, native commit
  `2fb19d4b53306d9f7bb37b364b2dffc40de57800`. Client/server SHA256
  `7c2d0e78094cee81d7e58f86d490cb76b77905302d8045e48094752a0b069411`.
  All new input/AI/melee native fixtures and the existing regression suite
  passed. Initial fixture-only compiler failures were corrected before this
  successful build; runtime code/resources match c20dabb41 exactly.
- Resources pinned to `c20dabb41ce2cc4aad58fb5ca932e0af427168e1`:
  3 client and 4 server scripts, two loose configs for each role. Encrypted
  archives authenticated. Existing patch numbers were not replaced.
- Signed launcher manifest `manifests/2026.10.18.6-33df459f.bin`, BLAKE3
  `33df459f1833f06a2d4fc77f15b0b3a6f0c3c92b4cb3653b595abc7d7f55c6f8`,
  6878 public files. Signature, chunk bounds and reconstructed update files
  verified. Prepared offline while distribution was disabled; the owner's
  later instruction explicitly authorized starting distribution. PID 3944
  serves this exact release, authenticated panel and P2P relay verified.
- Hoster folder `J:\LostZone_Work\Lost Zone Server` and
  `J:\LostZone_Work\Lost Zone Server.zip` updated. ZIP: 6905 entries,
  272988042 bytes, SHA256
  `c500e921637aef54d54a0c63fb8b5cd49f116ae9d3d3b72d97d4d9cbc7d88d3f`.
  Every member hash verified; accounts, saves, signing keys and private
  runtime excluded. Master build e689f5ce7 unchanged.
- Owner client and srvtest native/archives/configs installed with matching
  hashes while the client was closed. Old maps saved before stopping; old
  patch32 Marsh required termination only after its completed-save log and
  hung device teardown were confirmed. New Marsh PID18328 acquired saved
  world zone at epoch5. The owner then cancelled game-server startup and
  requested only launcher distribution: the launcher helper was stopped,
  Cordon was not restarted, new Marsh saved and exited, master stopped.
  Final state: no game client/location/master processes; distribution only.
- No in-game acceptance was performed. Combat, visual seat alignment and
  PDA typing in the real game still require owner playtesting. DCP migration
  and the previously open complete-sound-loss investigation remain open.
- Receipts/helpers: `J:\LostZone_Work\_work\patch_000033` and
  `J:\LostZone_Work\_work\owner_remote_bugs_20261013\*_000033*.py`.
