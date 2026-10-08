# 68. Graphical failed admission retained a destroyed input receiver

2026-10-08, Codex. Native source fix is in `4cea23d23`; fixture corrections in
`8e1c324d9` and `a42873172`. Failed-admission return is accepted; complete
same-process retry requires the additional dialog-update fix `e609538dd`. Primary
executables, owner accounts and worlds are unchanged.

## Qualified native failure

Ordinary rendering GHA4b74 client, separate private configs/scripts/appdata,
same retained `selftest_destructibles_correlated` server world. No bot render
mode, no owner Firebase credentials, no role elevation. Private menu and
actor-binder instrumentation calls original updates; stage tracing records
startup without skipping GAMMA MCM initialization.

The initial quoted CLI `-start "client(...)"` was rejected by the existing
player console guard. Corrected unquoted `-start client(...)` is permitted,
connects, presents the first actual window frame and loads Cordon geometry,
materials, AI graph and physics. The test initially used the wrong synthetic
login `nbot_960`: the bot driver starts at requested index+1, so the retained
server account is `nbot_961`. Server log explicitly rejects the unknown
account, while the client finishes loading the map and returns to the menu.

The return crashes: retained minidump exception `0xc0000005`, attempted read
of `0x30`, instruction `0x14009dac3`. Exact matching GHA PDB resolves this to
`CInput::iCapture`, `Xr_input.cpp:655`. Disassembly confirms a virtual
`IR_OnDeactivate` call through the prior receiver's vtable. A narrowly scoped,
read-only query of this private process records valid `pInput` and dummy
receiver, plus a freed previous receiver whose vtable is `0x20`; the new
receiver has the expected CMainMenu vtable. It is not a null input subsystem.

`IGame_Level::Load` captures the level before final admission completes.
`CLevel::net_start6` then deletes the failed level directly in its generic,
connect-error and missing-map branches, leaving it on the input stack. Only
the checksum branch already calls `net_Stop`, which releases it. Capturing
menu input on the next frame therefore dereferences the destroyed level.

The common failed-start path now calls `IR_Release` before any deletion or
menu reopening. Existing messages, download/checksum dialogs and full
checksum `net_Stop` remain. Successful admission does not enter this path.
No pointer-validity guessing, swallowed authentication failure, altered NPC
behavior, auth timeout change or permission bypass.

## Fixture and pending runtime verification

`scripts/check-netcoop-failed-start-input.py` imports the actual native
`net_start6` and actual `CInput::iRelease`, with engine API doubles. Its
qualified pre-fix control leaves a captured level at deletion. Fixed cases
cover all four failed-start branches, captured/uncaptured and covered input,
checksum cleanup, dedicated/direct modes and unchanged successful admission.
Assertions check removal before destruction and preserved other receivers.

First Foundation37749891110 / DX1137749891138 FAILED before the full engine:
fixture mock omitted the `IInputReceiver` alias. Alias correction8e1c passes
Linux/GCC/ASan/UBSan in37750201476; Windows rejects the legacy imported
`u32 cnt = cbStack.size()` narrowing warning under the fixture's `/W4 /WX`.
Second DX1137750201469 likewise stops before full compilation. The actual
engine release method and fixture assertions were not changed. Final
a42873172 confines suppression of that one pre-existing MSVC warning to the
imported release method, leaving new code under `/W4 /WX`.

Final Foundation37750844941 and DX1137750844864 SUCCESS. Validated artifact
11539071054, ZIP SHA256
`f3330cd418dc8b99f64f298fc0f42d12912de83a0d702e6c6a7b3afba331e413`,
both executable SHA256
`28859EF757A0BD2BF0365B4D8B4CC2D0040C777117B2AC924D4E410CB3A281D1`.
Only `_build/live/input-recovery-a42873172` received this package.

Two ordinary-client attempts qualified rejection after map loading. The
fixed executable returned to live menu/form updates without the old input
exception. Attempt1 could not execute the retry mailbox because the normal
frontend hides the main menu when showing its login dialog. Its own exact
pending GUID was preserved and cleared; this is an instrumentation limit,
not complete recovery acceptance. Attempt2 preserves original updates in
both windows; seven live callbacks follow rejected admission.

Attempt2 then executes valid native synthetic login in the same client and
closes the menu from Update. Actual exception `0xc0000005`, address
`0x14032c89c`, exact a428 PDB: `CDialogHolder::OnFrame`,
`UIDialogHolder.cpp:256`. `CMainMenu::Activate(false)` calls `CleanInternals`
while OnFrame holds an iterator into the cleared render vector. Production
asynchronous EnterWorld also closes the menu during Update. The raw dump,
logs, package provenance and hashes remain in attempt2-qualification.json;
same-process retry is FAIL, not hidden by the earlier menu PASS.

Source e609538dd rechecks vector size by index and retains no element
reference across dialog callbacks. Non-mutating callback order/count are
preserved. CleanInternals also clears deferred dialogs to prevent closed
popups reappearing. Actual OnFrame/CleanInternals/AddDialogToRender fixture
compares 256 legacy traces and covers callback deletion, deferred additions
and disabled entries. Foundation37756749563 SUCCESS on Linux sanitizers and
Windows; DX1137756749573 full build pending. Repeat the full rejection ->
live menu -> valid admission in `_build/live/input-recovery-e609538dd`, which
has fresh client appdata and the SAME retained private server world.
No primary promotion before scoped native acceptance. Do not cancel a full
build with another source push.

The shared PowerShell result evaluator now rejects the anchored actual
UnhandledFilter footer `at address 0x...`; ordinary inline hitch/profile
addresses remain valid. Source593c1e3ef passed Foundation37753870928 and
DX1137753870992. It changes acceptance diagnostics, not gameplay.

## Evidence and separate integration

Private root `_build/live/destructibles-correlated-4b74ba7f2/graphic` retains
the raw-start minidump, pre-stop client/server logs, input-crash-state.json,
module/stage provenance, original long/short alias attempts and all drivers.
Initial long-path rendering invalid-parameter failure is separate and not
proved resolved by shortening paths. Other early attempts were stopped while
waiting and must not be described as qualified engine failures or successes.

Correct-account native login through `netcoop_login` enters the ordinary game
with Actor19731 using the same GHA4b package. That attempt's subsequent private
observation command did not compile because its Lua path literal had single
backslashes; no damage/checkpoint was performed. The repeat syntax-checks the
literal before launch and uses a distinct GUID result for each command. This
is synthetic local admission, not Firebase registration or owner character
acceptance. MCM startup has a20s script-hang diagnostic; do not call it a
warning-free startup. Headless PASS does not establish visual smoothness.

The ordinary player console also rejects `screenshot`; a command request is
not an image. Current peer integration uses actual presented-frame markers
and native object observations, without claiming a screenshot or genuine
player weapon-hit RPC test. Its damage/restart/destruction peer acceptance
completed on both ordinary sessions as recorded in doc67; rejected-login
recovery on the new fixed executable is still pending separately.
