# 91. Explosives, protected archives and incremental patches (2026-10-10)

Owner asked to finish Claude's projectile/mine investigation, fix barrels that
only fly away, then protect gamedata and support later bugfix patches.
The ban on launching game/server/bots remains in force. Nothing in this session
launches them or wipes accounts, characters or worlds.

## Qualified engine source

`a0e8bb64f0782710cdfa1162b322231a589b142d`:

- DX11 [38055467951](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38055467951): SUCCESS, full engine compiled.
- Foundation [38055468010](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38055468010): SUCCESS, GCC/MSVC native fixtures.
- Artifact 11671792713; ZIP SHA256 `51fa344da50e30f034a037a0ba950cb66798d019c43c0dc8fa91e54ac4b2145f`.
- Client/server EXE SHA256 `71D3699B0EE6D544F1CB1EE8DF89D3BEBADD4FFCB0C12F30D8C2B4EF10A16F0C`.

Changes:

- The 12 m/s loose-item/debris clamp excludes CMissile (grenades and bolts).
  Bullet momentum on non-creatures is bounded by mass, not by increasing mass;
  explosion impulses and thrown missiles retain their normal path.
- Weapon AIM carries an optional kind: bullet/RPG/launcher. The actual weapon
  validates the kind/mode and invokes its projectile path. No hitscan bullet
  substitutes for a rocket. RPG reserves a freshly reloaded asynchronous shot
  until the rocket ownership event arrives; stock NPC/SP paths stay stock.
  Underbarrel copies adopt the owner's mode and validated origin; grenade effects
  are emitted once. Client-forged launch/explosion events are rejected.
- Explosive items get the authority's condition/fuse, wake for frame processing,
  and update an armed fuse even when sleeping item scheduling did not tick it.
  Remote is no longer allowed to suppress the netcoop authority's explosion or
  blast wave. Missing hitters fall back to the object's ID. Map explosive barrels
  receive steel-shell mass like their CPhysicObject counterparts.
- Mine menu actions use the existing server item-action router, inventory checks
  and section functor whitelist. Server places/consumes the item, persists absolute
  calendar deadlines/instance identity/owner, uses spatial contact with living
  actors/NPCs/mutants, credits the correct reconnecting owner, and triggers once.
  Offline mines remain pending. Calendar components preserve millisecond precision
  across years; no float diffSec epoch loss. Legacy client creation/triggers removed.

Actual native fixtures cover the physics loop, weapon dispatch, delayed fuse and
event generation. Actual Lua covers mine ownership, rollback, save/reload, offline
timer, ID reuse, credit and millisecond/year boundary. These are code/CI evidence,
not live-game acceptance of barrel explosions or gun behavior.

## Archive format and patching

LZPACK1 wraps existing compressed X-Ray DB bytes with AES-256-GCM in 64 KiB blocks.
Each volume has random salt/nonce prefix; SHA256(master+salt) derives its AES key.
AAD binds the complete header and block index. Corruption, wrong keys, truncation
and swapped blocks are rejected. CNG implementation uses Windows/STL only, a
separate no-PCH/EH-enabled translation unit; ordinary X-Ray core keeps its required
exception settings. Engine reads bounded blocks and streamed windows, never a
whole decrypted archive or plaintext disk cache. Protected LZO uses bounded decode.
Streamed zero-terminated strings handle exact encrypted window boundaries.

Production key is injected by GitHub Actions `LZPACK_KEY_V1`, not committed.
Owner key stays under ignored `_build/private/` and later owner Compressor/private.
Build manifest fingerprints the key; sealer requires matching GHA source/key/exes.
Public fixture keys are confined to standalone tests. PDBs, key files, save/session
data and private probes do not go into either distributable.

`tools/lzpack/` contains the packer, final sealer and owner's patch command.
Patches use unique six-digit versions, separate client/server scripts, and the
last fsgame alias `db/lostzone_updates`. Later lexical versions override base and
loose data. C++ changes need matching GHA binaries. Archive deletion/tombstones are
not implemented. Mutable GAMMA configs stay loose because io.open bypasses VFS.

This prevents ordinary DB unpackers, not all reverse engineering: an executing
client can obtain plaintext and contains key material. No impossible guarantee.

## J: assembly and retention

Before conversion: player 105 archives / 53,708,442,657 bytes; server 70 archives;
28,771,848,474 bytes potentially shared; J: free 43,919,790,080 bytes.
Verified identical archives are deduplicated with NTFS hardlinks. Each folder
copies independently to another disk; links contain actual bytes, no C: dependency.
Exact original archive bytes are retained in `_work/retained_plain_*` before atomic
replacement. Scripts/overlay files are retained there too. Original bin/configs/
scripts/overlay/hoster retained separately in `_work/pre_protected_release_20261010`.
Appdata is not touched. Marker blocks launchers during conversion.

Assembly/deployment outcome and final portable-runtime qualification will be
appended after completion. Existing docs/audit/48 acceptance counts are not raised
by these source/CI checks. All game acceptance remains pending owner's permission.

## One "resources" folder (owner 2026-10-10, Claude)

Owner: all game archives in one English-named folder instead of `db\` with
eleven subfolders. `tools/lzpack/flatten_resources.py` (also run at the end of
`finalize_release.py`) renames every mounted archive into `resources\` with a
prefix that keeps the engine's old mount order (fsgame lines top to bottom,
each folder in name order, a later file overrides an earlier one):

`00` db top level (files, shaders), `10` configs, `20` levels, `30` meshes,
`40` sounds, `50` textures, `60` mods, `70` patches, `80` addons,
`90` Lost Zone (lz_*, sealed scripts/overlay/embedded), `99` updates.

fsgame keeps one archive line, `$arch_dir$ = false | false | {ROOT}resources\`;
`$game_arch_mp$` points to the absent `resources\mp\` (only MP map downloads
use it; a missing folder mounts nothing). Patches are now named
`99_lz_patch_NNNNNN.db0` and copied straight into `resources\`; they sort after
every base archive, and loose gamedata/scripts are empty after sealing. Renames
stay on the same disk, so player/server hardlinks remain one copy; LZPACK1 does
not bind the file name. Unmounted leftovers of `db\` (none expected) and the
old→new name mapping go to `_work\resources_layout_*`.
Fixture: `check-lzpack-release.py` (actual sealer + flatten on a tiny tree:
order 00 < 60 < 90, one fsgame archive line, patch sorts last).

## Players wiped (owner 2026-10-10, Claude)

Owner: "очистить всех игроков - удалить акки полностью". Servers were not
running. Moved (not left in any runtime) to
`NetAnomaly_Full\_backups\players_wipe_20261010\` with their paths:
- `LostZone-4Maps-Test\appdata\server`: netcoop_accounts.txt, the character
  file, the cluster store (PDA, goodwill, ratings, squads, contracts, faction);
- `LostZone-4Maps-Test\appdata\player\netcoop_login.txt` (remembered login);
- `gamma-runtime\appdata\server`: legacy accounts.sqlite3 (+wal/shm),
  account_roles, auth_tickets, player_state_bridge;
- `gamma-runtime\appdata\selftest`: bot accounts, 16 characters, store.
The J: release folders had no player data. Worlds (savedgames) are kept;
player-owned stashes/furniture in them now have no owner account.
Firebase (cloud sign-in) users can only be deleted in the Firebase console
(Authentication → Users): the game has only the public client key.
Old test snapshots under `_build\live\` and `build-logs\` were left as they are.

## Artefacts after emissions (owner 2026-10-10, Claude)

Owner: artefacts never appear again after an emission. Cause: the dedicated
callback filter (netcoop_server_compat) blocks every `actor_on_*` callback that
is client feedback; `actor_on_interaction` was blocked too, including the
emission's world event `("anomalies", nil, "emission_end"/"psi_storm_end")`.
GAMMA refills artefacts exactly there (bind_anomaly_zone.force_spawn_artefacts,
drx_da_main dynamic anomalies), so nothing ever refilled on a server. Also
GAMMA's periodic spawner `grok_artefacts_random_spawner` runs on the blocked
`actor_on_update`. Fix: the filter passes `actor_on_interaction` with typ
"anomalies"; `netcoop_artefacts.update_world` (server world tick) runs the
GAMMA spawner while players are on the map and restarts its delays when a
player arrives (GAMMA's set_delay on map arrival). Fixture
check-netcoop-artefacts.py. Not verified in game.

## Server for a player's folder (owner 2026-10-10, Claude)

Owner: "сервер чисто всё что надо накинуть на игру ... другу скину, он рядом с
bin накинет". `tools/lzpack/make_server_addon.py --out J:\LostZone --key ...`
builds `Lost Zone Server Addon\` from the sealed release: dedicated\, server
configs, hoster, panel, fsgame_server.template and only the server's scripts
archive (resources\95_server_*). Every other server archive equals the game's
by content (sealed copies differ by salt, so they are decrypted and hashed) and
is not repeated; nothing in the add-on replaces a game file. The panel's default
plan is `hoster\netcoop_cluster.ltx.six`: k00_marsh, l01_escape, l02_garbage,
y04_pole (Поляна), l05_bar, l07_military; Meadow is reached from Cordon, the
Warehouses from the Bar. The full standalone "Lost Zone Server" stays for hosts
without the game.

## Nothing extra in the distributables (owner 2026-10-10, Claude)

Owner: "удали лишние папки которые не должны быть доступны игроку и не влияют
на запуск, и у дедика". Removed from J: (moved to `_work\trimmed_*`, not
deleted): the game's `client\bin` (an old runtime copy; the engine runs from
`bin\`), `client\textures` (not mounted: fsgame reads gamedata\ and the
archives; the RP textures are sealed in lz_overlay), `notices\notices`,
`MANIFEST-sha256.txt`, `built-from.txt`, `lzpack-format.json` (nothing in the
game or the launcher reads them) and the empty `appdata\` (Play Lost Zone.cmd
creates it); from the add-on's `hoster\` the `*.example` files and
`changers_dump.txt` (the panel reads only the .six/.full plans). The player's
`notices\` got the Microsoft D3DX license that ships with the D3DX DLLs.

The generators no longer make them: finalize_release moves `<role>\bin` and
`<role>\textures` into the retained originals and puts the build stamps next
to the owner's Compressor; make-portable-release copies notice files, not the
folder; make_server_addon skips hoster examples and stamps.
`check-portable-release.ps1` now fails on any of them (also in the add-on,
plus an add-on file that would replace a game file) and writes its SHA256
manifests to `_work\`.
