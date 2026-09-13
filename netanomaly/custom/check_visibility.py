"""Check evidence of remote actor replication in -net_trace logs; never equate it to visual QA."""
import argparse
import json
import re
from pathlib import Path

TRACE = re.compile(r'\[NetTrace\] actor=(\d+) name=(.*?) local=(\d) server=(\d) visible=(\d) visual=(\d) pos=([^ ]+) sample=([^ ]+) samples=(\d+)')


def inspect(path):
    actors = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        match = TRACE.search(line)
        if not match:
            continue
        actor, name, local, server, visible, visual, pos, sample, count = match.groups()
        if local == '1':
            continue
        state = actors.setdefault(actor, {'name': name, 'samples': 0, 'visible_samples': 0, 'positions': set(), 'server': server == '1'})
        state['samples'] += 1
        state['visible_samples'] += int(visible == '1' and visual == '1')
        state['positions'].add(pos)
    return {key: {**value, 'positions': sorted(value['positions'])} for key, value in actors.items()}


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('logs', type=Path, nargs='+')
    args = p.parse_args()
    reports = {str(path): inspect(path) for path in args.logs}
    print(json.dumps({'logs': reports, 'visual_confirmation': 'must be checked in the game windows'}, indent=2, ensure_ascii=False))
    # Every supplied peer must receive and retain at least one visible remote actor.
    passed = len(reports) >= 2 and all(any(a['samples'] >= 3 and a['visible_samples'] >= 3 for a in peers.values()) for peers in reports.values())
    raise SystemExit(0 if passed else 1)
