# GAMMA emission cleanup fixture

`surge-end.lua` is the unmodified `CSurgeManager:end_surge(manual)` from the
installed GAMMA `gamedata/scripts/surge_manager.script`, extracted between that
definition and `pos_in_cover`. Line endings are LF and CP1251 is decoded to UTF8.
Normalized source SHA256:
`aad00a89333b4d47271fd48f66a0f4ee4a1b955f76e411f1e3d220c5bcc61a34`.

The normal (`manual=false`, no time-forwarded saved FX) path intentionally leaves
weather recovery running. Test it through the actual multiplayer client adapter
and retain its sound/wave/light/camera cleanup while authority owns mortality.
The manual single-player control still explicitly stops the effect.
