"""Apply only the two qualified hidden-stat texture calls; retain original bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scripts',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup-dir',type=Path)
    args=parser.parse_args()
    folder=args.scripts.resolve(strict=True)
    target=folder/'ui_inventory.script';helper_target=folder/'netcoop_inventory_compat.script'
    if target.is_symlink() or target.resolve(strict=True).parent!=folder:
        raise ValueError('Refusing indirect inventory script')
    manifest=json.loads((Path(__file__).parent/'fixtures/inventory-compat/sha256.json').read_text(encoding='utf-8'))
    helper=(Path(__file__).parent/'netcoop-overlay/client/netcoop_inventory_compat.script').read_bytes().replace(b'\r\n',b'\n')
    if digest(helper)!=manifest['helper_sha256']:
        raise ValueError('Unqualified compatibility helper')
    original=target.read_bytes();current=digest(original)
    if current==manifest['after_sha256']:
        updated=original
    elif current==manifest['before_sha256']:
        updated=original
        for polarity in ['P','N']:
            field=polarity.lower()
            old=f'self.stat[name].ico_{field}:InitTexture("ui_inGame2_inv_state_{polarity}_" .. name)'.encode()
            new=f'netcoop_inventory_compat.init_bonus_texture(self.stat[name].ico_{field}, "{polarity}", name)'.encode()
            if updated.count(old)!=1:raise ValueError('Unexpected inventory call sites')
            updated=updated.replace(old,new,1)
        if digest(updated)!=manifest['after_sha256']:raise ValueError('Patched inventory hash mismatch')
    else:
        raise ValueError('Custom/new inventory script preserved; refusing unqualified version')
    exists=helper_target.exists()
    if exists and (helper_target.is_symlink() or helper_target.read_bytes()!=helper):
        raise ValueError('Existing custom helper preserved')
    changed=updated!=original or not exists
    report={'scripts':str(folder),'changed':changed,'before_sha256':current,'after_sha256':digest(updated),'helper_sha256':digest(helper),'apply':args.apply}
    if args.apply and changed:
        if not args.backup_dir:parser.error('--apply requires --backup-dir')
        backup=args.backup_dir.resolve()
        if backup.is_relative_to(folder):raise ValueError('Backup must be outside active script tree')
        backup.mkdir(parents=True,exist_ok=False)
        (backup/'ui_inventory.script').write_bytes(original)
        (backup/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        # Supply the namespace BEFORE changing its caller; never overwrite a
        # customized helper or write through a shared script hardlink.
        if not exists:
            with helper_target.open('xb') as stream:stream.write(helper)
        if updated!=original:
            if target.read_bytes()!=original:raise ValueError('Inventory changed during installation; backup retained')
            temp_name=None
            try:
                with tempfile.NamedTemporaryFile(dir=folder,delete=False) as stream:
                    temp_name=stream.name;stream.write(updated);stream.flush();os.fsync(stream.fileno())
                os.replace(temp_name,target);temp_name=None
            finally:
                if temp_name:Path(temp_name).unlink()
        if target.read_bytes()!=updated or helper_target.read_bytes()!=helper:raise ValueError('Installed bytes verification failed')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
