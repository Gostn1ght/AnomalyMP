# DCP / SIBNIC source compatibility audit

Owner-provided ZIPs were read locally, without installing/executing their binaries. DCP XDB entries selected for analysis were decoded with LZO and their original length/CRC checked. DayZ Cprs text was decoded with output bounds and additive checksums; no encrypted payload was bypassed. Unsafe/obfuscated paths are catalogued but never extracted. Duplicate PBO filenames remain separate entries.

Reproducible tool: `tools/audit-vehicle-sources.py`; parser checks: `scripts/check-vehicle-source-audit.py`. Local evidence is in `J:\LostZone_Work\_work\vehicle_sources_20261015_v2` and `J:\LostZone_Work\_work\helicopter_sources_20261015_v3`. Catalogues record original ZIP hashes, member CRCs, per-entry sizes/offsets and verified text hashes. Model inspection is isolated under the DCP audit folder's `candidate_moskvich`, not in installed game data.

## Existing target

- Cars are `CCar`, `Car.cpp`, `CarWheels.cpp`, `CarInput.cpp`, `CarLights.cpp`, `CarDrone.cpp`, `netcoop_vehicles.inc`.
- Physics is modified ODE, via `CPHWorld`, `CPhysicsShell`, per-bone elements/joints and contact materials. `Physics.cpp` initializes the actual fixed step to0.01s (100Hz); base tuning reference is0.02s. Do not replace the existing world integrator with an independent60Hz position update.
- Existing car movement already uses physical wheel joints, engine power/RPM, transmission, braking, shell masses/inertia and contacts. Server ownership/input/seat checks and pose replication already exist, but full requested prediction/reconciliation and master-durable cross-map vehicle transactions remain unaccepted/incomplete.
- `netcoop_vehicles.inc` currently bounds seats to8 and has legacy cluster-file transit. This is not the master's durable vehicle/passenger transfer requested by the final specification.
- `CCarDrone` is an existing force-based candidate boundary, but includes unconditional gravity compensation while powered; it is not a completed rotor/aerodynamic model.

## DCP

The three supplied archives contain Lost Alpha resource XDBs, compiled engine DLLs/EXEs and optional weather/music/knife/item-animation mods. They contain no corresponding C++ vehicle engine sources. Foreign engine binaries are incompatible with our engine ABI and must not be installed. Optional unrelated mods are not part of the transport port.

The patch's `config/items/vehicles.ltx` has83 sections,68 `vehicle_*` sections;97 vehicle model profiles were extracted from the patch. Six main DCP volumes/patch contain6365 catalogued entries. The representative `vehicle_moskvich` points at `physics/vehicles/moskvitch/veh_moskvich_u_01.ogf`.

Actual model:3,667,959bytes, OGF version4/type10 (rigid skeleton),39 bones, including four wheels, axles, driver/passenger seats, steering wheel, doors and lights. Approximate bounding dimensions are1.6924x1.8086x4.384m, consistent with target car units/axes. IK data exists; exact collision shapes/mass/inertia acceptance still requires native loading. Crucially its embedded UserData includes `models/vehicles/veh_moskvitch_u_03.ltx`, not the similarly namedu01 profile. Copying a filename-matched physics profile would be incorrect.

Compatible parameter families include wheel/door bone lists, reference radius, engine power/RPM, gear ratios, contact spring/damping/friction, lights and fuel. The target converts `engine_power` by0.8*1000, RPM to radians/s and model-profile fuel consumption by1/100000. The outer Lost Alpha item section also has fuel/trunk properties with different semantics; do not apply both fuel scales.

Extra DCP keys `suspension_distance`, `suspension_force_inc`, `suspension_spring_factor`, `suspension_damping_factor`, `suspension_inertia`, nitro and selected dashboard/camera features are not read by the existing target wheel loader. Copying their LTX text alone cannot claim that handling is ported. Add explicit validated ODE joint/engine adapters and measure their behavior before enabling profiles. Mass/shape data resides in model IK as well as optional config overrides.

Provenance is mixed: `veh_moskvitch_u_01.ltx` credits Videoton/Dezowave, while the model's actualu03 profile credits Videoton and a model from Sniper: Ghost Warrior3. No general cross-game redistribution grant is supplied for those assets. Keep candidates staged; do not claim they are open-licensed or ship them as such. Continue independent engine/physics work without copying foreign DLLs.

## Helicopters

The local packages match the SIBNIC project structure:11 client PBOs (nine aircraft packs, scripts and gunner) and one server PBO. Catalogues contain obfuscation/junk filenames and explicit `obfuscated` metadata. However standard Cprs compression of real text entries is readable:55 client text entries and5 server entries decoded with valid checksums, including actual `4_World/mod.c`, `5_Mission/start.c` and config data. Several entries share `config.cpp`; keep all, rather than overwrite one with another.

The two `mod.c` implementations are identical and define Enforce Script `HeliTest_SIB`, with engine/rotor simulation, damage zones and DayZ API calls. Actual flight code contains `SetOrientation` (lines257/353), zeroing angular velocity (328) and `SetVelocity` (387). This implementation does not meet the owner's torque-controlled rigid-body requirement. It cannot be translated verbatim into a claimed physical X-Ray helicopter.

Use the source for input/start/damage/component behavior reference; implement an independent fixed-step force/torque flight model through physical shell elements, rotor inertia/governor, tail anti-torque, aerodynamic losses and ground collision queries. Keep the target's server authority and bounded input queues. Rotor bone animation is presentation, not the physical lift calculation. Aircraft P3D/PAA/material assets also need format/skeleton/geometry conversion and provenance review.

The bundled README and the author's [client repository](https://github.com/moddayz/Helicopter_pbo_client_mod) describe DayZ workshop repacking with SIBNIC attribution; the [server repository](https://github.com/moddayz/Helicopter_pbo_server_mod) limits the server addon to the server side. These are not evidence that arbitrary aircraft assets are freely reusable across engines. No external mod was published or installed.

Archive format references: Bohemia's [PBO format](https://community.bistudio.com/wiki/PBO) and [Cprs/LZSS format](https://community.bistudio.com/wiki/Compressed_LZSS_File_Format). The bounded Python decoder follows the public format, not the flight implementation. It never executes decoded source.

T1 technical findings are recorded. T2–T9 driving/flight/replication/persistence acceptance remains OPEN; no support count, physics fidelity, successful spawn or network load is claimed from file inspection.

Follow-up implementation: doc123 adds an actual optional adapter for the two suspension spring/damping factors through the existing ODE wheel joint. The other unsupported handling fields and full DCP car/aircraft asset integration remain open.

Read-only physical follow-up, 2026-10-16: the candidate Moskvich IK chunk parses to the exact end as39 version1 bone records using the target `bone.h` layout. Its shapes are14 boxes,4 cylinders and21 empty shapes. Four actual road wheels have wheel-joint type3 and10kg each; their embedded spring/damping factors are approximately2.7/2 rear and2.6/2 front. Steering-wheel geometry is not a road wheel. All recorded masses/centers/factors are finite. The sum of all bone masses is1930kg, and of nonempty physics-eligible shapes1720kg (`sfNoPhysics` is bit2; bit0 is `sfNoPickable`). These sums are file evidence, not a measurement of the assembled physical shell's mass/inertia. Evidence remains isolated at `J:\LostZone_Work\_work\vehicle_sources_20261015_v2\candidate_moskvich\physical-audit.json`; no vehicle is installed or spawned by this check.
