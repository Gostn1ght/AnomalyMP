# Release the world lock during checkpoint chunk decoding

PlayerSaves.finish already parsed/hashed the NCH file outside the shared world lock, but decoded and concatenated every base64 chunk while holding that lock. With large snapshots, unrelated location/player operations therefore had to wait for CPU-only decoding.

Copy the bounded, immutable upload metadata/part rows while authorized under the lock, then validate ordered offsets, canonical per-chunk encoding, sizes, total byte count, NCH format and full SHA outside it. Re-enter the ordinary fenced transaction and repeat current upload/session/location authority and entity/checkpoint CAS before COMMIT. No API, schema or native save format change. An incomplete/corrupt upload cannot replace the previous committed record.

Regression first failed on the old code: a real finishing thread paused inside base64 decoding still held the world lock. After the fix, a second operation changes the character while decoding is paused; finish rejects that stale CAS and retains the previous exact save. Additional stored-staging corruption cases cover shifted offsets, bad base64, short/oversized chunks and missing final parts, followed by successful completion after restoring the exact staging bytes.

The15 checkpoint tests and complete319-test backend suite pass locally (77.1 seconds for the full suite). CI and packaged EXE verification are pending for this batch. No installed world/config/account data or game process was used. This does not activate native primary persistence or close M2b/M3. New backend-only pushes must not cancel the running native engine CI99f218e6f.
