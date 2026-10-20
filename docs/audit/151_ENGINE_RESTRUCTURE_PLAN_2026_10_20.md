# Engine restructure and performance plan (owner 2026-10-20)

Owner: study the architecture problems and bugs of this engine and fix both;
cut the DX9 and DX10 renderers, keep only DX8 and DX11; cut what is not
needed; separate e.g. helicopters and cars; make the structure normal by
open documentation (find the best variant); write proper multithreading and
DX8 optimisation; remove the rectangle that opens before the game; let the
game load while alt-tabbed; start fast instead of minutes of black screen.

Work happens on branch `engine-restructure` (worktree
`NetAnomaly_Full\engine-restructure`), built by `workflow_dispatch` of the
DX11 workflow, merged into `menu-3d-hideout` stage by stage so the Codex
session never works against a moved tree for long.

## What is there (2026-10-20)

| Part | Files | Lines |
| --- | --- | --- |
| xrGame | 2741 | 470 k |
| xrRender (shared) | 242 | 56 k |
| R1 (static light, "DX8" config) | 36 | 6 k |
| R2 (DX9) | 91 | 13 k |
| R3 (DX10) | 98 | 17.5 k |
| R4 (DX11) | 114 | 22 k |
| xrRenderDX10 layer (R3+R4) | 55 | 14.5 k |
| xrEngine | 190 | 53 k |
| xrCore | 176 | 46 k |

One executable per renderer (DX8 = R1, DX9 = R2, DX10 = R3, DX11 = R4 build
configurations, statically linked). CI builds and ships only DX11.

Reference layout: OpenXRay (github.com/OpenXRay/xray-16) — renderers as
separate modules behind `xrAPI`, `xrCore`/`xrEngine`/`xrGame` split, the
task manager `xrCore/Threading/TaskManager` (work-stealing job system) used
for loading and per-frame parallel work.

## Measured start of the client (viewtest stand, warm shader cache)

| Time | Phase |
| --- | --- |
| 0–22 s | process start, file system index of 108 773 files in 135 archives (nothing in the log until "Starting engine") |
| 22–43 s | engine, configs, material pairs, textures descriptors |
| 43–86 s | **silent 40 s** after the HUD font: no log line (to find: shader creation / texture prefetch of the 3D menu room) |
| 86–92 s | 3D menu room, menu ready |

92 s here with a warm cache; the owner sees ~5 min (first start compiles
every shader; slower disk/CPU).

## Stages

1. **Start and focus (first, visible to players)**
   - Phase timings in the log (`[startup] N s: phase`), then remove what the
     timings show: the silent 40 s, the file-system scan on every start
     (cached index), log buffering.
   - Load while alt-tabbed: a lost/occluded device sleeps 33 ms per loading
     step and some steps wait for a frame; loading must not depend on focus.
   - The window/rectangle before the game (to confirm with the owner which one).
   - Shader compilation in parallel worker threads on the first start.
2. **Renderers**: remove R2 (DX9) and R3 (DX10): projects, configurations,
   menu entries, `renderer_r2*`/`renderer_r3` console values, dead shared
   code; keep R1 (DX8) and R4 (DX11); CI builds DX8 too.
3. **Structure**: split the netcoop monolith (netcoop.cpp + .inc) into
   modules (accounts/auth, characters, storage, trade, PDA, cluster/master,
   vehicles, helicopters); cars and helicopters as separate modules over a
   common vehicle base; remove dead parts (in-game editor hooks, duplicate
   `optick`/`optick-git`, old `engine.sln`, unused 3rd-party code) after a
   reference check.
4. **Multithreading**: one job system (OpenXRay-style task manager) instead
   of ad-hoc threads; parallel loading (textures, models, spawn), parallel
   per-frame work (particles, skeleton updates, AI scheduler slices),
   keeping the server's determinism.
5. **DX8 (R1) optimisation**: batching, state caching, visibility, LOD.
6. **Bug sweep**: MSVC `/analyze` in CI, crash classes from dumps (doc 150:
   single-player `Actor()` on the server), fix by class, not one by one.
