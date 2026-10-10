"""Seal the two portable folders only with a matching successful GHA artifact.

No game/server launch. Original bytes are retained outside the distributable
folders. NTFS hardlinks deduplicate identical archives on J:; copying either
folder elsewhere produces a complete ordinary portable copy.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime
import lzpack

def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def inside(path,root):
    path=Path(path).resolve()
    if not path.is_relative_to(root): raise ValueError('Output escapes the selected release folder')
    return path

def sealed(path):
    with Path(path).open('rb') as stream:return stream.read(8)==lzpack.MAGIC

def archive_files(folder):
    return sorted(p for p in (folder/'db').rglob('*') if p.is_file() and p.suffix.lower().startswith('.db') and p.name.lower()!='thumbs.db')

def pack_rows(rows,destination,key,entry,retained):
    """Split small new scripts/overlay into bounded standard DB volumes."""
    groups=[];group=[];size=0
    for name,path in rows:
        length=path.stat().st_size
        if length>lzpack.MAX_VOLUME:raise ValueError('Single overlay asset exceeds the volume limit')
        if group and size+length>lzpack.MAX_VOLUME:
            groups.append(group);group=[];size=0
        group.append((name,path));size+=length
    if group:groups.append(group)
    outputs=[]
    for index,group in enumerate(groups):
        target=destination.with_name(destination.name+f'_{index:03d}.db0')
        raw=retained/(destination.name+f'_{index:03d}.raw-building')
        protected=target.with_name(target.name+'.sealed-building')
        raw.unlink(missing_ok=True);protected.unlink(missing_ok=True)
        try:
            lzpack.make_db(group,raw,entry);lzpack.protect(raw,protected,key)
            if target.exists():
                backup=retained/(target.name+'.previous')
                if not backup.exists():os.link(target,backup)
            os.replace(protected,target)
        finally:raw.unlink(missing_ok=True)
        outputs.append(target)
    for old in destination.parent.glob(destination.name+'_*.db0'):
        if old not in outputs:
            os.replace(old,retained/(old.name+'.obsolete'))
    return outputs

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True);parser.add_argument('--artifact')
    parser.add_argument('--expected-sha');parser.add_argument('--key');parser.add_argument('--plan',action='store_true')
    args=parser.parse_args();root=Path(args.out).resolve()
    game=inside(root/'Lost Zone',root);server=inside(root/'Lost Zone Server',root)
    for folder in (game,server):
        if not folder.is_dir():raise ValueError('Portable folders must be assembled first')
        for path in folder.rglob('*'):
            if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):raise ValueError('Link/reparse point in portable release')
    archives={game:archive_files(game),server:archive_files(server)}
    unique_size=sum(p.stat().st_size for p in archives[game])
    common_size=sum(p.stat().st_size for p in archives[server] if (game/p.relative_to(server)).is_file())
    if args.plan:
        print(json.dumps({'player_archives':len(archives[game]),'server_archives':len(archives[server]),
            'player_archive_bytes':unique_size,'potential_duplicate_bytes':common_size,'free_bytes':shutil.disk_usage(root).free}))
        return
    if not (args.artifact and args.expected_sha and args.key):raise ValueError('Matching GHA artifact, source SHA and archive key are required')
    artifact=Path(args.artifact).resolve();key=lzpack.master(args.key)
    actual=(artifact/'built-from.txt').read_text(encoding='utf-8-sig').strip()
    metadata=json.loads((artifact/'lzpack-format.json').read_text(encoding='utf-8-sig'))
    if actual!=args.expected_sha or metadata.get('format')!='LZPACK1' or metadata.get('key_fingerprint')!=hashlib.sha256(key).hexdigest()[:16]:
        raise ValueError('GHA artifact/key mismatch; existing folders were not changed')
    for folder,subfolder,executable in ((game,'bin','LostZoneClientDX11.exe'),(server,'dedicated','LostZoneServerDX11.exe')):
        installed=folder/subfolder/executable;built=artifact/subfolder/executable
        if not installed.is_file() or not built.is_file() or digest(installed)!=digest(built):
            raise ValueError('Install the matching GHA binaries before sealing archives')
    # All updates are immutable, versioned files; replacement is atomic. The
    # marker stops launchers during the final conversion of old packages.
    for folder in (game,server):(folder/'UPDATING.lock').write_text('Protected release is being assembled.\n',encoding='ascii')
    retained=inside(root/'_work'/('retained_plain_'+datetime.now().strftime('%Y%m%d_%H%M%S')),root)
    retained.mkdir(parents=True,exist_ok=False)
    known={};common={};report=[]
    # Verify duplicates before replacing a server copy with a hardlink.
    for path in archives[server]:
        shared=game/path.relative_to(server)
        if not shared.is_file() or shared.stat().st_size!=path.stat().st_size:continue
        if os.path.samefile(shared,path):common[path]=shared;continue
        one,two=digest(shared),digest(path)
        if one!=two:continue
        common[path]=shared;known[shared]=one;known[path]=two
        temp=inside(path.with_name(path.name+'.deduplicate-building'),root);temp.unlink(missing_ok=True)
        os.link(shared,temp);os.replace(temp,path)
    remaining=sum(p.stat().st_size for paths in archives.values() for p in paths if not sealed(p) and p not in common)
    if shutil.disk_usage(root).free<remaining+2*1024**3:
        raise ValueError('Insufficient space to retain all original bytes; originals were not deleted')
    for folder in (game,server):
        for number,path in enumerate(archives[folder],1):
            print(f'Protecting {folder.name}: {number}/{len(archives[folder])} {path.relative_to(folder)}',flush=True)
            if sealed(path):
                reader=lzpack.Reader(path,key);reader.read(0,1);reader.read(reader.size-1,1)
                continue
            raw_hash=known.get(path) or digest(path)
            backup=inside(retained/folder.name/path.relative_to(folder),root);backup.parent.mkdir(parents=True,exist_ok=True)
            os.link(path,backup) # preserves exact old bytes without a second physical copy
            shared=common.get(path)
            target=inside(path.with_name(path.name+'.sealed-building'),root);target.unlink(missing_ok=True)
            if shared and sealed(shared):os.link(shared,target)
            else:lzpack.protect(path,target,key)
            os.replace(target,path)
            report.append({'folder':folder.name,'archive':str(path.relative_to(folder)),'original_sha256':raw_hash,'protected_sha256':digest(path)})
            (retained/'conversion.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        role='client' if folder==game else 'server'
        scripts=inside(folder/role/'scripts',root)
        rows=lzpack.files_under(scripts)
        if rows:
            pack_rows(rows,folder/'db/lostzone/lz_scripts',key,f'$fs_root$\\{role}\\scripts\\',retained)
            backup=inside(retained/folder.name/role/'scripts',root);backup.parent.mkdir(parents=True,exist_ok=True)
            os.replace(scripts,backup);scripts.mkdir() # VFS now reads the sealed script pack
        assets=inside(folder/'gamedata',root);rows=lzpack.files_under(assets)
        if rows:
            # Nested .db files must be real archives, not DB entries inside another DB.
            nested=[(name,p)for name,p in rows if p.suffix.lower().startswith('.db')]
            for name,path in nested:
                output=folder/'db/lostzone'/('lz_embedded_'+digest(path)[:16]+'.db0')
                if not output.exists():lzpack.protect(path,output,key)
            rows=[('gamedata\\'+name,p)for name,p in rows if (name,p)not in nested]
            if rows:pack_rows(rows,folder/'db/lostzone/lz_overlay',key,'$fs_root$\\',retained)
            backup=inside(retained/folder.name/'gamedata',root);backup.parent.mkdir(parents=True,exist_ok=True)
            os.replace(assets,backup);assets.mkdir()
        (folder/'db/lostzone_updates').mkdir(exist_ok=True)
        shutil.copy2(artifact/'lzpack-format.json',folder/'lzpack-format.json')
        shutil.copy2(artifact/'built-from.txt',folder/'built-from.txt')
        for path in archive_files(folder):
            if not sealed(path):raise ValueError('Unprotected archive remains: '+str(path))
            reader=lzpack.Reader(path,key);reader.read(0,1);reader.read(reader.size-1,1)
        if any(scripts.rglob('*.script')):raise ValueError('Loose game scripts remain')
        print('Protected scripts/assets complete: '+folder.name,flush=True)
    # Only the owner gets the compressor and key, outside both distributables.
    tools=inside(root/'Compressor',root);(tools/'private').mkdir(parents=True,exist_ok=True)
    here=Path(__file__).resolve().parent
    for name in ('lzpack.py','README.md','Create patch.cmd'):shutil.copy2(here/name,tools/name)
    shutil.copy2(args.key,tools/'private/lzpack-v1.key')
    for folder in (game,server):
        (folder/'UPDATING.lock').unlink()
    print('PASS sealed portable packages; original bytes retained at '+str(retained),flush=True)
    print('Owner compressor: '+str(tools),flush=True)
if __name__=='__main__':main()
