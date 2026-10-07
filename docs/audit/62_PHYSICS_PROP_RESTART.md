# 62. Physics prop restart acceptance (L29 scope)

2026-10-07, Codex. After owner's bounded64 instruction:64smoothness remains
open (doc61); continue remaining tasks without changing normal runtime.

## Native baseline in progress

Private `_build/live/prop-restart-before-ff78b4197`, matching ff78 exes
801763D6..., current patched server Lua and full existing GAMMA archives.
Fresh private appdata, only valid user.ltx copied. No retained world/account
deleted and no primary file changed. Server/bot processes hidden, bot below
normal. Fsgame files written UTF8 without BOM and normal GAMMA working dir.

One real network bot joins. Pick movable nonbreakable obj_physic within150m;
capture global transforms of EVERY body through actual physics Lua API, push
the shell, wait30s, call actual netcoop_world_save, capture at checkpoint,
restart SAME saved world with the same character, then capture all bodies.
Wait for actual clock and healthy bot state before probing. No cleanup/reseed.
Pre-stop logs retained separately; compare real movement and restored pose
before accepting. A matching object origin alone does not prove an opened
hinged door's bone orientation. No native compilation locally.

This first probe checks whichever eligible prop is selected, not all doors,
destroyed objects, ground item gameplay state or offline pathfinding. Those
remain separate unless directly tested. Baseline acceptance still pending.

## Native baseline failure confirmed (2026-10-08)

Selected ID16773, sectionphysic_object, namemar_physic_object_0008, one body.
Force changed position AND orientation, then actual netcoop_world_save returned
SAVE committed. Immediate post-commit pose equals the settled moved pose.
Restart explicitly loaded selftest_prop_restart_b; same object ID/section/body
count returns EXACTLY its initial transform. Position error3.811287m,
maximum transform coefficient error2.659576. No persistence PASS.
All evidence retained in snapshots.json, acceptance.json (passed=false), both
phase logs and pre-stop copies. Both server/bot processes stopped.

Reason: world checkpoint intentionally bypasses whole single-player ClientSave
(dedicated previously crashed there and rejects M_SAVE_PACKET). Runtime physical
bones never reach the ALife entity's saved_bones before its snapshot. Prop
replication does not itself persist the pose. New scoped adapter must call only
the existing physics serializer/decoder, update coherent root position/angles,
and let any capture failure preserve the old world commit. It must not call
inherited game-object/Lua net_Save hooks or alter simulation/AI/cadence. Fixed
CI/build and identical native restart acceptance remain pending.

## Scoped implementation pending CI/native acceptance

2026-10-08: CPhysicObject adapter calls CPHSkeleton::SaveNetState only,
then the existing SPHBonesData decoder into temporary storage. Full decode/EOF
and body count checked before replacement; current root position/angles copied.
Entity identity, section, parent, startup animation and fracture source retained.
37+8*body_count strict packet bound checked before serialization. Existing
engine quantized pose codec retained; this scope does not preserve velocities
beyond the stock physics-save codec. No whole object/Lua net_Save hooks.

Checkpoint captures live props before ALife save; skips removed/attached,
shell-less/zero-body, unrelated objects and explicit flNotSave props. Offline
entities unchanged. Capture refusal/exception keeps previous committed slot.
GHA fixture executes actual adapter/traversal with API doubles and tests metadata,
repeat replacement, malformed decode, overflow and selection. World-store fixture
executes actual checkpoint with injected capture refusal/exception. Real native
pose/restart proof still required; no runtime promotion or L29 completion yet.
