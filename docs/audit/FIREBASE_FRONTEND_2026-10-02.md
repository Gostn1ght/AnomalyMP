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
This background is used for account/profile screens. The character home uses an extracted section of the original Cordon trader bunker: 24,766 original triangles and 43 original texture materials. Static walls, floor, arches, pipes and furnishings come from l01_escape; the map, table, crate, radio and PDA are original game/modpack meshes. No generated box furniture remains. The extraction script and source hashes are recorded in scripts/extract-menu-room.py and meshes/netcoop/cordon_bunker.json. The background image remains limited to account/profile screens.
Prompt: grounded post-apocalyptic Eastern European stalker camp courtyard, worn shelters at the edges, crates, sparse trees and dim campfire, empty central ground for a separate actual 3D character; muted olive/charcoal/brown, diffuse warm overcast light; quiet dark side areas for UI; no people, interface, text, logos or watermarks.

References: [Firebase Authentication REST](https://firebase.google.com/docs/reference/rest/auth), [Firebase password authentication setup](https://firebase.google.com/docs/auth/web/password-auth), [Apps Script web apps](https://developers.google.com/apps-script/guides/web), [ContentService redirects](https://developers.google.com/apps-script/guides/content), [Firebase administrative user update](https://docs.cloud.google.com/identity-platform/docs/reference/rest/v1/projects.accounts/update).

## Menu startup and unavailable servers

- The menu XML root/path lifetime was corrected in 7b6799b51; local-menu-root.log records zero errors (5m27s). Installed SHA256 was 656481E7EEB6E7BBA3F477F63310E61FD0E2956A30E44240E42918DB70F4A053. The s130 menu run contains no shniaga_wnd fatal or script error.
- The prior Connect2Server timeout generated a rejection packet lacking ClientID, which OnConnectResult reads. A local timeout now directly rejects/disconnects and returns to the normal menu; it never calls the packet reader. GameNetworkingSockets limits the initial transport handshake to eight seconds; the overall connection-result wait is twenty seconds for netcoop. Post-load disconnects are checked during startup as well.
- Netcoop uses a translucent standard CUIMessageBoxEx with one OK button for an unavailable server. It appears over the menu; standard MESSAGE_BOX_OK_CLICKED closes the box. It neither exits the application nor erases the saved account/character. Other rejection dialogs are preserved.
- Room binary and locale XML validation passed. All menu/code Lua tests and Direct3D shader compilation passed again after the original room replacement. Geometry rays from the menu camera to eight actor/body sample points are unobstructed by the original bunker. This is a geometry check, not a visual screenshot check.
