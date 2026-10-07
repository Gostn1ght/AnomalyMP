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

fa5edb5f23a4293e93029c95e8a78c29bc0bc526: Foundation37607469611 PASS both OS,
DX11 37607469678 SUCCESS full checks/engine/package/upload. Package artifact
11476356618 (189396278 bytes), downloaded _build/gha/vision-fa5edb5f2.
Matching exe SHA256
794316757B231F71467194E358084588DB93963E0B0225346C412686AE212113.
Isolated acceptance _build/live/fa5edb5f2; original GAMMA fs_root preserved,
separate appdata, both server/bot user.ltx seeded. Warm bot shader cache copied
from completed9e16; renderer verifies cache CRC. Main runtime still unchanged.

Combined native16: final16/16,16uniqueactors,0terminalfailures,3admissionretries.
Default graphical load-client mode (render gate disabled) with valid user.ltx;
no native fatal; existing caught PDA/handler messages remain as in doc55.
64 experiment uses -dedicated on the load clients, same actual transport/actor
handshake and payload. Dedicated startup omits menu work; this changes driver
conditions relative to9e and cannot establish an A/B game FPS improvement.
Still four processes below normal on shared four-core host, sampling enabled.
No additional high-CPU PDB symbolization during steady windows this time.

## Final native combined result

fa64 dedicated load clients: 64unique actor IDs, final64/64,0terminalfailed,
8admissionretries,0nativefatal. One population measurement before crowd move:
48stalkers30mutants,42/23online. No final population measurement was captured
before harness shutdown; do not claim before/after quantity equality from this
run. Local debug moved only players close to13friendlyNPCs; NPCs were not moved
or removed. This is denser and a different random fresh-world population than
9e39/27 with8nearNPCs; no controlled performance A/B attribution.

Last six near-NPC windows p50=57–76ms,p95=161–205ms,max355–646ms;
p99prints250 in every window because engine histogram's last bucket is250ms
AND ABOVE (netcoop.cpp4372). It is not an exact250ms percentile.
Total sent8.2–10.6MB/s; lower traffic on slower frames is not a bandwidth
optimization. Steady bot examples still have callback gaps0.3–1.05s and bot
main-frame peaks0.53–1.07s. Omitting menu/renderer startup reduced bot private
memory from~2GB to~0.55GB, but did not remove all gaps. Main server private
memory~1.97GB still does not meet1.5GB goal. Budget blocked remained0; this does
not prove zero transport queuing or smooth delivery.

Last post-crowd main-thread profile2728samples/30s: inclusive scheduler74.3%,
stalker45.1%,vision23.9%,Lua binder16.7%,planner10.1%. Sampling enabled;
percentages overlap and are not additive. PDB symbolization ran after shutdown
for this final test. Log/summary/profile retained under isolatedaccept64.
Caught PDA event messages20/handler1 still present (limited logging), as in the
older baseline. No visual max-range NPC movement/reaction acceptance. NO main
runtime promotion; primary executables/worlds/accounts unchanged.

Next lossless CPU work must target actual Lua pure reads/planner redundancy or
independent static geometric computation with precise state/lifetime barriers.
Do not parallelize observer-dependent Lua/material callbacks, share approximate
rays from different NPC origins, cap traces or lower binder/AI frequencies.
Bot receive/frame gaps need their own driver/transport profile; -dedicated has
ruled out menu rendering as the only explanation. No capacity or188-stage
completion claim follows from64successful handshakes.
