# 73. Restore14 missing SSFX rain sound assets

2026-10-08, Codex. Scoped asset repair accepted and installed. This is not a
new row in the188 world requirements; counters remain26/34/69/59.

Both ordinary GUI and later dedicated restore previously report14 missing
SSFX rain footstep/jump/land OGG files. The matching local GAMMA archive
`190- Screen Space Shaders 23 - Ascii1457/db/mods/ssfx_rain_footsteps.db0`
contains exactly these14 audio files plus four directory entries. Archive
SHA256 `1465d07b0dfabbda8082f06cc08f9063ed5a6acbed4d714602d249f46ba8a655`.
The runtime had the Lua sound references but did not mount this mod archive.
No whole mod/profile activation is needed.

An existing bundled asset codec reads the archive (no new native compilation).
All14 files are bounded/whitelisted, decoded, checked against archive CRC32,
size and OggS header, and individually SHA256-manifested. The original mod
archive and original GAMMA installation are not modified. The repository
ships installer/manifest only, not audio payloads.

Actual ordinary GHAe609 client, validated source/package from doc68, and a
matching server restore the SAME private correlated world. Separate private
configs/appdata, existing synthetic account961, no owner credentials. Both
roles mount only the matching archive through additional PRIVATE FS aliases.
After the ORIGINAL actor update, actual native sound constructors load all14
sounds. Their native durations are nonzero (512–838ms); SSFX on_game_load also
runs without the old missing-sound stacks. Client stays admitted another15s.
Both sealed pre-stop journals contain no missing-file sound diagnostics,
native fatal/exception, SCRIPT ERROR, failed handler or caught probe error.
This proves resource loading, not human audio playback or an entirely clean
GAMMA startup. Existing MCM/loadout/HUD255/texture diagnostics stay separate.

Qualified proof: `_build/live/rain-sound-e609/qualified-acceptance.json`,
join2 client/server pre-stop journals, decoded-manifest.json, original archive
inspection and GHA provenance. All failed/incomplete trials remain:

- Standalone menu did not consume the prepared command before timeout;
  UNQUALIFIED, own exact pending nonce preserved/verified then cleared.
- First admission trial omitted the archive alias on its SERVER copy;
  strict gate caught14 absent server sounds before launching the client.
  FAIL retained; repeat adds the alias to both private roles, not primary configs.

After qualified native acceptance, install ONLY14 decoded original OGG files
into gamma-runtime/gamedata/sounds/material/human/step. LostZone-3D-Hideout
uses an existing sound-directory junction to these same files, verified
through both configured runtime paths. No alias/config edits or exe replacement.
`scripts/install-netcoop-rain-sounds.ps1` preflights all source hashes/sizes
and target conflicts, refuses replacing customized audio, copies with no
overwrite and verifies hashes. First run adds14, repeat keeps14 with zero
additional writes. Primary installation proof retains exact file hashes.
All88 primary exe/config/account/character/world fingerprints remain unchanged;
the14 added sound assets are the ONLY primary runtime change this turn.
All test processes stopped and shared debug empty after acceptance.

Separate native diagnostic correction prepared: StopScriptAnim excludes only
the normal inactive255 sentinel from invalid-part warnings, preserves reset/
movement/resync behavior and warnings for3..254. Actual-method2048-case
differential fixture is included in Foundation/DX11 workflows. Native build/
fixture results still required; no local C++ compilation or primary engine
promotion. This does not fix visible character blinking or all animation issues.
