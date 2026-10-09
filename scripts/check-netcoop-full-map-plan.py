"""Generate a full installed-map catalog with actual dumped changer arrivals."""
from pathlib import Path
from tempfile import TemporaryDirectory
import configparser
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
def read(path):
    ini = configparser.ConfigParser(inline_comment_prefixes=(';',), interpolation=None)
    ini.read(path, encoding='cp1251')
    return ini

current = read(root / 'scripts/netcoop-cluster/netcoop_cluster.ltx.full')
assert len(current['locations']) == 33
assert set(current['locations']) == set(current['launch']) == set(current['on_demand'])
with TemporaryDirectory() as temp:
    runtime = Path(temp) / 'runtime'; output = Path(temp) / 'output'
    for level in current['locations']:
        (runtime / 'gamedata/levels' / level).mkdir(parents=True)
    configs = runtime / 'client/configs/plugins'; configs.mkdir(parents=True)
    (configs / 'new_game_start_locations.ltx').write_text(
        '[monolith_start_locations]\npower_station = l12_stancia\n'
        'old_station = l12_stancia,true\ntrain_hangar = l02_garbage,true\n', encoding='cp1251')
    command = [sys.executable, '-B', str(root / 'tools/make-cluster-plan.py'), '--runtime', str(runtime), '--output-root', str(output)]
    subprocess.run(command, check=True)
    generated = read(output / 'scripts/netcoop-cluster/netcoop_cluster.ltx.full')
    assert dict(generated['locations']) == dict(current['locations'])
    assert generated['launch']['l12_stancia'] == 'power_station'
    assert generated['launch']['l02_garbage'] == 'train_hangar'
    assert generated['on_demand']['k00_marsh'] == generated['on_demand']['l01_escape'] == '0'
    starts = read(output / 'scripts/netcoop-overlay/server/configs/netcoop/start_levels.ltx')
    for section in generated['launch'].values():
        if section.startswith('lz_'):
            assert section in starts and float(starts[section]['y']) > -1000
            assert int(starts[section]['gvid']) >= 0 and int(starts[section]['lvid']) >= 0
    subprocess.run(command + ['--closed', 'labx8,l13u_warlab'], check=True)
    reduced = read(output / 'scripts/netcoop-cluster/netcoop_cluster.ltx.full')
    assert len(reduced['locations']) == 31 and 'labx8' not in reduced['locations']
    for level, address in reduced['locations'].items():
        assert address == current['locations'][level]
print('PASS full map plan: 33 maps/labs, real arrival points, stable ports, optional exclusions, start section without comma')
