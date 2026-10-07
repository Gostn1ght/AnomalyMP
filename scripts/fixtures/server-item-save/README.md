# GAMMA personal bolt save reference

Copied 2026-10-07 from the prepared GAMMA runtime's
`server/scripts/itms_manager.script`, `save_state` (line 512).
LF normalized; SHA256 pinned in the actual installer/Lua regression check.

Original module attribution:

    itms_manager by Alundaio
    Copyright (C) 2012 Alundaio
    Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported
    Modified by Tronex (2018–2020); Bolt count manager (2019/9/19).

Reference excerpt retains that license:
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
No modification of the reference function. The test executes it with Lua5.1
and substitutes engine inventory objects only. It verifies actor-present
behavior rather than claiming full character persistence from a Lua fixture.
