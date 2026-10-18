# Patch 000032: reload input and ambient recovery

Owner reports: reload fails with every weapon; transport has no character
collision; sound disappears and returns after Alt+Tab. NPCs do not draw
knives/axes, so their grip could not be compared.

## Qualified causes

- Current owner's `user.ltx` has `bind wpn_reload kF10`, no `custom22` and
  no R binding. Stock GAMMA `arti_jamming.on_game_start` moves native reload
  to F10; its `on_key_press` only forwards `custom22` to that native action.
  Thus R cannot reach any weapon at all. No ammo/state bypass is needed.
- Current client log repeatedly reports `sound_ambient.script:112`, indexing
  nil `ch`. `reset_settings` clears channels but retains the preceding count
  when the next ambient is missing. Its failure also removed the timer;
  weather changes within one hour did not refresh the channel list.
  This qualifies an ambient failure, **not** the cause of every sound going
  silent. Alt+Tab recovery of all audio still needs a controlled reproduction.
- Native collision correction is already in `934354d7c`, built successfully
  in CI [39133976529](https://github.com/Gostn1ght/AnomalyMP/actions/runs/39133976529).
  Removing the dynamic-class exclusion restores character contacts while
  retaining the ground/debris filters. Gameplay acceptance remains open.

## Changes and checks

- GAMMA now captures the native reload key before moving it and passes it to
  `netcoop_reload_input.restore`. Existing custom22 bindings are preserved;
  a custom native key moves across; the broken F10-only configuration gets R
  only when R is free. Occupied keys are never stolen. Unjam still runs the
  original GAMMA handler. Single player is unchanged.
- Ambient reset clears the count. Empty channels keep a nonfailing timer;
  weather/map/hour changes retry initialization, and reconnect invalidates
  the cached selection. Valid channel playback is retained.
- `check-netcoop-reload-input.py` executes the whole shipped GAMMA module,
  actual start/key callbacks and helper for default/migrated/custom/occupied
  keys, jams, reconnect and SP. `check-netcoop-ambient.py` runs the complete
  ambient module through failed/successful resets, same-hour weather/map
  changes and reconnect. Both added to CI; both pass locally in Lua 5.1.
- Full overlay scope/compilation, weapon-parts, taskboard and helicopter
  checks pass. No game or server was launched for these checks.

Native `934354d7c` also includes the preceding patch32 work: Mi-24 gunner,
taskboard, PDA password/friends/tabs, loaded-launcher inventory/save support,
transition question initialization, anomaly damage, axe animation and F7
faction/pardon/god actions. These require the owner's in-game acceptance.

The existing unstaged `WeaponMagazined.cpp` diagnostic draft is retained;
it is not part of the already built native executable. DCP model migration
and the complete-sound-loss investigation remain open.
