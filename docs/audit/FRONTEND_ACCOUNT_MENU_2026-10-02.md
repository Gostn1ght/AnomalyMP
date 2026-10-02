# Account verification before entering the world

The normal client launcher must omit `-start client(...)`. That switch explicitly
loads the world and bypasses the front end, and is only for world smoke runs.

The first screen registers an account, or checks an existing account. The native
`netcoop_frontend_auth` client uses GameNetworkingSockets without creating a
Level, requesting world state, or sending `M_CREATE_PLAYER_STATE`. It sends the
normal authenticated request with character slot zero. The server returns the
approval status, role, names and inventory/model previews for five character
slots, then closes the temporary connection. Auth replies are flushed before
closing. Saved credentials use the existing Windows DPAPI storage.

The account window stays active while waiting; its own `Update` consumes the
result because the main menu is hidden. Duplicate requests are blocked and
connection failures restore the form. Remembered approved accounts go straight
from Play through verification to character selection. Only Enter the Zone
starts a game connection with the selected slot. New character creation keeps
the freeplay item point picker.

`python scripts/check-netcoop-menu.py` runs the actual Lua menu under Lua 5.1
using `lupa`, with stubbed UI and transport. It verifies first-screen behavior,
password validation, pending-account lock, asynchronous responses while the
owner menu is hidden, slot/preview mapping, and the distinction between account
verification and starting the world. An optional argument selects the installed
`netcoop_login_ui.script`. This test does not establish visual quality or a live
server handshake; those still require a normal client session.
