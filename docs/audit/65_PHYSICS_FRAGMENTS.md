# 65. Physics-skeleton checkpoints (2026-10-08)

Status: source/CI/package and scoped native pose restart PASS. L30 remains partial; no increase
to the 22 fully accepted stages. No primary-runtime rollout.

## Problem and scope

`CPhysicsSkeletonObject` is a separate runtime class from `CPhysicObject`.
The authority checkpoint traversal previously captured neither its current
body poses nor its fractured bone root/mask. The existing server type,
`CSE_ALifePHSkeletonObject`, already supports the stock skeleton save codec;
no new world, character, or network format is required.

The adapter captures stock `CPHSkeleton::SaveNetState`, decodes into a
temporary `SPHBonesData`, checks body count and complete packet consumption,
and then updates the existing entity's bones/flags and XYZ pose. It keeps
identity, parent, section, source ID, startup animation, and client data.
The stock `flNotSave` flag continues to exclude temporary debris. An
unresolved `flSpawnCopy` is rejected instead of saving a live-source dependency.
Capture failure refuses the world checkpoint through the existing path.

The class also now returns immediately if the inherited spawn failed,
before deleting its collision model, restoring physics, or enabling it.
`CPHSkeleton::Spawn` returning false is the normal non-copy route and must
not be treated as an inherited spawn failure.

## Verification

- The existing actual-method/actual-traversal native fixture now includes
  this separate class, metadata and bone mask/root retention, decode errors,
  bounds/type/identity/finite-value guards, unresolved copies, temporary
  debris exclusion, and the refused-spawn path. Native execution is GHA-only.
- The real PowerShell result evaluator rejects the new fragment-capture
  error record. Local PowerShell checks and Python fixture syntax pass.
- Private discovery on validated GHA source
  `4fa43fe7d0231df3c5ff4fce4a6bb3c5af70342f` found the stock destroyable
  objects on Cordon. Private root:
  `_build/live/fragment-discovery-4fa43fe7d`.
- A zero-damage stock impulse probe on four existing objects completed
  in `_build/live/fragment-fracture-baseline-4fa43fe7d`. It retains one world
  across its restart, with separate pre-stop logs. This is a trusted server
  probe, not a graphical player hit/RPC test. All four shells reported
  `is_breakable=false`; the impulse produced no physics-skeleton objects.
  It is therefore not a fragment/fracture acceptance case.
- A focused baseline completed in
  `_build/live/fragment-pose-baseline-4fa43fe7d`. A private test-only section
  instantiates the actual physics-skeleton class with the unchanged stock
  bucket visual. Complete server/client config copies differ only by the
  appended section; the primary configs remain untouched. This can test
  pose persistence for that class, not natural joint-fracture generation.
  The baseline failed the original pose gates: both bodies returned to their
  exact initial pose after SAME-world restart, position error 1.885136m and
  rotation-coefficient error 0.988977. The object moved and settled; both
  phases ended 1/1 playing, one recovered phase1 retry, no terminal/Lua/fatal/
  shader/save errors. CSE flags stayed zero with no stored bodies. Common
  healthy proof passed; `baseline-summary.json` retains provenance and four
  pre-stop log hashes. This is a reproduced omission, not an entry/load failure.
- First Actions runs `37726751994` and `37726751999` failed at fixture
  compilation: the newly added spawn instance reused the existing matrix
  variable's name. The fixture variable is renamed; assertions and engine
  code are unchanged. Both Linux and Windows failures are retained in
  `_build/live/fragment-ci-*.log`. No native package from these runs.
- Correction/source `c8716c4c1f70d1a96e6a5e6aff549c82a5bd38bb`:
  [Foundation 37727137941](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37727137941)
  passed Linux/GCC+ASan/UBSan and Windows/MSVC actual-method fixtures;
  [DX11 37727137945](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37727137945)
  passed checks and the full engine build/package/upload. Artifact
  `11528723681`, ZIP SHA256
  `51d85e70e0714cea641e5ebe65b8b0332091de50ed6aaf7047ba51ae81e0f466`.
  Both exe SHA256
  `212BA94B9C60DAE1747001EB38131712D7665AD50D7CC1DAD9B55C4C1AFAAEB7`.
  Exact source, built-from, ZIP digest and exe manifest validated in
  `_build/gha/fragments-c8716c4c1`.
- Only `_build/live/fragment-pose-fixed-c8716c4c1` received the new package.
  Private scripts/configs/user settings match the baseline; no saved world
  or character copied. Before running the fix, the original recorded spawn
  position was pinned, and full initial-pose equality added to the comparator.
  Original force, settle period and 0.05m/0.04 restart gates remain.
- Fixed native case PASS: full initial body matrices exactly equal the
  failed control. The object moved 1.885589m, rotated (coefficient change
  0.989080), and settled. Both bodies retain their pose after SAME retained
  world restart: maximum position error 0.002883m and rotation error 0.009167.
  Actual CSE saved flags include `flSavedData`, with bone mask31, root0 and
  body count2. Metadata/source ID/startup animation retained; both phases
  final1/1 playing, no admission retries, no terminal/Lua/fatal/shader/save/
  capture errors. Original baseline remains FAIL with common healthy proof.
  The raw logs retain prior GAMMA loadout warnings; these are not new script
  exceptions and this is not a claim of warning-free general gameplay.
  Retained NPC loadout records: four in the baseline's two server logs, six
  in the fix's two server logs (including missing weapon/ammo configuration).
- `native-summary.json` in the fixed root records exact package provenance,
  eight pre-stop server/bot log hashes across control/fix, driver/snapshot/
  config evidence hashes, strict initial-pose comparison and all four
  unchanged primary exe hashes. Both debug channels empty, processes stopped.
  Guarded failed-base-spawn and no-save debris paths have GHA fixture proof;
  they were not forced in this native case.

## Open limits

The stock codec does not retain full velocities or an uninterrupted physical
trajectory. General `CDestroyablePhysicsObject` accumulated health is still
open. All models/maps, offline routing, graphical interactions, max-view
smoothness at 64 players and 512-player load are not accepted by this work.
Main executables, world saves and account data remain unchanged.
