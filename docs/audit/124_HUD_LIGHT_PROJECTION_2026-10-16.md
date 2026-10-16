# HUD light projection and validation status

The R2/R3/R4 light helpers previously applied the HUD FOV direction projection to the six fixed world-space shadow cubemap faces. Under a rotated view, this non-rigid projection shears their basis. The new helpers project the emitter position while retaining POINT/OMNIPART world axes. Spotlights project both direction and right vectors. A light repeated within/across packages is transformed only once.

The saved state now restores position, direction and right for every transformed light, even if relevance lists or HUD flags change during rendering. The cached light transform is invalidated on entry and restoration, because both spaces can be rendered during one device frame.

`check-native-hud-light-projection.py` extracts the actual identical helpers from all three renderers. Its CI-only native fixture checks six cube faces, an anisotropic HUD projection under camera yaw, spot bases, repeated emitters, unchanged world lights, complete restoration and cache invalidation. The release build targets DX11; matching helper fixtures do not constitute complete DX9/DX10 builds.

This is a source-level projection defect associated with HUD lights. It does not establish that every reported shadow, water seam, scope or character mesh artifact has the same cause. Those visual acceptance checks remain open under the owner's instruction to test without the game.

Previous native run `38787310889` passed the isolated fixtures but failed the full engine build at `netcoop_items.inc`: `make_string` returns `std::string`, whose conversion to allocator-specific `xr_string` is explicit. The notification now retains the function's actual return type with `auto`. A new full build is required before distribution.

Earlier run `38783097051` fully passed for blast/ballistics, seated inventory and loot routing changes. The subsequent consumption/suspension/light batch has not yet been installed. Resource patch 000020 is built and authenticated, source `d265adea1cd39be7e329baac0c1199f0e4c8ffa5`, and remains staged until the native release passes.
