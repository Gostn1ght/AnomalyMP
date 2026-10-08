# 65. Physics-skeleton checkpoints (2026-10-08)

Status: implementation under verification. L30 remains partial; no increase
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

## Verification in progress

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
- A focused baseline is now running in
  `_build/live/fragment-pose-baseline-4fa43fe7d`. A private test-only section
  instantiates the actual physics-skeleton class with the unchanged stock
  bucket visual. Complete server/client config copies differ only by the
  appended section; the primary configs remain untouched. This can test
  pose persistence for that class, not natural joint-fracture generation.
- First Actions runs `37726751994` and `37726751999` failed at fixture
  compilation: the newly added spawn instance reused the existing matrix
  variable's name. The fixture variable is renamed; assertions and engine
  code are unchanged. Both Linux and Windows failures are retained in
  `_build/live/fragment-ci-*.log`. No native package from these runs.

## Open limits

The stock codec does not retain full velocities or an uninterrupted physical
trajectory. General `CDestroyablePhysicsObject` accumulated health is still
open. All models/maps, offline routing, graphical interactions, max-view
smoothness at 64 players and 512-player load are not accepted by this work.
Main executables, world saves and account data remain unchanged.
