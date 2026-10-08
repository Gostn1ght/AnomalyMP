# 80. Owner gameplay reports after four-map launch

2026-10-08. Original188 counters27/33/69/59 remain unchanged. Fix gameplay
reports first, then return to remaining stages, easy before medium before hard.

Four servers remain running in PRIVATE LostZone-4Maps-Test:
Cordon1477/PID7732, Swamps1467/PID20264, Garbage1487/PID21592,
Bar1497/PID14656. Native qualified GHA21351fe49 engine, separate worlds/account
namespace, test_admin granted ADMIN by native server console. Primary engine,
accounts, characters and worlds protected. Native owner client16940 entered
as test_admin(admin), Actor23591, completed precache, and owner played. It
later disconnected/quit normally; currently no client. Do not force-reopen
while owner is testing elsewhere. Do not shut down the four requested servers
as ordinary probe cleanup. Persistent metadata running-servers/running-client
must be checked against current processes; a closed client makes its PID stale.

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
