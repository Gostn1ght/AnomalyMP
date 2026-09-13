"""Apply the audited overlay to a clean, pinned engine checkout on the CI runner."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply(source):
    source = source.resolve()
    lock = json.loads((ROOT / 'engine/source.json').read_text())
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head not in (lock['ref'], lock['original_ref']):
        raise ValueError('Engine checkout does not match the pinned snapshot')
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Engine checkout must be clean before applying the patch')
    patch = str(ROOT / 'engine/gamma.patch')
    subprocess.run(['git', '-C', str(source), 'apply', '--check', '--ignore-space-change', patch], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', '--ignore-space-change', patch], check=True)
    shutil.copytree(ROOT / 'engine/overlay', source, dirs_exist_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('source', type=Path)
    apply(parser.parse_args().source)
