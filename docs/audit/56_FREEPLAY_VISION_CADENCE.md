# Restore freeplay perception without far-target skipping

2026-10-07. Owner requires GAMMA NPC/mutant behavior and population, including
smooth movement throughout visible range, with no slower reactions introduced
as an optimization.

## Removed behavior change

Dedicated `Feel::Vision::o_trace` had a far_budget of 12, introduced in
f39224a9f. Later e233e5bdc exempted players of both actor classes. Distant
non-actor targets beyond 30 m were still skipped in round-robin windows,
retaining stale fuzzy visibility state. NPCs/mutants therefore could perceive
one another later than in freeplay. A crowd can also spend the round-robin
window on exempt players, leaving distant non-actors skipped in that update.

Restore the exact actual function from this repository's pre-budget revision
843e5eef060a0e9bca79ddb537f0e10bfc40b7ae. Remove the now-unused cursor member.
All target classes and distances follow original order/cadence. Existing
ray/triangle caches, visibility thresholds, collision callbacks, sampled points
and fuzzy accumulation remain byte-for-byte identical in the function.
No new sharing of observer-dependent ray results is introduced. A result from
another NPC is not interchangeable when endpoints, ignored owner, material
callbacks, bones or moving occluders differ.

## Evidence and limits

Pin the historical function with normalized LF SHA256 in
scripts/fixtures/freeplay-vision/o_trace.cpp. check-netcoop-vision-cadence.py
compares the actual production function to that pinned history, and verifies
the cursor was removed. This is source-equivalence proof of restoration,
not a geometry simulation, performance benchmark or live visual acceptance.
The full engine still compiles only in GitHub Actions.

Restoring perception can increase CPU relative to the lossy round-robin code.
Do not claim an FPS gain from this correction. Reducing CPU must come from
measured redundant work, safe caching or independent parallel work with the
same resulting decisions and latency. Keeping a behavior regression to obtain
a better benchmark is incompatible with the owner requirement.

Combined native acceptance still needs 16/64 same-point and close-NPC tests,
delivery callback vs bot frame gaps, real graphical movement at maximum
visibility and reaction checks. Population and scheduler intervals remain
unchanged. No new live audit checkmarks are justified by this source check.

## Independent removal of redundant replication work

Full-rate records previously calculated each observer's Euclidean distance even
though their cadence/budget bypass does not use it. Skip that distance only for
protected records; generic world records retain the original calculation.
The optional replication index also no longer stores protected records in its
spatial cells or stagger buckets: they are already included globally every tick.
Final selected offsets remain unique and sorted in original packet order.
Owner-only inventory filtering, Net_Relevant and transport eligibility remain.
Index stays opt-in; no claim of a measured live index speedup.

The native fixture pins actual d540 Sender cadence, compares optimized/indexed
eligibility to that previous predicate's full scan across float boundaries,
overloads, tick wrap, handle reuse and moving objects, and instruments distance
calls. These are exact redundant-work removals, independent of restoring vision.
