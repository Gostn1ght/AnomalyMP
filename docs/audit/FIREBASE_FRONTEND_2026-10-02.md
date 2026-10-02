# Firebase account frontend

Project: `lostzoneapi`. The client and dedicated server use Firebase Authentication REST over HTTPS through WinHTTP. The JavaScript SDK and Analytics are not required by this native game.

## Flow

1. First launch shows registration or email/password login, before a game server connection.
2. Account username is separate from the character nickname. A Google Apps Script service sends a six-digit email code. Continue submits the code; the client checks `emailVerified` through Google's `accounts:lookup` after verification. There is no verification-link fallback.
3. A new verified account creates a character nickname, appearance description and story, then selects starter items using the existing freeplay point picker.
4. Up to five local character drafts are saved per Firebase UID and canonical server address with Windows DPAPI. Switching servers selects a different set of characters. Legacy unscoped drafts are migrated only into the original default server. Starter stacks preserve each item count; the native point-budget validator checks drafts before saving.
5. The main menu renders a real depth-tested room, the actual character and selected primary weapon. A wall map opens Play, a PDA opens settings, and an equipment crate opens inventory. Controls follow the projected object positions. Side arrows and five slot cards switch characters. The inventory uses both configured game bindings. RP preview includes neutral, hands in pockets, hands behind the back and three seated poses; table-dependent and lying poses are excluded. Only Play starts a world connection, after refreshing the Firebase token.
6. The dedicated server verifies the ID token with Google and checks the UID, account name and verified email. An existing account cannot be claimed with a different UID. Device binding and administrator approval still apply.

Passwords are not written to disk. Only the refresh token and account metadata are remembered in a file protected for the current Windows user. Tokens are kept out of Lua and logs. Certificate validation is enabled and requests have timeouts and response-size limits. Apps Script ContentService responses follow one 302/303 redirect to Google's exact `script.googleusercontent.com` host as GET without forwarding the POST body. Other redirect forwarding is disabled. The code endpoint accepts only Google's deployed `/exec` URL format.

The email service derives recipient/UID from a Firebase-validated ID token, stores only HMAC challenges, limits resends and wrong guesses, and binds the administrative `emailVerified` update to the address that received the code. Google owner OAuth credentials remain on Google. Setup instructions and manifest are in `services/email-code`. A deployed endpoint must be configured before new registration can succeed; an empty endpoint is rejected before Firebase creates an account.

Refresh calls use Google's documented form encoding. Character save format NCH5 adds description and story and continues reading NCH3/NCH4. Existing legacy game accounts remain separate; this does not silently convert them into cloud identities.

## Scope and verification

- The room/code native DX11 build completed with zero errors (`build-logs/local-room-code.log`). The final actor torso/resource-lifetime/UID-cache build also completed with zero errors (`build-logs/local-room-code-final.log`, 5m41s). Existing compiler warnings remain.
- `scripts/check-netcoop-menu.py` executes the actual Lua using Lua 5.1 with UI/transport stubs: first screen, six-digit code gate, request locking, offline character creation, stack counts and icon rows, separate nickname, both inventory bindings, deferred/reused settings with constructor-failure recovery, preview weapon selection, RP whitelist, UID/server isolation, remembered login and token refresh before world entry passed.
- `scripts/check-email-code.cjs` executes the actual Apps Script source with mocked Google services: token-derived recipient, HMAC storage, code expiry, resend and guessing limits, email-change and cross-UID rejection, permission/quota/mail failure handling passed. This sends no real email.
- `scripts/check-netcoop-preview-shaders.py` uses the Windows Direct3D compiler for the room shaders, preview pixel shader and six actor skin variants. Compilation passed.
- `scripts/check-netcoop-firebase.py --live` uses one synthetic invalid-credentials request. After enabling Email/Password, Google returned `INVALID_LOGIN_CREDENTIALS`: key, HTTPS endpoint and provider are reachable. This test neither registers a real account nor sends email.
- Overlay XML and locale files were parsed independently. The installed Lua is tested again after deployment.
- Visual placement, real email delivery, native WinHTTP login and the full two-client world authentication still require an in-game check with the user's account; no successful live login is claimed here.

Registration is hosted by Google and does not require the owner's PC or game server to run. Playing still requires the game server. Drafts are local to the Windows user; authoritative world characters remain on the game server. There is no Firestore cross-device character storage. Admin registration notices are sent when the account first reaches the game server, where moderation takes place. Firebase display names do not reserve globally unique usernames; collisions are rejected by the game account database.

Server addresses are the current namespace key. Use the same canonical hostname/address for one server; different aliases are not automatically resolved into one identity. The account UID is shared across servers, while their approval, device binding and character databases remain separate.

## Menu artwork

Asset: `scripts/netcoop-overlay/client/textures/ui/netcoop_camp.dds`.
Generated with the built-in imagegen tool, then converted to DDS for the engine.
This background is used for account/profile screens. The character home now uses a purpose-built concrete shell with original Agroprom underground wall, floor and ceiling materials. Original game meshes provide the map, metal table, chest, stool, radio, hanging lamp and PDA. The earlier Cordon bunker and wooden decor room were rejected by the user and are no longer rendered. Shell dimensions and material provenance are recorded in personal_room.json; no generated room illustration is used.
Prompt: grounded post-apocalyptic Eastern European stalker camp courtyard, worn shelters at the edges, crates, sparse trees and dim campfire, empty central ground for a separate actual 3D character; muted olive/charcoal/brown, diffuse warm overcast light; quiet dark side areas for UI; no people, interface, text, logos or watermarks.

References: [Firebase Authentication REST](https://firebase.google.com/docs/reference/rest/auth), [Firebase password authentication setup](https://firebase.google.com/docs/auth/web/password-auth), [Apps Script web apps](https://developers.google.com/apps-script/guides/web), [ContentService redirects](https://developers.google.com/apps-script/guides/content), [Firebase administrative user update](https://docs.cloud.google.com/identity-platform/docs/reference/rest/v1/projects.accounts/update).

## Menu startup and unavailable servers

- The menu XML root/path lifetime was corrected in 7b6799b51; local-menu-root.log records zero errors (5m27s). Installed SHA256 was 656481E7EEB6E7BBA3F477F63310E61FD0E2956A30E44240E42918DB70F4A053. The s130 menu run contains no shniaga_wnd fatal or script error.
- The prior Connect2Server timeout generated a rejection packet lacking ClientID, which OnConnectResult reads. A local timeout now directly rejects/disconnects and returns to the normal menu; it never calls the packet reader. GameNetworkingSockets limits the initial transport handshake to eight seconds; the overall connection-result wait is twenty seconds for netcoop. Post-load disconnects are checked during startup as well.
- Netcoop uses a translucent standard CUIMessageBoxEx with one OK button for an unavailable server. It appears over the menu; standard MESSAGE_BOX_OK_CLICKED closes the box. It neither exits the application nor erases the saved account/character. Other rejection dialogs are preserved.
- Room binary and locale XML validation passed. All menu/code Lua tests and Direct3D shader compilation passed again after the original room replacement. Geometry rays from the menu camera to eight actor/body sample points are unobstructed by the original bunker. This is a geometry check, not a visual screenshot check.

### Installed original-room build

Commit 3ca49a58494460322f1054ac11b04cb0770438d7 is installed for client and dedicated server; SHA256 for both executables is 5FD280AE359A169E0A0380E99CF7151D7D4379AE333C8615219FED58340AFCEF. Both local-cordon-menu and local-cordon-menu-final builds completed successfully. The installer verified byte-identical room assets and one translucent OK template in each stock message-box layout. The map was repositioned to an unobstructed point, and the clock synchronization worker now joins before transport teardown.

Live check: s131 p1 was launched with start client(localhost/name=tester/port=1267/portcl=1269), with no listener on UDP 1267. The log records transport ProblemDetectedLocally, connection unavailable; returning to menu, and level destruction. PID 18092 remained alive and responding after failure. The same run logs original Cordon bunker loaded: 43 materials and no FATAL/SCRIPT ERROR/shniaga_wnd assertion. This checks the real startup/failure path rather than a Lua mock. The user still needs to confirm the room composition and OK dismissal visually; no automated UI interaction was performed.

Email-code deployment is still pending: code_endpoint remains empty until the owner runs Apps Script setup, deploys the web app and supplies its /exec URL. No live email-code verification is claimed.


### Concrete room and PDA settings repair — 7284cba98

Installed code commit 7284cba982d0809c9ecaf082d9730cdb8b62f526 in both client and dedicated roles. Executable SHA256: 03AA7BB4104F568E5DFFA66B8E29313577D5FB38C8F0634BC857CAA394589BBE. Local DX11 build local-concrete-room completed with exit code zero. Overlay deployment and byte identity were verified; room SHA256: FA12E7C33B008E927B5C21403188CDBE49B58A2A6D2134CE8B518D789BAE9AA5.

The s132 crash during the PDA/settings transition is recorded as pure virtual function called in netcoop_login_wnd:Show (line 440), followed by the error recovery path. The Lua Show override called an inherited virtual binding without a default implementation. Removing that override preserves native Show and avoids the same failure in both the normal and recovery paths. An actual-Lua regression assertion now requires that Show remains inherited; camera gating, settings reuse/recovery, inventory and server-scoped draft tests still pass.

The room now contains five continuous concrete surfaces and seven original furniture/device meshes, 5,921 triangles and 13 materials. Original concrete textures are checked against l03u_agr_underground's material table. Original THM metadata supplies normal/gloss maps when available; plain materials retain their diffuse fallback. The pixel shaders decode X-Ray WZY normals/X gloss, reconstruct the tangent frame, use directional ambient plus a warm lamp and small material specular, and filter the shared 1024 shadow map with nine taps. Shadow updates remain capped at 20 Hz. This remains an isolated forward menu renderer, not the complete in-level deferred/postprocessing pipeline.

check-personal-menu-room.py verifies the binary's dimensions, finite values and unit normals, concrete planes, unobstructed map/PDA views and original table support geometry. PDA bottom-to-table gap is 0.005 mm. Lua tests pass both on the source and installed overlay. All six preview skin vertex variants and diffuse/bumped/depth pixel shaders pass the real Direct3D compiler.

Live s133 menu check: PID 16508 launched without a game server, personal room loaded: 13 materials, process responding, and GPU timing continued to flush while the menu was open. Early 10-second average GPU batches ranged from 0.95 to 4.56 ms, with maximum sample 9.06 ms; this measures the menu draw pass rather than total frame time. No new s133 dump or fatal/pure-virtual error was recorded in that observation. An existing BusyHandsDebug/InitMMShniaga diagnostic still appears during stock menu construction; it does not prevent this room from loading and is not claimed resolved. The user's visual check and actual PDA -> settings -> room interaction remain pending; no automated UI control or screenshot capture was performed.
