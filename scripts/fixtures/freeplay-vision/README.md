# Historical freeplay vision reference

`o_trace.cpp` is the exact `Feel::Vision::o_trace` function from this repository:

- revision `843e5eef060a0e9bca79ddb537f0e10bfc40b7ae`;
- path `src/xrEngine/Feel_Vision.cpp`;
- before dedicated round-robin target skipping was added in `f39224a9f`;
- SHA256 (UTF-8 / LF / one final newline)
  `bf4bdfa2ff83bba7ee52ee07928f2bd434fd08aafa18b55b6cf7ed9a50118017`.

Copied from existing project history, under the project's existing license.
The source-equivalence check verifies restoration of original ordering, ray and
triangle caches and fuzzy accumulation. Full engine compilation runs in Actions.
This reference is not a performance benchmark or proof of smooth visual movement.
