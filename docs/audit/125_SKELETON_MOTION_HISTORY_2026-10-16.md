# Initialize skeleton motion history from the actual pose

The DX11 motion-vector path in `CSkeletonX::_Render` read `CKinematics::CurrentFrame`, `Matrix_Temp` and each bone's `mRenderTransform_temp` before their first initialization. `CBoneInstance::construct` initializes the current transform, not those history matrices; model copy/spawn did not reset renderer history either. A large garbage frame value could also permanently prevent history updates due to the old unsigned greater-than comparison.

The actual history update now belongs to `CKinematics::UpdateMotionHistory`. On first draw, or after a rendering gap, previous/current histories are both seeded from the actual current world and bone pose. Consecutive frames advance the previous history; repeated child/shadow/scope passes in one frame cannot advance it twice. Unsigned frame subtraction handles counter wrap. Constructor, Copy and Spawn explicitly reset the history, including model-pool reuse in the same frame.

No current pose, bone calculation rate, animation, graphics preset or gameplay state is changed. This repairs an independently confirmed uninitialized-read defect in temporal presentation; it does not prove that the owner's missing meshes/scopes or water seams are fixed.

CI-only `check-native-skeleton-motion-history.py` executes the actual reset/update bodies with deliberately NaN-poisoned histories, checking first draw at zero/arbitrary/max frame, all bone/world matrices, normal consecutive updates, repeated passes, culling gaps, model reuse, backwards counters and wrap. Full engine CI and game visual acceptance are required separately. The game is not launched.

Verified: run38854891742 completed successfully for01670ad8767c568d8481109f6e8d8f979075419a, including all Linux/Windows fixtures, the new actual history fixture, full DX11 engine compilation and artifact upload. Downloaded client/server EXEs independently match SHA256 `13e25074a496358556d3bc29158ab4e0a86d5d87c1ed37511ca69d329dd22ea7`. Native binaries are installed to the friend overlay and srvtest; patch000020 and final installation evidence are recorded in doc126. No game was launched and visual acceptance remains open.
