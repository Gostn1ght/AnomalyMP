# Full-rate cadence before redundant distance removal

`cadence.cpp` is the actual Sender cadence block from repository revision
`d54030213cfbf950b5103ab0c275423242ed87a1`, `src/xrGame/xrServer.cpp`.
SHA256 after checkout newline normalization:
`cbef7e47e7982084081bb30a8e6eb39a0a6db763cf979febf3af642fdee67537`.

check-netcoop-replication-index.py compares the actual optimized predicate and
index selection against this pinned pre-optimization predicate/full scan.
An instrumented vector asserts that protected full-rate states need zero
distance calls; generic world states still evaluate distance normally.
Compilation/execution is GitHub Actions only. This is decision-equivalence
proof, not a live throughput or FPS benchmark.
