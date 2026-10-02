# Firebase account frontend

Project: `lostzoneapi`. The client and dedicated server use Firebase Authentication REST over HTTPS through WinHTTP. The JavaScript SDK and Analytics are not required by this native game.

## Flow

1. First launch shows registration or email/password login, before a game server connection.
2. Account username is separate from the character nickname. Google sends the email verification link. The client checks `emailVerified` through `accounts:lookup` after token refresh.
3. A new verified account creates a character nickname, appearance description and story, then selects starter items using the existing freeplay point picker.
4. Up to five local character drafts are saved per Firebase UID with Windows DPAPI. Starter stacks preserve each item count; the native point-budget validator checks drafts before saving.
5. The main menu renders the actual character model with side arrows, five slot buttons, RP preview, inventory on the bound game key, game settings and a separate server address panel. Only Play starts a world connection, after refreshing the Firebase token.
6. The dedicated server verifies the ID token with Google and checks the UID, account name and verified email. An existing account cannot be claimed with a different UID. Device binding and administrator approval still apply.

Passwords are not written to disk. Only the refresh token and account metadata are remembered in a file protected for the current Windows user. Tokens are kept out of Lua and logs. Certificate validation is enabled, redirect forwarding is disabled, and Google requests have timeouts and response-size limits.

Refresh calls use Google's documented form encoding. Character save format NCH5 adds description and story and continues reading NCH3/NCH4. Existing legacy game accounts remain separate; this does not silently convert them into cloud identities.

## Scope and verification

- Native DX11 build completed with zero errors (`build-logs/local-firebase-final.log`).
- `scripts/check-netcoop-menu.py` executes the actual Lua using Lua 5.1 with UI/transport stubs: first screen, email gate, request locking, offline character creation, stack counts, separate nickname, inventory key, remembered login and token refresh before world entry passed.
- `scripts/check-netcoop-firebase.py --live` uses one synthetic invalid-credentials request. After enabling Email/Password, Google returned `INVALID_LOGIN_CREDENTIALS`: key, HTTPS endpoint and provider are reachable. This test neither registers a real account nor sends email.
- Overlay XML and locale files were parsed independently. The installed Lua is tested again after deployment.
- Visual placement, real email delivery, native WinHTTP login and the full two-client world authentication still require an in-game check with the user's account; no successful live login is claimed here.

Registration is hosted by Google and does not require the owner's PC or game server to run. Playing still requires the game server. Drafts are local to the Windows user; authoritative world characters remain on the game server. There is no Firestore cross-device character storage. Admin registration notices are sent when the account first reaches the game server, where moderation takes place. Firebase display names do not reserve globally unique usernames; collisions are rejected by the game account database.

## Menu artwork

Asset: `scripts/netcoop-overlay/client/textures/ui/netcoop_camp.dds`.
Generated with the built-in imagegen tool, then converted to DDS for the engine.
Prompt: grounded post-apocalyptic Eastern European stalker camp courtyard, worn shelters at the edges, crates, sparse trees and dim campfire, empty central ground for a separate actual 3D character; muted olive/charcoal/brown, diffuse warm overcast light; quiet dark side areas for UI; no people, interface, text, logos or watermarks.

References: [Firebase Authentication REST](https://firebase.google.com/docs/reference/rest/auth), [Firebase password authentication setup](https://firebase.google.com/docs/auth/web/password-auth).
