# 80. Owner gameplay reports after four-map launch

2026-10-08. Original188 counters27/33/69/59 remain unchanged. Fix gameplay
reports first, then return to remaining stages, easy before medium before hard.

Historical launch (all four processes absent when checked later on 2026-10-08;
their records below are stale, not evidence of current running state):
Cordon1477/PID7732, Swamps1467/PID20264, Garbage1487/PID21592,
Bar1497/PID14656. Native qualified GHA21351fe49 engine, separate worlds/account
namespace, test_admin granted ADMIN by native server console. Primary engine,
accounts, characters and worlds protected. Native owner client16940 entered
as test_admin(admin), Actor23591, completed precache, and owner played. It
later disconnected/quit normally; currently no client. Do not force-reopen
while owner is testing elsewhere. Do not shut down the four requested servers
as ordinary probe cleanup. Persistent metadata running-servers/running-client
must be checked against current processes; a closed client makes its PID stale.

## Continuation: qualified328 and pickup preferences

Foundation37824728218 and DX1137824728127/source3289dfd966e0ade60f797416f361e6167d9bdc31
SUCCESS. GCC/MSVC actual RP prefix1024 cases + actual CUIButton click PASS;
actual replica-copy10000 cases PASS. Artifact11571787222, ZIP
3cf1e34d713d7acf1c3a4ef119fb01dbcb88e6f9b6e64b686cb2822a059da7aa,
both EXE4662354E2431A67C4505DC5A91014A2FB11111DD107006B9B32385A21E38B722.
Installed only into separate _build/live/owner-gameplay-repro-3289dfd96.
Private test_admin copied; independent retained lab world, no owner worlds copied.
Lab server19644. Client long lab aliases caused early AV (WER21c6bb resolves
to error-handler print_stack, not necessarily the original assertion). Retained
failed aliases; shortened client appdata/configs/scripts paths without changing
qualified archive/root spelling pair. Subsequent client10188 actually admitted
ADMIN, precache0. Native Z + mouse press/release caused hands_pockets to finish,
but diagnostic wrapper wrote into its module namespace rather than _G, so
callback counter stayed0 and RP_STOP_FAIL was logged. Preserve this trial;
do not call it a full PASS. Correct _G observer and bounded client-object scan
(client ALife facade iteration was empty); client25284 retry in progress.

Owner session log explicitly rejected cl_cod_pickup_mode, g_multi_item_pickup,
g_draw_pickup_item_names while loading settings before authenticated role.
Allow exactly these local pickup UI/control preferences in actual console
classifier; expand GHA differential cases. g_autopickup already allowed.
No server ownership validation or gameplay/debug allowlist relaxed. This fixes
settings load / disabled COD callback prerequisite; floor pickup and hovering
still require actual item/animation/ownership evidence. No primary rollout.

Owner briefly requested adding Darkscape (k01_darkscape) to transition play,
then left to sleep and instructed autonomous fixes again. Preserve four-map
worlds; do not launch an interactive client unnecessarily. Later restore/add
maps from retained worlds when qualified gameplay fixes are ready.

Startup proof sealed in qualified-startup.json/acceptance/*.log and two native
PNGs, BOTH viewed: Cordon world/HUD then PDA over world. The full session is
not clean: later MCM ShowDialog pure-virtual error; visible Dot Marks dependency
warning. These do not invalidate completed entry/render, but remain open.
The Unknown account rejection was an injected nbot_961 login in ui_main_menu
copied from an earlier diagnostic tree. Restored exact canonical/primary menu
SHA1950A780A386BAA3D888BF6D35D323DE66137464B031426704781C8AC931F533;
no recovery probe/forced bot login remains. DPAPI decrypt checked silently:
test_admin approval1 key matches actual ADMIN server hash. No password rotation
or account deletion. Launch preflight hashes clean menu and actor binder.
Failure logs/backups and preparation-helper corrections retained privately.

Owner reports, in priority order:

- RP Stop button does not work; pose locks actor.
- Barrels/boxes and their fragments fly violently when shot; wall contacts
  cause continuing particles and terrible sound. Not just inventory drops.
- Weapons on floor cannot be picked up and sometimes hover; include item
  pickup/physical state in this same investigation.
- Mutants less smooth than stalkers, animation stalls, some remain immobile.
  No population/vision/cadence reduction allowed.
- ADMIN god mode ineffective; demo_record teleport is rolled back. Server
  authority must validate/admin-authorize these rather than opening cheats
  for ordinary players.
- After these fixes, resume original188 autonomously.

RP source correction0ed5ab5ea: CLevel::IR_OnKeyboardPress returned for every
non-Z/system key during a pose BEFORE UI delivery. Mouse press never reached
the wheel's Stop button. Forward blocked keys to an EXISTING top UI receiver
when input enabled, then return unconditionally, even if UI declines. Actor
movement/fire remain blocked; Z/system exceptions and non-RP paths preserved.
Release already follows ordinary UI delivery. Actual native prefix matrix
and actual CUIButton press/release are compiled only on GHA. Linux1024 cases
and click PASS; Windows failed because a test stub global actor shadowed the
real method local under W4/WX. Rename ONLY stub to test_actor; no warning
relaxation or actual method substitution.0ed Foundation37823087810/DX11
37823087659 fail Windows fixture BEFORE full engine; no new EXE installed.
Native/human RP click acceptance still pending.

Physics source finding: buffered pure-client replica bodies are fixed; real
FixBody clears linear/angular velocities and force/torque, and substitutes
artificial ODE mass. But replica set_State reinstalls server angular velocity,
force and torque; only linear velocity was cleared. Real PHElement::set_State
applies all four fields. Legacy inventory follower already clears all four.
Copy-only buffered preparation now clears all four, retaining authoritative
snapshot queue, pose interpolation, previous pose reset and enabled collision.
Server mass/hit impulses/fragment generation are unchanged. This prevents
unintended local integration on pose-driven replicas; do NOT claim the whole
barrel/wall behavior fixed before native repro. Actual10000-state preparation
fixture in GHA checks zero dynamics, retained pose and unchanged source state.

Further evidence/investigation:
physics contact criterion uses ODE point velocity times sqrt(ODE mass), without
clamping virtual fixed mass; volume expression and per-contact particles can
amplify invalid replica dynamics. Fix cause first, not arbitrary sound masking
or blanket physics/AI caps. Fragment transition still needs authority/client
native comparison (CPHDestroyable::NotificatePart). User cfg has
cl_cod_pickup_mode off. Callback exists in actual engine/GAMMA, but the COD
update returns before notifying it when disabled, so Dot Marks sees no firing.
This alone does not prove why legacy F pickup fails; trace actual target/use/
before-item callback/server ownership instead of falsely claiming missing API
or merely forcing a setting. God/demo need per-player authority design.

Latest pre-RP Lua source1b01b013d: DX1137816511889 fullSUCCESS. No intervening
C++ changes relative to qualified213 engine; isolated story-dialog guards
verified locally and in Actions. B06nine prepared NOTRUN; defer while this
owner session is using servers. No primary C++ rollout or new188 acceptance.
