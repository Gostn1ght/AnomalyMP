# 70. Native world identity across interrupted startup

2026-10-08, Codex. B03 accepted for its original local identity/seed/epoch
requirement. B04 is subsequently accepted separately in doc71; distributed
fencing remains open.

Validated GHA source `4b74ba7f2b958ec1d4fad26ec68140bc97154816`,
DX11 run37732900805 and Foundation37732900872 SUCCESS, artifact11531705521.
Executable SHA256
`E4EDE44A70CAEEB43DC9CA00968ECDAE0CF838BDF7D44F4E35341E2EC15FE7A0`.
No local native compilation. Fresh private
`_build/live/identity-native-4b74ba7f2`, usersettings only, no copied accounts
or world data. Default GAMMA population and AI are unchanged.

The first real server is interrupted as soon as its40-byte durable authority
record appears, before any server-ready clock marker. The exact observed
bytes are copied to `aborted.authority` BEFORE stopping the process. No
invented record or inferred replacement for a missing first observation.
The actual store durably writes its epoch before bootstrap; native fixtures
already verify this ordering and failure behavior. The acquired Msg may
still be buffered when the process is stopped, so its absence is not used
to infer the identity. The checksummed durable bytes are the identity oracle.

Two following real server startups reach ready on the SAME private world:

- WorldID remains `13564581398834934011`.
- Seed remains `14696362713997730183`.
- Epochs are exactly1 (interrupted),2 (ready),3 (ready).

The failed startup's epoch is not reused. The final server stays ready another
30seconds. An independent Python parser checks all three exact binary records,
schema magic, little-endian fields and FNV checksum, as well as both ready
journals and the first sealed authority bytes. `acceptance.json` seals three
native journals and two logs copied before normal test shutdown. No fatal,
SCRIPT ERROR, time-event error, failed handler or native exception footer in
these journals. Existing GAMMA NPC-loadout diagnostics remain separate;
this is not an assertion of a clean entire modpack.

The earlier combined exclusivity trial in
`_build/live/authority-native-4b74ba7f2` is NOT accepted: the contender remains
alive without an acquired/ready marker or explicit rejection reason in its
journal. Its timeout and evidence are retained in unqualified-attempt.json.
This identity-only repeat does not test exclusivity and cannot close B04.
The old xrCore controlled-exit handler flushes but does not log its reason;
source171473a99 adds a message before the existing flush/dialog/termination
sequence, with actual-method fixtures and strict log-gate controls. Both
Foundation37759512127 platforms and DX1137759512199 full build SUCCESS.
Do not diagnose the old contender from its quiet process state alone.

All test processes stopped. Shared debug channel empty. All88 primary
exe/config/account/character/world fingerprints unchanged; no rollout.
At B03 acceptance:24 accepted,36 fixture/code-only,69 partial,59 untouched.
After the separate B04 acceptance in doc71:25/35/69/59.
This does not establish distributed lease recovery, clock wire sync,
all-map chunk hydration, visual64/max-view behavior or512-player capacity.
