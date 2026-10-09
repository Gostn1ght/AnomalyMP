# 87. Session 2026-10-09 evening: traders, look/shot, calendar, crates, respawn, crows

Owner policy unchanged: SERVERS OFF, no game/server/bot/load runs until the owner
says so. Everything below is source + Lua fixtures + GitHub Actions only. Nothing
here is accepted in game; audit counters stay 27/33/69/59 (161 not closed).

Baseline: a4d8628ab qualified — DX11 run 37951023676 SUCCESS, Foundation
37951023767 SUCCESS (both completed before any new source push).

## 1. Traders on every location (2c4aa7c90)

- Data, not memory: GAMMA trader logic = a logic section with a non-generic
  `trade =` config (shipped `configs\scripts`). Maps with such traders: jupiter,
  jupiter_underground (ISG), k00_marsh, k01_darkscape, k02_trucks_cemetery,
  l01_escape, l02_garbage, l03_agroprom, l04_darkvalley, l05_bar, l07_military,
  l08_yantar, l09_deadcity, l10_red_forest, pripyat, zaton (16). The other 17
  (incl. all labs, l06_rostok, radar, limansk, hospital, l11_pripyat, generators,
  y04_pole, stancia 1/2, sarcofag, control_monolith) have none.
- `netcoop_traders.script` + `configs\netcoop\traders.ltx`: on those 17 maps the
  server creates ONE neutral trader (`stalker_silent`, community `trader` —
  neutral to all, as GAMMA's relation table) 4 m from the anchor Actor, i.e. the
  map's start point; told not to choose ALife tasks (stays); invulnerable;
  assortment `trade_stalker_basic.ltx` (wraps GAMMA's trade_init; trade profile
  set when a player trades, prepare_trade has db.actor bound). Once per world
  (state.netcoop_traders[level]); never replaced after death/release.
- BUG FOUND in the 2026-10-09 retirement table: 17 real traders were marked
  `remove` (barmen incl. Barkeep, base medics, Yantar cook). Their logic sets
  trade_generic_barman / trade_generic_medic / trade_ecolog_spirit. Now `trader`.
  `hunter_gar_mec` and `zat_a2_stalker_nimble` (Nimble) were missing: added as
  traders (a story trader offline at the first scan had no trade profile and
  would have been released). Worlds that already ran the old table released
  those NPCs; they are NOT restored by this change (no respawn rule).
- Fixture `check-netcoop-traders.py` (CI): the 33-map catalogue is partitioned
  into GAMMA-trader maps and added maps; one trader, once, never replaced; own
  assortment kept; other NPCs untouched.
- NOT verified in game: position quality on each map (anchor start point may be
  inside a building/lab corridor), idle animation of a squadless NPC.

## 2. NPC look vs shot (acd8324f0, local until the build above finishes)

Root cause found in code: the server's spine/shoulder/head bone callbacks turn
from `m_body.current` and distribute (head - body) with the sight action's
torso-look factors. Puppets got (a) the model yaw (XFORM) as body yaw — they
differ while animations turn the model (animpoints, covers) — and (b) the
default free-look factors (head turns alone, torso and weapon stay with the
body) while the server NPC in combat uses torso look. Now the stalker snapshot
carries the bone body yaw and the torso-look flag (trailing fields; old
clients ignore them); the puppet sets body yaw for the callbacks, keeps XFORM
at o_model, and uses CSightAction(CurrentDirection, torso_look). Sniper fire in
a cover shoots along the head TARGET (g_fireParams): clients get the target as
the head. Display only; server AI aim unchanged. Not verified in game.

## 3. Calendar catch-up visible as "jump to evening" (941dde492)

A location server behind the cluster calendar accelerated up to 4x normal while
players watched. Now: no players on that server -> catch up within ~30 s (up to
900x, world clock max 1000x); players present -> at most 1.25x normal. No jumps
(world clock rule kept). Emission shadow smoothness itself is NOT addressed.

## 4. Crate mass = shell + real contents (b6b55f470, WIP integrated)

From _build/wip/box-mass-20261009, re-examined against GAMMA sources:
- bind_physic_object drops crate loot without `drop_box` only at 50 %: the plan
  now rolls that gate once with the contents; the death callback releases the
  planned loot before the stock branch, so GAMMA's second 50 % roll no longer
  decides (it would have made loot 25 % / mass wrong). Stock spawn_items for a
  planned crate is a no-op after release (never twice).
- Lua multiple-return bug fixed (section_exist got resolved_section's 2nd value).
- Mass reapplied on every scan (offline/online recreated the shell with the
  authored 100 kg; the old per-id cache never reapplied).
- Engine weights matched: ammo inv_weight*rounds/box_size (CWeaponAmmo),
  multi-use empty+uses*(full-empty)/max_uses when use_condition (CEatableItem),
  "medkit__1" alias as ItemProcessor:Extract_Uses.
- Never raises inside the engine death callback: a failed spawn rolls back what
  was made and runs GAMMA's own roll; the plan is marked released first, so no
  path spawns twice. Reused ids are replanned.
- Engine part from the WIP patch: CPhysicObject::netcoop_set_content_mass,
  netcoop_prop_shell_mass/netcoop_mass_props/netcoop_prop_set_mass,
  netcoop_prop_mass.h (wood 12 mm/600 kg/m3, steel 1.5 mm/7850 kg/m3 shells).
- Fixture `check-netcoop-box-contents.py` (CI). NOT verified in game.

## 5. Respawn death loop (local commit)

The new body got the old one's hunger/stamina/thirst back (client player_state
in pstor): a player who starved/died of thirst respawned starving. Dropped on
respawn (radiation/psy were already reset); a living reconnect keeps them.
check-netcoop-respawn-state.py extended. Spawn position already the map start
(placed=false on respawn), inventory not duplicated (dead body keeps it).

## 6. Crow jumps on clients (local commit)

A client crow flew its own local flight (UpdateWorkload towards a random goal
near the local player) while every server update overwrote its position. Now a
living remote crow on a pure client interpolates the server's snapshots
(netcoop_interpolation_time); a jump > 50 m is placed. Native crow fixture
extended. NOT verified in game.

## Open (unchanged, honest)

Mutant aggression/circling and hostile faction reactions (no evidence without
game runs; not guessed), weapon pickup/context menu server parts, transition
boundaries / Garbage extra zone, emission shadow smoothness, 64-player CPU,
the remaining 188 items, J: distribution (next).
