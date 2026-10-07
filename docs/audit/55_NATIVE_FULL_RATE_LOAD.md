# Native full-rate load and delivery-gap attribution

2026-10-07. Source d54030213, matching client/server from successful GitHub
Actions DX11 37585365023, artifact 11466733728. Both exe SHA256:
36BA115085198F7B5BAF08E384AB306B2174FB19CA861EBFF6187498DCD57395.

## Isolated native results

Package staged in `_build/live/d54030213`, private appdata `accept16` /
`accept64` and corresponding bot directories. Main runtime executables, worlds,
accounts and characters untouched. GAMMA game data / archives / server Lua are
the existing runtime's data; four critical world/corpse/compat/emission overlays
match repository byte-for-byte. Missing third-party DLLs copied only when absent
from the GHA package. No local compilation.

Initial fixture setup incorrectly changed `$fs_root$` while keeping GAMMA data
paths: archive entry-point `gamedata` mounts below fs_root, so a model was missing.
The corrected setup preserves GAMMA fs_root and working directory, changing only
appdata; subsequent runs loaded successfully. Retained initial crash log is a
harness setup failure, not a production-source regression.

16 bots, two processes below normal, three minutes after load: final 16/16
playing, zero terminal failures, one admission timeout/retry. No fatal/script
errors or SendFailed. Last six frame windows: p50 6 ms, p95 16–18 ms,
p99 43–53 ms, maximum 61–188 ms. Total sent roughly 3.0–3.2 MB/s; server budget
blocked=0. Bot queue-drain worst gaps approximately 130–286 ms.

64 bots, four processes below normal, five-minute load phase: final 64/64
playing, zero terminal failures, six admission timeouts/retries. No fatal/script
errors or SendFailed. Last six ordinary-spawn windows: p50 11–14 ms,
p95 45–56 ms, p99 73–93 ms, maximum 116–289 ms. Sent roughly 18 MB/s.

For the second phase the private local server debug command moved all 64 player
actors close to the densest friendly group (eight NPCs within 30 m), without
moving NPCs or changing AI/population. Center -145.89,0.65,-288.84. Actual map
population before/after: 41 stalkers, 28 mutants. Online population increased
28→33 stalkers and 21→24 mutants as player presence activated them.
Last six close-NPC windows: p50 27–32 ms (earlier close window 37 ms),
p95 72–105 ms, p99 95–164 ms, maximum 127–302 ms. Sent roughly 13–17 MB/s;
server budget blocked=0. These are percentiles of individual reporting windows,
not percentiles recalculated from all raw frames. Earlier historical 110 ms
scene is not a controlled baseline comparison.

Bot queue-drain gaps in this phase reached approximately 0.9–1.5 s;
trailing shutdown windows reached 1.9–2.7 s. Harness stops server before bots,
so exclude trailing windows from steady-state attribution. Resending `you`
after relocation logs another playing entry; harness count 128 is not 128
distinct players. Raw logs and qualified summary.json retained in isolated
appdata. Loaded private memory around 1.87–1.88 GB does not meet 1.5 GB target.

## Diagnostic correction pending native acceptance

The old bot update gap uses the main-thread queue-drain timestamp. It cannot
distinguish delayed delivery from a paused load client. New BotGapProbe records
update callback delivery before forwarding to the unchanged base queue, and
records bot main-frame spacing separately. Original report prefix and packet
bytes preserved. Callback delivery is not a socket arrival timestamp: transport
worker scheduling and queue lock contention can still delay it.

One producer per connection; atomic maximum exchanged by reporting consumer.
Timestamp zero, unsigned clock rollover and previous observation across report
boundaries are supported. Derived destructor calls stop before probe members
die. CI copies the actual helper, actual message enums and extracts the actual
callback method; checks byte forwarding, update-only observation, consumer pause,
concurrent producer/report and reset/rollover on GCC+sanitizers and MSVC.
This does not certify full transport lifecycle or race freedom of unrelated
existing connection code. Native fixture compilation/execution is Actions only.

Load clients were also eligible to draw the main menu through the normal rendering gate.
Reuse existing -netcoop_bots detection to skip Begin/seqRender/Present only for
load clients, retaining OnFrame, networking/input and existing 10 ms cadence.
Ordinary graphical clients and dedicated simulation are unaffected. Renderer
startup is still present; no claim that menu drawing explains all measured gaps.

## Still open

New diagnostic/headless-driver source needs Actions fixture + full DX11 build,
then another isolated native 16/64 run. No main-runtime promotion until acceptance.
Bots do not render NPCs: maximum-visible-distance animation, held weapons,
movement and reactions require an actual graphical client. Full-rate send does
not itself guarantee timely delivery or AI execution. No AI cadence reduction,
population reduction or new live checkmarks in the 188-stage audit.

Existing profile_ai/metric_ai_update wraps CustomMonster Think; stalker overrides
its schedule and Think path. Treating it as inclusive stalker Lua/planner/vision
profile or deriving all-stalker AI cadence from it is incorrect.

Diagnostic source9e256b9b2: Foundation 37593806445 PASS on MSVC and GCC; actual
callback/probe fixture passed both OS. DX11 37593806421 still compiling at this
recording point. Isolated repeat directories prepared with unchanged GAMMA
fs_root/working directory. Host is an i5-2500K with four cores/four threads;
shared-host load contention remains a material limit.

Diagnostic DX11 37593806421 SUCCESS full checks/engine/package/upload. Matching
client/server artifact 11469784291 (189954533 bytes); isolated native repeats
follow before interpreting the two gap measurements.
