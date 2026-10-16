# Verified gameplay/render batch and patch000020

Installed without launching a game client, location server or installed world master.

## Build and artifacts

- Native source `01670ad8767c568d8481109f6e8d8f979075419a`, successful complete DX11 CI [38854891742](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38854891742). Linux checks, Windows native fixtures, full engine compilation and artifact upload passed. Earlier complete run38853207613 also passed and was not cancelled by the following push.
- Downloaded artifact `J:\LostZone_Work\_work\ci_01670ad87`:45 selected deployable/archive-receipt entries verified against ZIP sizes/CRC and source receipt. Independently fetched client and server EXEs share SHA256 `13e25074a496358556d3bc29158ab4e0a86d5d87c1ed37511ca69d329dd22ea7`.
- Resource patch000020 source remains `d265adea1cd39be7e329baac0c1199f0e4c8ffa5`, cumulative since026428e48. One client mutant-interaction script and one server mutant-loot script; no loose resource changes or deletions. Later commits contain native/fixture/documentation changes, with no further overlay delta.
- Both encrypted patch archives passed authenticated verification. Client SHA256 `30153033298f00d62147062329ff485391a7ba8839679827893f99a281c1789e`; server SHA256 `de8e54e8323aea0a10cc55cf843eec81c5778f94afa49ce4bf527a0c4820b905`.

## Installation and integrity

Friend overlay: `J:\LostZone_Work\Lost Zone Server`, with current native client/server binaries, both patch archives and updated Russian instructions. Dedicated binaries/server resources also installed to srvtest. Owner game received client resources only; every existing owner binary remained byte-identical and its previously quarantined client executable remains absent. No antivirus change or restoration was attempted.

Native installation backup: `J:\LostZone_Work\_work\before_native_01670ad87_20261016_083356` (five changed files). Resource installation passed a dry run before apply; backup: `J:\LostZone_Work\_work\before_resource_000020_20261016_083511`. Existing patch numbers were retained, not overwritten.

The complete6870-file public manifest matched before updating. Independent post-install verification matched **all6872 public files**, sizes and SHA256, plus66 installed native artifact copies across addon client/dedicated and srvtest dedicated. Engine/run, master, patch/source and date pins agree. Legacy `master_source_commit` metadata is aligned with the actual current master. No private runtime/key/appdata files are included in the distributable. Installers fingerprinted existing private config/world/account/character/key data before/after and found no changes.

Master remains verified60539905933fd4e0c8e6b3e41dd9bfa7cc91d01a; its EXE/fallback sources and private runtime were not replaced. Launcher publication remains false; existing published release2026.10.13.1 is unchanged. The already-authorized distribution server was restarted hidden and its local HTTP8787 returned200. Final game/location/master process count:0.

## Included code changes and limits

Docs120–125 record the implementations: finite blast impulse direction; bounded trajectory searches/invalid flight rejection; vehicle held-item/shot blocking while consumption stays available; precise transfer-refusal reasons; direct server-backed mutant interaction and preservation after nil/partial item creation; existing torso-only consumption motions for observers; optional DCP wheel spring/damping coefficients; HUD point-light cubemap projection and full light restoration; initialized skeleton motion history across first draw/reuse/gaps/frame wrap.

These automated and build checks do not establish live game acceptance. In particular, the reported host TPS-zero cause, all vehicle/trunk/transition crashes, SVD/other hand poses, every actor outfit/consumable prop, scope/character artifacts and water seams remain open for gameplay/visual confirmation. Source fixes are not marked as all reports resolved.

Full DCP car/physics and helicopter integration T2–T9 remains open; no supplied vehicle/aircraft model or foreign engine binary was installed. The isolated DCP/aircraft audits and physical adapter are in docs121/123. M2b live primary player persistence/admission/hydration, M3 actual GAMMA task/reward-once coordination, and H09/H11 native cross-location NPC/item transfer also remain open.

Additional source review confirmed the existing `server_task_check_target` / `cancel_task_on_other_map` path cancels certain non-story task targets on other maps. Removing that cancellation alone cannot supply the missing target entity or durable task ownership; it belongs to the M3 world-target/character-checkpoint integration. Existing trader preparation/profile refresh is implemented, but the owner's all-traders report is not closed from source inspection.
