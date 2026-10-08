# 71. Native local world exclusivity and controlled-exit diagnostics

2026-10-08, Codex. B04 accepted for its original ONE LOCAL DIRECTORY contract.
This is not distributed fencing, a network-share lease or multi-host recovery.

Source `171473a9940abbfe3e15564bbb2dbb7e63ee5c6c`, Foundation37759512127
and DX1137759512199 SUCCESS. Both GCC/sanitizers and MSVC fixtures import the
actual controlled-exit methods. Actual PowerShell result-gate controls PASS.
Validated artifact11541814586, ZIP SHA256
`d20186624d34399c6337fc23f88aba9b965981c61a7121c06422bf842122363c`,
both executable SHA256
`2136C663EE24352B9A232AB1D6A5E70ADDE377A85B369BE9305DB7EBECA356AA`.

Fresh private `_build/live/authority-native-171473a99`, usersettings only,
no owner accounts/world copied. Save directory is absent before the first
actual server starts. Its durable40-byte record is observed/copied BEFORE
interrupting startup. Next server reaches ready as owner, epoch2.
A second ACTUAL server with another network port targets the SAME save
directory and world while the owner is running. The contender writes:

`! [X-Ray][exit] world is locked or lock file is inaccessible`

It has no acquired/ready marker. The authority record's SHA256 is identical
before/after the failed acquisition; its epoch does not advance. The original
owner remains ready without unexpected native/Lua failures. The test stops
only its contender and owner. A third acquisition then reaches ready,
epoch3, and remains alive another30seconds. Stable identity:
WorldID15883345463564265689 / seed8924220031495453929, epochs1→2→3.

Independent parser verifies exact binary records/magic/FNV, the first bytes
sealed before interruption, explicit contender rejection, unchanged authority,
all owner-ready journals and six sealed native/pre-stop journals. The expected
contender error is classified separately; no fatal/SCRIPT ERROR/failed handler
or unexpected native-exception footer in owner/aborted/reacquired logs.
Existing GAMMA NPC-loadout diagnostics remain; this is not whole-modpack
startup acceptance. `acceptance.json` and source/package hashes retained.

The old GHA4b attempt is preserved as UNQUALIFIED: its quiet contender was
not a sufficient refusal oracle. The new diagnostic establishes the expected
native lock refusal in the repeat. It does not retrospectively turn the
old attempt into a PASS. Core do_exit now logs the exact message with a
constant format before the existing FlushLog/MessageBox/TerminateProcess;
dialog/termination behavior and gameplay are unchanged. Both actual methods
have fixture checks for message/sequence, including literal format characters.
Shared PS evaluator rejects the anchored exit record but allows ordinary
debug text mentioning it. The existing actual unhandled-address footer
gate remains. Native compiler/toolchain and runtime checks are GHA-only.

All test processes stopped, shared debug channel empty. All88 primary
exe/config/account/character/world fingerprints unchanged; four primary exe
remain FE829..., no rollout. Current188:25 accepted,35 code/fixtures,
69 partial,59 untouched;163 not fully closed.
