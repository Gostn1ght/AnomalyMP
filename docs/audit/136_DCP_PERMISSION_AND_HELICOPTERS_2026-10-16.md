# DCP permission, first car, helicopters (2026-10-16)

- Owner: personally obtained written permission from v2v3v4 to use the DCP models in Lost Zone. Keep a copy of that letter with the project's licences; credit as agreed with the author.
- That permission covers the pack author's own work. Profiles that state a model came from another commercial game (Moskvich u_03: Sniper: Ghost Warrior 3; Skyline: GRID; GAZ-24: DayZ) and textures named after PUBG are not covered by it and stay out of releases unless their rights holders agree.
- First car to port (T2): Niva 2121 `veh_niva_u_01` (Lost Alpha base, Videoton rework), extracted to `J:\LostZone_Work\_work\dcp_niva_u_01` with `tools/extract-vehicle-assets.py`.
- Helicopters (T5-T7): not started. The SIBNIC DayZ helicopter code sets velocity/orientation directly (doc 121) and cannot be ported as physics; Lost Zone needs its own rotor model on the ODE body (lift and torque from collective/cyclic/pedals, drag, ground effect), controls, server authority and replication like cars. Helicopter models need the same rights check.
