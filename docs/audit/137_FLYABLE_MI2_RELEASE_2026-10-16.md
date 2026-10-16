# Flyable Mi-2: implementation and release

Owner 2026-10-16 authorized finishing Claude's helicopter and publishing the
matching client update through the launcher first, with an updated friend
overlay in `J:\LostZone_Work\Lost Zone Server`.

## Implemented in 94d48f8a2

- A separate `veh_mi2_heli` CCar section and `veh_mi2_pilot.ogf`, derived from
  the existing Mi-2; original AI helicopter sections/models are unchanged.
- Server fixed-step force/torque flight, collective with vertical-speed hold,
  commanded pitch/roll, pedals, forward bank turn, drag, ground effect and
  spool-up/down. No direct position/velocity override in the flight method.
- Six seats, vehicle input/replication/trunk and existing cluster-file transit.
  The latter is not proof of master-durable vehicle/passenger transactions.
- Rotor animation follows RPM; physical collision blades remain stationary.
- Admin-only spawn `spawn veh_mi2_heli`; Space up, Ctrl down, W/S pitch,
  A/D roll, Q/E yaw, O engine, F exit. Pilot exit stops the engine in flight.

## Pre-release correction

`CCar::bone_map` is **static construction scratch**, cleared by
`ParseDefinitions()` and populated when a shell is constructed. Using it in
every helicopter physics step selects the last constructed car's body and can
leave a dangling pointer after that car is destroyed. The flight step now
selects element zero from its own `PPhysicsShell()`, checking shell, visual,
element count, body pointer and finite positive timestep first. Root element
zero is the same shell-owned body used by the existing car exit velocity.

`check-native-helicopter.py` executes the actual flight method with two
independent shells, empty/missing shell and invalid timestep cases, and a
limited vertical force integrator for hover/climb/release/descent/spool-down.
It deliberately supplies no shared bone map. Native compilation runs only in
Windows GitHub Actions. The vertical harness does not replace ODE collision,
model animation, cockpit/seat or multiplayer gameplay tests.

`check-netcoop-helicopter.py` was also added to the DX11 Linux checks. It
passed locally: model/profile/section, 24 bones, six seats and 20 flight keys;
the existing vehicle Lua test also passed.

## Patch 000021 prepared

Built from `94d48f8a234eb74af2995e28438cf707c2d20d53`, diffing each role
against resource patch20 source `d265adea1cd39be7e329baac0c1199f0e4c8ffa5`.
Output: `J:\LostZone_Work\_work\patch_000021`.

- Client archive SHA256:
  `39a2b043258d1f041b79edc15b0158ddbc561d6c1ab12319ad2fe16a1ac420cb`.
- Server archive SHA256:
  `d9385d34022d13e0c6fb7fe093b616ca42edf85acd295e28162d976a762138e0`.
- Both archives contain the new model; client also contains the pilot hint
  script. Four client and two server config files remain loose for GAMMA.
- Model SHA256:
  `3c0cbabfe0a1c203a58a0d6c778801f46dd235749ec73758c6316411bc2007d0`.

## Verification and delivery status

An isolated model compatibility probe at
`J:\LostZone_Work\_work\heli_qa_20261016` (baseline c3acff438, no owner data)
created the server entity but reproduced `CKinematicsAnimated::ID_Cycle`,
`motion_ID.valid()`, missing `$editor`. This is the same unchanged car startup
path in 94d48f8a2. Startup animation now resolves with `ID_Cycle_Safe`, falling
back to `idle` when available; missing optional cycles do not assert. Skeleton
creation uses the same safe helper. Helicopter startup leaves the rotor blend
created by Init alone, avoiding a second PlayCycle replacing its stored blend.
The native fixture executes the actual helper for missing `$editor`, valid
idle, missing both, and null visual. The compatibility probe is not flight
acceptance and its fatal error remains part of the evidence, not a passing run.

Full CI, isolated native spawn test, installation and launcher publication
are pending. Do not call flight/animation/two-client acceptance complete.
Master `e3fcbf1f1` is retained; no account, character or world is wiped.

Full DCP integration, the owner's FBX conversions, M3 and H09/H11 remain
separate open work. Doc136's "helicopters not started" reflects its earlier
snapshot; the implementation above supersedes it without claiming acceptance.
