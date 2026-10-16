# Owner FBX conversion staging

Prepared independently while the corrected Mi-2 DX11 build runs. No vehicle,
NPC or mutant from this staging work is added to the Mi-2 launcher release.

## Portable tools

Official [Blender 4.5 distribution](https://download.blender.org/release/Blender4.5/),
Windows x64 4.5.14 LTS; ZIP checksum verified against the official
`blender-4.5.14.sha256` list:
`b9533d2397ac1984db4466fb23a7a4649391cca93f6e84209f9bcc60d071c8b9`.
Portable directory: `J:\LostZone_Work\_work\portable_blender_4.5.14`.
No installer, registry changes or existing Blender preferences are used.

[blender-xray v2.46.1](https://github.com/PavelBlend/blender-xray/releases/tag/v2.46.1)
is isolated in that directory; its release ZIP matches the GitHub asset digest
`c58250dd087118623f28b407c1d12448751990263e21deb9c66cd7669051788c`.
The owner asked to remove the portable tools after conversion work is finished.
They are retained while that work is still open.

## Source inspection

Background imports (no game client) wrote reviewable source scenes and JSON
to `J:\LostZone_Work\_work\owner_fbx_20261016`.

- Owner UAZ FBX: eight meshes, one armature. Its 23 non-end bones exactly
  match the existing GAMMA UAZ skeleton; bind positions match within
  `5.96e-7` metres. The DCP UAZ candidate has a different 42-bone skeleton,
  so blindly copying its complete physics profile would be incorrect.
- Owner GAZ-24 FBX: 48 meshes, one armature, dimensions approximately
  2.00 x 5.07 x 1.66 metres in Blender. Export/physics acceptance pending.
- `Ecologs_GFY.rar`: eight FBX variants, 48 DDS textures and 14 PNGs;
  eight staged actor conversions now exist (details below); runtime acceptance remains open.
- `god_forest.zip`: 196 FBX files (mostly animations) and 13 PNGs;
  animation/skeleton mapping and mutant integration remain open.

## UAZ staged export

`stage_owner_uaz.py` uses the owner's FBX geometry and the **matching**
original GAMMA physics skeleton. The original model was read from the owner's
protected `30_meshes_meshes_dynamics.db0`, decompressed to its declared size
and CRC-checked. Its SHA256 is
`65ca767a455a9e588ee68e94956d0ad01b64cfd9b30f3ff1ee6791afde375579`.
No foreign executable or engine DLL is used.

Output: `owner_fbx_20261016\veh_uaz_owner_01.ogf`, SHA256
`54d251db675c9c1f8cd1ebb4609713c59cf44c2f1f5b3cc2dd13848f706d9891`.
The staged `.blend` is `uaz-conversion.blend`. It preserves 23 physics bones,
the matching bind positions and collision shapes/joints. The source UAZ is
a rigid skeleton without motion chunks; the export retains that contract. OGF chunk bounds and the exact texture reference
`veh\veh_uazik_new` were verified after export. Initial exporter use produced
an invalid generic texture-node name; the source material's base-colour node
now names the actual game texture, and the corrected export was rechecked.

This is a conversion candidate, **not** a completed DCP handling port.
The original skeleton's masses are still present. DCP mass, suspension and
handling adaptation, native loading/driving, wheel/door placement, replication
and safe replacement of old vehicle sections remain open. No existing vehicle
or saved-world entity has been removed.

## GAZ-24 staged export

`stage_owner_gaz24.py` exported the owner FBX on its matching 42-bone
DCP skeleton, retaining each source material's shader rather than assigning
one shader to all surfaces. Bind positions differ by at most `6.34e-7` m.
Output: `owner_fbx_20261016\veh_gaz24_owner_01.ogf`; 48 meshes and 15
explicit `veh\...` texture references. The source physics/profile data was
extracted with length/CRC checks into `dcp_gaz24_u_01`. This candidate remains
private staging, subject to doc136's release restrictions; no new car is
installed or publicly distributed. Native loading, handling and integration
are still open.

## Ecolog staged exports

All eight supplied variants have been exported to
`owner_fbx_20261016\ecologs\stalker_ecolog_owner_<variant>.ogf`, with their
48 DDS textures under `textures\act\lostzone_ecologs`. The native template
is GAMMA's `actors\stalker_ecologist\stalker_ecolog_military.ogf`.

The 47 named bones match, but the FBX bind pose does **not** match the native
pose: a direct armature replacement would deform the actor (maximum bone
position difference 1.77 m). `stage_owner_ecologs.py` first poses the source
rig to the native rest transforms and applies the source skin modifier,
then assigns the baked geometry to the native rig. Residual bind-position
error is below `2.4e-7` m. The original native physics rig is retained.

`review_ecolog_export.py` independently checked all eight OGF chunk bounds,
47-bone counts, plausible model dimensions, six texture paths and existing
DDS headers per variant. Native motion-reference and userdata chunks are
byte-identical to the template. Receipts: `ecologs\conversion-review.json`
and `ecologs\export-reviewed.json`; `blue-bind-review.png` was rendered
offline and visually inspected for the rest-pose silhouette.

These are private conversion candidates. No model replacement, NPC spawn,
animated gameplay or multiplayer acceptance is claimed. The forest-god
source still requires unit scaling, rig reduction/retargeting and animation
mapping before native mutant integration.

## Forest-god input contract

`inspect_forest_fbx_contract.py` parsed the actual binary FBX nodes in all
196 files from the supplied `god_forest.zip`, after ZIP CRC-checked reads.
The 195 named animation files contain no Geometry, AnimationStack,
AnimationLayer, AnimationCurve or KeyTime payloads. The model FBX has nine
geometry/skin/cluster records, but Blender's import produced no vertex groups
on its nine meshes. Do not treat filenames such as `@idle.fbx` or `@bear_run.fbx`
as evidence that motion data exists.

The source has 127 bones. This engine's `SkeletonCustom.cpp` verifies at most
64 and uses a 64-bit visibility mask; direct export of the complete source
rig would fail. Geometry bounds are about 100 times too small after the
FBX import. A valid animated integration needs skin-binding repair,
compact-rig retargeting, unit correction and actual animation data. No
replacement monster or invented animation has been installed. Evidence:
`owner_fbx_20261016\forest-fbx-contract.json`.
