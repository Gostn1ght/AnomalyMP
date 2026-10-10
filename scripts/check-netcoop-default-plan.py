"""The server's default plan (hoster/netcoop_cluster.ltx.six): owner 2026-10-10
"Agroprom instead of the Warehouses". Every map the panel should run has a
start section ([launch]: the watchdog skips a map without one) and the same
port and start as the full catalog; the underground starts on demand."""
from pathlib import Path
import configparser

root = Path(__file__).resolve().parents[1]
def read(path):
    ini = configparser.ConfigParser(inline_comment_prefixes=(';',), interpolation=None)
    ini.read(path, encoding='cp1251')
    return ini

six = read(root / 'scripts/netcoop-cluster/netcoop_cluster.ltx.six')
full = read(root / 'scripts/netcoop-cluster/netcoop_cluster.ltx.full')
maps = set(six['locations'])
assert maps == {'k00_marsh', 'l01_escape', 'l02_garbage', 'y04_pole', 'l05_bar', 'l03_agroprom', 'l03u_agr_underground'}, maps
assert 'l07_military' not in maps
assert maps == set(six['launch']) == set(six['on_demand'])
for level in maps:
    assert six['locations'][level] == full['locations'][level], level
    assert six['launch'][level] == full['launch'][level], level
ports = [six['locations'][level].split(':')[1] for level in maps]
assert len(set(ports)) == len(ports)
assert [level for level in maps if six['on_demand'][level] == '1'] == ['l03u_agr_underground']
# the panel launcher replaces an older default plan that had no [launch]
cmd = (root / 'scripts/dist/Start Server Panel.cmd').read_text(encoding='utf-8')
assert 'findstr /l /c:"[launch]"' in cmd
print('PASS default server plan: Marsh, Cordon, Garbage, Meadow, Bar, Agroprom (+ underground on demand); every map has a start section')
