# 81. ADMIN teleport and retained native relation crash

2026-10-08. Follow doc80. Original188 counts27/33/69/59 unchanged.

Source9043440b8eeba4ab5b9cfd20edb2e6ae75c4dc15:
Foundation37835454753 SUCCESS both compilers; DX1137835454767 fullSUCCESS.
God actual native role/connection/predicate fixture and actual fragment
selection/replica fixture passed. Preceding8a935d67a Foundation37834873675:
Linux PASS, Windows test-stub BOOL/bool comparison and implicit int->u16 warnings
under W4/WX; fullDX1137834873642 failed BEFORE engine compilation.904 fixes
only those fixture types; warning policy retained. New package download pending.
No primary EXE rollout. Scoped RP/pickup proof is on328 plus exact pickup Lua.

The same private328 lab ran until a real server crash at22:49:49 local.
Retained appdata/server/logs/xray_gameplay_server_serverauthority_10-08-26_22-49-45.mdmp
and complete sealed-after-server-crash client/server logs. Owner worlds untouched.
Server19644 exited; private client15352 was stopped after sealing; now no game
processes. Preserve current world/account/characters, do not reseed for PASS.
Two late parent-assertion failures remain alongside real earlier item ownership
journal; the player died/drop/respawn after the successful pickup, see doc80.
Later client inventory quick-use error _g_patches.hspairs(nil) is ALSO retained
and remains open. Do not call the whole run clean from earlier scoped acceptance.

Native crash evidence: WER AV0xc0000005 at module+5c6e9f resolves through matching
GHA PDB to CScriptGameObject::GetRelationType, script_game_object_use.cpp147.
Dump exception is a read at0x8; RBP=0. Matching PE instruction at RIP is
mov rdi,[rbp+8], dereferencing the nil `who` Lua argument. Lua trace originates
at xr_conditions.actor_friend -> xr_meet.update_state -> NPC hit callbacks,
not the RP/pickup diagnostic observer. Add native nil-who return using existing
invalid-target Dummy contract. On dedicated server only, wrap actor_enemy,
actor_friend, actor_neutral, see_actor: absent actor/NPC returns false; normal
arguments/multiple returns forwarded unchanged. This avoids treating Dummy
as an enemy when there is no player. NPC AI continues; no count/rate/vision cut.
Actual helper Lua51 cases + existing AI/items/scope checks PASS. Whole actual
native relation function fixture added to GHA; full/native soak acceptance pending.

ADMIN demo teleport source: engine demo Enter now asks game persistent handler.
Pure client sends only a verified-ADMIN request; it does not ForceTransform itself.
SP/local engine path remains old ForceTransform. Lua command only accepts three
finite/bounded coordinates, actor ID comes from authenticated sender. Native
helper rechecks bound role/owner/alive/admission and current-map geometry bounds,
moves authoritative body and owner position, clears pending jump/movement, then
sends reliable GE_MOVE_ACTOR only to owner. Other clients receive ordinary
authoritative movement snapshots. Actor MoveActor clears controlled client's
old prediction history/pending inputs, preserving ALL sequence/ACK counters;
resetting those to1 would make the server reject future movement. Ordinary
client forged teleport events remain denied by existing authority gate.
Actual Lua role/parse/native-rejection cases PASS. Actual request/server function/
MoveActor fixture added to GHA, not locally compiled. Native demo acceptance pending.

Mutant investigation remains open. Do not add multipart animation replication
merely from reading dead controller code: controller.update_frame currently
returns after inherited call; the split selection calls below it are commented
out. Server animation controller DOES call UpdateTracks; a missing-render guess
alone is not evidence. Inspect actual motion/phase/progress and client poses on
real mutants before changing animation or scheduler behavior. No mutant source
changes or claimed mutant PASS in this continuation.

After qualification, restore private owner maps from retained worlds, include
requested Darkscape(k01_darkscape) route if appropriate, no interactive client
while owner asleep. Then resume remaining188, easy before medium before hard.
