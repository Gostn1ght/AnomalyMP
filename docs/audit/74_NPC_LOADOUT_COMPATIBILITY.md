# 74. Nine GAMMA NPC loadout compatibility entries

2026-10-08, Codex. Scoped configuration repair accepted and installed.
This is not a new188 row; counts remain26 accepted/34 code/69 partial/59 open.

Actual native INI observations in doc68 found a missing `wpn_usp_match`
section and three weapon variants with stale ammunition indices. GAMMA
loadout initialization drops the absent weapon from its weighted pool;
on_creation falls back to ammo0 for invalid indices and reports errors.
The original script and its diagnostics are preserved.

The explicit manifest repairs nine rows in five files:

- Blackops secondary: `wpn_usp_match` becomes the existing `wpn_usp`.
- Freedom experienced/veteran Ithaca20x70: indices3/6 become0, its sole
  `ammo_20x70_buck` type.
- Monolith legend DVL_m1: index3 becomes0, its sole `ammo_338_federal` type.
- Monolith master/legend, ISG veteran/master and Greh legend AK74uM1ISG:
  index6 becomes3, pristine `ammo_7.62x39_ap`. This retains AP quality for
  the actual changed caliber instead of accepting fallback FMJ0.

Every attachment flag, row weight, accessory chance, comment, line ending
and unrelated byte remains unchanged. Restoring USP to its intended pool
changes the available weighted weapon choice; identical random selection
or unchanged NPC inventory contents is not claimed. No population,
respawn policy, AI cadence, perception, movement or combat code changes.

`scripts/install-netcoop-npc-loadouts.py` previews by default. It checks
every expected section/key before writing, rejects missing/custom/ambiguous
entries, retains original bytes in an exclusive backup directory, and
replaces each file atomically to avoid modifying another hardlinked copy.
A repeat preview reports zero changed rows. The repository contains only
the targeted manifest and installer, not whole third-party config trees.

Native acceptance uses the validated GHAe609 package from doc68 and the
SAME retained private `selftest_destructibles_correlated` server world.
Both roles load separate private patched config trees; the native INI
reader verifies all nine exact section/key pairs, weapon existence,
actual ammo_class indexing and selected caliber/quality. Random USP ammo
members are all verified as existing native sections. Ordinary known
synthetic account961 enters as Actor26903 and stays another20s. Original
actor updates and GAMMA initialization are retained. Both pre-stop logs
contain zero NPC-loadout, target rain Lua missing-file, fatal/exception, SCRIPT ERROR,
failed-handler or probe errors. MCM/HUD255 and other diagnostics remain
separate; this is not a completely clean GAMMA startup. Other native
asset warnings:38 missing-texture and10 missing-sound records; these are
not the14 target Lua rain exceptions and remain unresolved.

Proof: `_build/live/loadout-e609/qualified-acceptance.json`, matching
pre-stop logs and patch/backup hash manifests. Nonce
`LOADOUTFIX_3324a55d355b4de0afe973b30f26811c` identifies both native results.
Failed probe attempts are retained: a non-raw Python path opened an empty
wrong INI, then a whole-table key count incorrectly counted an unrelated
faction's existing Ithaca entry. Both strict assertions rejected before
client admission. The final probe verifies the intended section/key pairs
without relaxing ammo checks. Those failures are not native PASS.

After acceptance, preflight all four ACTIVE primary client/server config
roots for gamma-runtime and LostZone-3D-Hideout. Actual relevant weapon
config bytes match the privately tested trees. Install only five loadout
files/nine rows per root (20 files total), with exact original backups
under `loadout-e609/primary-backups`. Final bytes/hashes and idempotent
zero-change previews are recorded in `primary-installation.json`.
Fallback gamedata configs, original downloaded GAMMA and primary FS aliases
are not edited. All88 protected exe/config-alias/account/character/world
fingerprints remain unchanged; these20 targeted LTX files are outside that
baseline, so do not describe all primary configs as unchanged.

All test processes stopped; shared debug channel empty. No primary engine
promotion. Human weapon fire, all NPC generated item packets, immortal or
jerky NPC behavior, character blinking and64/max-view remain open.
