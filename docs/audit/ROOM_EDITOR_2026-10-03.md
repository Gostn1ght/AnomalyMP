# Personal room editor — 2026-10-03

Delivered separate folder `../LostZoneRoomEditor`, with `Start Editor.cmd`, `Stop Editor.cmd`, embedded Python 3.13.7/Pillow 12.2.0, local Three.js 0.180.0, original-asset reader and full source. No game server, npm install, or network required at runtime. Source: `tools/room-editor`.

## Implementation

- Searchable paged catalogue: 12,426 installed/base archive OGF models and 109,918 static level visual fragments (122,344 records, 103 categories).
- DB indexes decoded using the engine's LZH implementation; individual resources decoded using safe LZO1X. Runtime does not unpack whole archives. The investigation's temporary extracted stone archive was moved to `../build-logs/room-editor/archive-reader-fixture` rather than shipped inside the tool.
- OGF static, rigid, and skeleton 1W/2W/3W/4W geometry with progressive highest LOD ranges; legacy trailing CRLF padding accepted. Level geometry references decoded with original normals/UVs and original textures. Skinned decorations use bind pose, not animation.
- Selection, transforms, numeric fields, translation/angle/scale snap, floor placement, duplication/deletion, undo/redo, project download/open, local and browser save/restore.
- Configurable concrete shell, original-material search, four cameras, map/PDA/chest interaction points, primary shadow lamp.
- NCRM v2 export to runtime and source overlay; NCRC v1 camera/light sidecar (116 bytes). Atomic file writes and prior file backups. Validates dimensions/transforms/material availability and menu complexity limits before installing.
- Local HTTP only, cross-origin writes require a per-launch token, static path containment; does not access account credentials or cloud services.
- Model/thumbnail cache bounds, explicit unused GPU resource disposal, render only on changes, capped pixel ratio, cached shadows. Preview uses WebGL lighting; actual X-Ray lighting is verified in game.

## Verification

- DX11 MSBuild final build: zero exit, `../build-logs/room-editor-final-build.log`.
- Real Direct3D shader compiler: preview/room, bump variants, all skin modes and depth shaders pass.
- Initial export: exactly byte-identical to previous room, 5,921 triangles, 13 materials, 639,799 bytes. Existing room support/winding checks pass.
- Representative import sample: 159 of 160 initially parsed; remaining shipped weapon (`wpn_m1892.ogf`) had trailing CRLF. After reader fix, that weapon loads 3 parts/3,815 triangles. Actors and Agroprom level visual geometry also explicitly checked.
- Portable Python runtime: imports Pillow and archive DLL; HTTP catalogue, texture/model reads, save and real export pass. Camera binary length/magic/version verified. Invalid zero scale and tokenless mutation rejected without changing installed geometry.
- Headless test of this tool's own UI: loading, textured preview, add, numeric transform, duplication, undo/redo, camera capture, shell resize, browser autosave and restored state pass. `smoke.cjs`; screenshots in `../build-logs/room-editor`. No automated interaction with the user's game UI or authenticated browser tabs.
- Installed engine executable SHA256: `D65A77C49F67168E77D2DFFB9CB827F11D7B447E9E769A89220AD878C6FCC3A0`, matching client/server roles.
- Live test menu `room_editor_p1`: responsive, logs report `room editor cameras and lamp loaded`, `personal room loaded: 13 materials`; shader CRCs updated successfully, GPU samples 1.60 ms and 1.00 ms average. Test process then stopped. Layout editing and export require client restart; no attempt to automate game UI.

## Limits

Special effect/service visuals without independent triangle geometry show an explanation. Level categories are visual fragments, including terrain, not semantic prefabs. Catalogue includes every OGF path, while only renderable mesh visuals can be inserted. Animated models export as static furnishings. One lamp casts the game's menu shadow; additional lamp objects are decorative. Character position remains at the original game menu origin. Arbitrary role objects require assigning/updating their interaction point and camera. Model preview matches geometry/textures, not the complete X-Ray shader pipeline.
