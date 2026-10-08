# 76. G12: native first-checkpoint admission barrier

2026-10-08, Codex. Original G12 requirement accepted for a local persistent
world: player world admission waits for its first successful durable
checkpoint. Live audit now27 accepted/33 code/69 partial/59 open,161 unclosed.

Validated GHAbe30 package/provenance from doc75, private
`_build/live/bootstrap-admission-be30-2`. Fresh private server/bot appdata;
no owner worlds, accounts or characters copied, deleted or reseeded.
Normal initial population, AI, physics and fixed30s bootstrap/15s retry
policy remain unchanged. No engine/gameplay source edits for this acceptance.

A GUID command in this server's private Lua state temporarily replaces only
`zz_netcoop_world_rules.script_snapshot_matches` with a rejecting checker.
This controlled fault exercises the actual C++ incomplete-checkpoint branch.
It is not a filesystem corruption/power-loss test. The ORIGINAL checker is
retained and restored before the recovery phase; other callbacks are preserved.

The single-controller native sequence:

1. New world has no committed pointer. Actual packet client `nbot_202`
   requests admission; its exact native server connection IDs receive
   "The world is still being prepared; try again in a minute". Its four
   attempts never produce an Actor; final pre-commit report is0playing/1failed.
2. Native ALife saves occur, but the injected checker rejects them. The
   engine reports incomplete script snapshot, keeps the world uncommitted
   and publishes no pointer. Another packet client `nbot_203` receives the
   same authoritative refusal after a failed checkpoint;0playing/1failed.
3. Restore the ORIGINAL checker after seven observed verification failures.
   Actual native bootstrap save succeeds and publishes the first `LZW3`
   pointer naming `selftest_bootstrap_admission_a`.
4. Independently verify recorded byte sizes and FNV64 hashes for BOTH `.scop`
   ALife and `.scoc` GAMMA script snapshots. Seal copies, pointer and SHA256s.
5. A new packet client `nbot_204` enters as Actor42752, stays another20s,
   final1wanted/1playing/0joining/0connecting/0failed. Native server admission
   appears after the successful bootstrap commit, never before it.

Client startup meant the first observed network refusal occurred AFTER an
initial failed save; the first phase proves pre-COMMIT refusal, not a
separate request before the first save attempt. The second negative phase
also runs while no initial snapshot has been committed. No checkpoint
success is inferred merely from files existing or from a bot disconnect.
Account authentication/registration is separate from world admission; this
test qualifies the native player-entry gate.

Proof: `qualified-acceptance.json`, six sealed phase/pre-stop journals,
`first-committed.current`, `first-committed.scop`, `first-committed.scoc`.
Nonce `BOOTSTRAP_23aef258b8a443a4998d95283b675627` correlates fault/restoration.
The verifier checks connection-ID-specific refusals, no Actor in either
negative bot snapshot, native failure→restore→commit→admission ordering,
last successful bot report and both pointer digests. No unexpected native
fatal/exception, SCRIPT ERROR, failed handler, probe or loadout error.
Expected incomplete-checkpoint/refusal/terminal negative-bot reports are
deliberate controls, not a clean-run claim for those phases. Other GAMMA
asset/MCM warnings remain outside G12.

The preceding root `bootstrap-admission-be30` is UNQUALIFIED and retained:
the first waiter incorrectly awaited the server-only refusal text in the
bot log, then two controllers competed over cleanup and interrupted recovery.
The final repeat uses ONE controller/new private appdata, server connection-ID
correlation and the real `-netcoop_bots_first N`→`nbot_(N+1)` account mapping.
No failed old world is deleted or silently reused as a successful result.

All processes stopped; shared debug empty; all88 protected primary
EXE/FS-alias/account/character/world fingerprints unchanged. Accepted primary
sound/LTX changes remain exactly docs73/74; no primary engine promotion.
Disk failure/crash durability, network-share guarantees, distributed fencing,
all post-admission transactions, human Firebase entry and64/max-view smoothness
remain separate requirements. This closes G12 only, not those broader cases.
