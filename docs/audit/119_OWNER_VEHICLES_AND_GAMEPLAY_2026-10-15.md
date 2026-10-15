# Owner additions, 2026-10-15

The owner's latest direct request changes the vehicle source to Definitive Car Pack (DCP), including its handling/physics, and supplies two SIBNIC DayZ helicopter ZIPs. The pasted transport requirements are retained as doc118. They supplement existing tasks; they do not authorize launching game clients/location servers, publishing the launcher, or replacing engine DLLs with Lost Alpha binaries.

New reports, all OPEN for game acceptance:

1. Grenade throws/explosions and Bulldog shots take host TPS to zero while client FPS stays normal. Audit blast/fragment/projectile physics and unbounded native searches. Do not equate a finite-vector fix with proving this exact hang.
2. Corpse withdrawals say `Transfer refused: no free inventory slots` despite apparent space. Keep armor/backpack/weight/item-dimension capacity and the separate lossless512-item bound. Distinguish cell overflow, record limit and invalid/incomplete ownership tree. Screenshots are dated2026-10-13 and cannot alone establish behavior of patch000019/native99 deployedOct15.
3. SVD low/misaligned in NPC hands, possibly player hands. Existing broad pose fitting is not visual acceptance of this weapon.
4. Visible water polygon boundaries; scopes and character meshes distorted/missing. Inspect client shader/config/model path; no arbitrary global preset changes can be claimed as a fix from screenshots alone.
5. Flashlight/chem-light shadows fall across the wrong areas; first-person hands also occlude the light. Keep this distinct from the previous backward torch direction correction.
6. In vehicles, forbid drawing held items/weapons and firing; consumption remains available. Enforce on server and through UI/Lua/forced inventory activation, not only key handling.
7. Other players must see medicine/food/drink use animations. Existing local first-person item effects are not replicated third-person actions.
8. Cannot butcher mutants. Route F interaction to the server-backed mutant loot adapter before local SP callbacks can mark corpses looted. Verify live GAMMA window and multiplayer item creation, including failed creation and repeated requests, before closing.

Transport stages from doc118 remain distinct:

- T1 audit real package formats, author/terms, ODE/CCar parameters, bones and dependencies.
- T2 one actual DCP car, compatible asset/config adaptation and physical driving.
- T3 drivetrain/surfaces/damage/fuel/repair.
- T4 vehicle authoritative replication/prediction/reconciliation/passengers.
- T5 physical helicopter body, rotor dynamics and controls.
- T6 stable aerodynamic effects/damage.
- T7 helicopter multiplayer integration.
- T8 seats/interactions/sound/animations/world persistence.
- T9 measured load, latency/loss/restart/transfer acceptance.

Existing M2b primary player persistence/admission/hydration, M3 GAMMA quests/rewards, H09/H11 native NPC/item transfer, traders and earlier visual/crash reports remain open. No stage is closed merely by listing it here or passing isolated fixtures.

Supplied archives: three `drive-download-20261015T173627Z-1-00{1,2,3}.zip` in Downloads; `Helicopter_pbo_client_mod.zip` and `Helicopter_pbo_server_mod.zip` in the owner's referenced conversation outputs. Audit tool `tools/audit-vehicle-sources.py` reads bounded catalogues and selected text into separate work folders; it never installs or executes supplied DLL/EXE files.
