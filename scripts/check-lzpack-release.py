"""Exercise the actual release sealer on a tiny portable tree, never a game."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import os
import shutil
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools/lzpack'));import lzpack

with TemporaryDirectory() as tmp:
    temp=Path(tmp);out=temp/'release';artifact=temp/'artifact';key=bytes(range(32));keyfile=temp/'owner.key';keyfile.write_bytes(key)
    expected='0123456789abcdef0123456789abcdef01234567'
    artifact.mkdir()
    (artifact/'built-from.txt').write_text(expected,encoding='utf-8')
    metadata={'format':'LZPACK1','key_id':'v1','key_fingerprint':hashlib.sha256(key).hexdigest()[:16]}
    (artifact/'lzpack-format.json').write_text(json.dumps(metadata),encoding='utf-8')
    original={};folders=[]
    for name,role,binfolder,exe in (('Lost Zone','client','bin','LostZoneClientDX11.exe'),('Lost Zone Server','server','dedicated','LostZoneServerDX11.exe')):
        folder=out/name;folders.append(folder)
        (folder/'db/lostzone').mkdir(parents=True)
        (folder/role/'scripts').mkdir(parents=True)
        (folder/'gamedata/shaders').mkdir(parents=True)
        (folder/binfolder).mkdir()
        (artifact/binfolder).mkdir()
        payload=b'fixture executable bytes, never executed'
        (artifact/binfolder/exe).write_bytes(payload);(folder/binfolder/exe).write_bytes(payload)
        script=(folder/role/'scripts/fixture.script');script.write_bytes(('return "'+role+'"').encode())
        shader=folder/'gamedata/shaders/fixture.h';shader.write_bytes(b'fixture shader')
        # Shared archives start as separate physical files. The sealer must
        # retain exact originals while making each final folder portable.
        archive=folder/'db/lostzone/base.db0'
        source=temp/(role+'.bin');source.write_bytes(b'model bytes'*10000)
        lzpack.make_db([('meshes\\fixture.ogf',source)],archive,'$fs_root$\\gamedata\\')
        original[folder]=archive.read_bytes()
    command=[sys.executable,str(root/'tools/lzpack/finalize_release.py'),'--out',str(out),'--artifact',str(artifact),'--expected-sha',expected,'--key',str(keyfile)]
    # A mismatched binary/key must be rejected before touching the packages.
    keyfile.write_bytes(bytes(reversed(key)));bad=subprocess.run(command,capture_output=True)
    assert bad.returncode!=0 and all(not (folder/'UPDATING.lock').exists()for folder in folders)
    keyfile.write_bytes(key)
    subprocess.run(command,capture_output=True,check=True)
    assert os.path.samefile(folders[0]/'db/lostzone/base.db0',folders[1]/'db/lostzone/base.db0')
    for folder in folders:
        archive=folder/'db/lostzone/base.db0';reader=lzpack.Reader(archive,key)
        assert reader.read(0,reader.size)==original[folder]
        assert not (folder/'UPDATING.lock').exists()
        assert not list(folder.rglob('*.script')) and not list(folder.rglob('*.key'))
        assert (folder/'db/lostzone_updates').is_dir()
    retained=list((out/'_work').glob('retained_plain_*'));assert len(retained)==1
    for folder in folders:
        assert (retained[0]/folder.name/'db/lostzone/base.db0').read_bytes()==original[folder]
        role='client'if folder==folders[0]else 'server'
        assert (retained[0]/folder.name/role/'scripts/fixture.script').read_bytes()==('return "'+role+'"').encode()
    copied=temp/'portable-copy';shutil.copytree(folders[0],copied)
    assert not os.path.samefile(copied/'db/lostzone/base.db0',folders[0]/'db/lostzone/base.db0')
    reader=lzpack.Reader(copied/'db/lostzone/base.db0',key);assert reader.read(0,reader.size)==original[folders[0]]
    assert (out/'Compressor/private/lzpack-v1.key').read_bytes()==key
print('PASS actual protected release: mismatch rejected before mutation, exact original backups, deduplicated sealed archives, encrypted scripts/assets, independent portable copy, owner key outside distributables')
