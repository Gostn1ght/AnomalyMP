# Master entry and the master window (owner 2026-10-17)

Request: players enter only the master's IP and land on the map where they
saved, at the same place; the master is a console like the map servers, and
the maps must be managed from it.

## Entry (891d198d2)

- `backend/lostzone/gateway.py`: public TCP `GET /v1/entry` on
  `[cluster] entry_port` (default 1267; 0 = off), bound on 0.0.0.0, rate
  limited, answers `{host, port, location}` of the first location of the plan
  that holds a live lease, 503 when none runs, 405 for anything but GET. A
  loopback host in the plan is returned empty: the client keeps the address
  it used.
- `serve --gateway-port N --cluster <plan>` starts it next to the private
  API (127.0.0.1:38477, unchanged).
- Client: `netcoop_master_entry("ip:port")` (WinHTTP, 1.5 s) in
  `netcoop_login_ui.script` `route_addr`: the login and the connect go to the
  map the entry names; no answer = the address as typed (old servers).
- The map the player lands on asks the master (M2b admission). A character
  living on another map answers `ELSEWHERE home=<map>`; the map redirects the
  client there. If that map is off and on demand it is woken and the player
  is told to log in again in 1-2 minutes. The position is the master's
  checkpoint of the character (saved on exit), so the player appears where
  they left.
- A redirect naming 127.0.0.1 is rewritten to the host the client connected
  to (`client_cluster_transfer`).

## Master window (70b99ffce, 820a0f1ea)

- `Start Master.cmd` and the panel are one window "Lost Zone — мастер":
  tabs Локации / Игроки / Консоль мастера.
- The master runs hidden (`serve`), stdout/stderr in
  `appdata\server\netcoop_cluster\master_<stamp>.log` (+ `.err.log`, last 10
  kept). The console tab tails the newest log and sends lines to
  `POST /v1/console` (admin bearer read from `hoster\master\runtime\config.json`
  inside `Master-Console`, never shown). `quit`/`exit` are refused there:
  the master stops from the button.
- Console command `players`: ACTIVE/FROZEN sessions with their location.
- Maps write `players_<port>.txt` every 2 s (`login|name|slot|faction|role|ping`)
  and take `command_<port>.txt` every 1 s (at most 32 lines; allowed:
  `sv_ban`, `sv_unban`, `sv_account_role`, `sv_leader`, `sv_cmd`; others are
  logged as refused). The Игроки tab shows rosters fresher than 15 s and
  writes the admin/leader/ban commands; unban by login goes to any running map.

## Credentials for maps added later (1c88ec67a)

The panel merges all 33 maps into the plan. A master initialised with the
six-map plan threw on the seventh (`writer-config`: no credential).
`writer-config --add-location` creates only the missing `location:<map>`
credential (atomic replace of the private config); `Initialize-Master` passes
it for every map of the plan.

## Verified

- Backend: 347 unit tests (gateway, console endpoint, players, credential add).
- m2btest stand, master 820a0f1ea: started hidden (no window), log written,
  `status` and `players` through `/v1/console`, `quit` refused, `/v1/entry`
  503 with no maps.
- Panel snapshots: Игроки with three rosters (header count from rosters),
  Локации, console text (RichTextBox is not drawn by DrawToBitmap, so its
  text is saved beside the snapshot).

## Router

Open TCP `entry_port` (1267) and the maps' UDP ports. Players type
`IP:1267` only.
