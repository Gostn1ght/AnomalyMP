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

## Delivered 2026.10.18.5 / patch 000032

- Native `934354d7c4c25d2472f5494a5e7df0f64176ea4e`, successful complete
  DX11 CI 39133976529. Client/server SHA256
  `2aabfbedb52642d66830b0af3cec5e1d947d118e9244b2cbaa5a4565d62d6699`.
- Resource patch pinned to `ea89862d87bbb6c5a88ca32f4438f8a4ad9e98e4`:
  8 client scripts/assets + 3 loose configs, 7 server scripts/assets + 1 config.
  Its first CI run failed the Linux CRLF policy check, not the Lua tests.
  `.gitattributes` correction and normal-priority host tools are pinned to
  `b40436cb43d2e630f5b48f8c6f4b56d9aacb1af4`; checks job in run 39139549445
  passed. Overlay contents are identical between these two resource commits,
  and their committed native trees exactly match the successful native build.
  The duplicate native build of b40436cb4 was still running at delivery.
- Signed launcher release 2026.10.18.5 has 6877 public files. Manifest
  `manifests/2026.10.18.5-4cd18a33.bin`, BLAKE3
  `4cd18a3330e86913753273ef5bb0fc19f8f1a709b558eb748ba68f6bdfde552b`.
  Ed25519 verified, required client files reconstructed and byte-compared,
  all chunk bounds checked, no server/private paths. P2P serving online;
  the configured HTTP mirror remains off.
- Hoster overlay `J:\LostZone_Work\Lost Zone Server` and ZIP
  `J:\LostZone_Work\Lost Zone Server.zip` updated. ZIP has 6903 entries,
  272877491 bytes, SHA256
  `32c061c390e31acfe31bdeeefac2d0bf71200bd3acf8a77eff3c34536370132e`.
  Every ZIP member hash was verified against the public file manifest.
  Watchdog now actually uses Normal priority. Master executable remains
  e689f5ce7; accounts, saves and private runtime are excluded/preserved.
- The owner closed the client and both map processes during preparation.
  Their absence was rechecked before installing the matching native/patch
  and loose configs into the owner game and srvtest. They were left stopped;
  no UI was operated and no game session was started. The already running
  master was retained. Next play session uses patch32 on both sides.
- Receipts: `J:\LostZone_Work\_work\patch_000032\` (`source.json`,
  `installation-reviewed.json`, `publication-reviewed.json`,
  `server-zip-reviewed.json`, `owner-test-updated.json`). Previous release
  files/ZIP retained in the work backups. Packaging helpers are
  `J:\LostZone_Work\_work\owner_remote_bugs_20261013\*_000032.py`;
  `install_owner_000032_offline.py` is the nonlaunching local installer.
