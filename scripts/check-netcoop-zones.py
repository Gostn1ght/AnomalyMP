"""Anomalies switched off on the server reach players who come later (owner
2026-10-24, spec 5.2): the server sends each loaded client the anomalies that
are off, the client switches them off (also ones it spawns later), campfires
stay with their own sync, and the state is cleared with the session."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "src/xrGame"


def read(name):
    return (GAME / name).read_text(encoding="utf-8", errors="replace")


zones = read("netcoop_zones.inc")
assert "zone->IsEnabled()" in zones and "smart_cast<CZoneCampfire*>(zone)" in zones
assert "gamma_snapshot_ready" in zones and "s_zones_synced[CL->ID.value()]" in zones
assert 'P.w_stringZ("netcoop_zones")' in zones and "server->SendTo(id, P" in zones
assert "zone->netcoop_switch_off()" in zones and "s_zones_pending.insert" in zones
assert "id >= 0xffff" in zones  # no wrap to a valid id
assert '#include "netcoop_zones.inc"' in read("netcoop_accounts.inc")
frame = read("netcoop_auth.inc")
assert frame.index("server_campfires_update(server);") < frame.index("server_zones_update(server);")
assert 'if (!xr_strcmp(channel, "netcoop_zones")) return client_on_zones(data);' in read("netcoop_script_messages.inc")
stop = read("Level_network.cpp")
assert stop.index("Server->Disconnect();") < stop.index("netcoop::zones_reset();")
spawn = read("CustomZone.cpp")
body = spawn[spawn.index("BOOL CCustomZone::net_Spawn"):spawn.index("void CCustomZone::net_Destroy")]
assert body.index("netcoop::client_zone_spawned(this);") < body.rindex("return (TRUE);")
assert "void netcoop_switch_off() { if (IsEnabled()) OnStateSwitch(eZoneStateDisabled); }" in read("CustomZone.h")
print("PASS anomalies off on the server: sent to each loaded client, applied on spawn, campfires apart, reset with the session")
