"""Flyable Mi-2 (doc 137): the shipped model, its car profile and the item
section agree with each other and with what Car.cpp reads.

- veh_mi2_pilot.ogf's userdata includes the shipped profile;
- every bone the seats and the profile name exists in the model;
- the profile has every key CCar::ParseDefinitions reads without a default;
- every heli_* key of the section is one netcoop_heli_load reads;
- client and server configs are byte-identical;
- the model carries the "idle" motion the rotors turn with.
"""
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "scripts/netcoop-overlay"
OGF = OVERLAY / "client/meshes/dynamics/vehicles/mi2/veh_mi2_pilot.ogf"


def chunks(data):
    pos, out = 0, {}
    while pos + 8 <= len(data):
        cid, size = struct.unpack_from("<II", data, pos)
        out[cid & 0x7fffffff] = data[pos + 8:pos + 8 + size]
        pos += 8 + size
    assert pos == len(data)
    return out


def ini(text):
    sections, current = {}, None
    for line in text.splitlines():
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"!?\[([^\]]+)\]", line)
        if m:
            current = sections.setdefault(m.group(1), {})
            continue
        key, _, value = line.partition("=")
        current[key.strip()] = value.strip()
    return sections


model = chunks(OGF.read_bytes())
userdata = model[17].rstrip(b"\0").decode("ascii")
assert userdata == '#include "models\\vehicles\\veh_mi2_pilot.ltx"', userdata
body = model[13]
count, = struct.unpack_from("<I", body, 0)
pos, bones = 4, set()
for _ in range(count):
    z = body.index(b"\0", pos); bones.add(body[pos:z].decode()); pos = z + 1
    z = body.index(b"\0", pos); pos = z + 1 + 60
assert b"idle" in model[15], "the rotor motion"

for name in ("configs/models/vehicles/veh_mi2_pilot.ltx", "configs/mod_system_zzzzzzzz_netcoop_helicopters.ltx"):
    client, server = (OVERLAY / "client" / name).read_bytes(), (OVERLAY / "server" / name).read_bytes()
    assert client == server, f"{name}: client and server differ"
    client.decode("ascii")

profile = ini((OVERLAY / "client/configs/models/vehicles/veh_mi2_pilot.ltx").read_text(encoding="ascii"))
items = ini((OVERLAY / "client/configs/mod_system_zzzzzzzz_netcoop_helicopters.ltx").read_text(encoding="ascii"))
heli = items["veh_mi2_heli"]

car = (ROOT / "src/xrGame/Car.cpp").read_text(encoding="utf-8", errors="replace")
parse = car[car.index("void CCar::ParseDefinitions()"):car.index("void CCar::CreateSkeleton(")]
parse = re.sub(r"#else.*?#endif", "", parse, flags=re.S)  # CAR_NEW is defined: optional wheels
init = car[car.index("void CCar::Init()"):car.index("void CCar::Revert()")]
required = set(re.findall(r'ini->r_\w+\("car_definition", "(\w+)"\)', parse + init))
required -= set(re.findall(r'line_exist\("car_definition", "(\w+)"\)', parse + init))
missing = required - set(profile["car_definition"])
assert not missing, f"profile lacks {sorted(missing)}"
assert {"R", "N1"} <= set(profile["transmission_gear_ratio"])
for section in ("explosion", "damage_bones", "immunities", "car_sound", "damage_particles"):
    assert section in profile, section
assert profile["car_definition"]["damage"] in profile
for key in ("driver_place",):
    assert profile["car_definition"][key] in bones, key
for key in ("particle_bones1", "particle_bones2"):
    assert profile["damage_particles"][key] in bones, key
for bone in profile["collision_damage"]:
    assert bone in bones, bone
for item in heli["netcoop_seats"].split(","):
    bone, *offset = item.strip().split(":")
    assert bone in bones and len(offset) == 3, item
    [float(v) for v in offset]

load = car[car.index("void CCar::netcoop_heli_load()"):car.index("void CCar::netcoop_heli_rotors()")]
read = set(re.findall(r'"(heli_\w+)"', load))
given = {key for key in heli if key.startswith("heli_")}
assert given <= read, f"unknown keys {sorted(given - read)}"
assert read <= given, f"keys left at the engine default {sorted(read - given)}"
assert heli["netcoop_heli"] == "true" and heli["visual"] == "dynamics\\vehicles\\mi2\\veh_mi2_pilot.ogf"
inc = (ROOT / "src/xrGame/netcoop_vehicles.inc").read_text(encoding="utf-8-sig")
for key in ("netcoop_center_x", "netcoop_half_width", "netcoop_rear_z"):
    assert f'"{key}"' in inc and key in heli, key
# Lift must hold the weight with room to climb at the default collective rate.
assert 1.1 < float(heli["heli_lift_ratio"]) < 3

print(f"Helicopter: {len(bones)} bones, {len(heli['netcoop_seats'].split(','))} seats, "
      f"{len(read)} flight keys, profile and section agree with Car.cpp, client = server PASS")
