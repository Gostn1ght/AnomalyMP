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
