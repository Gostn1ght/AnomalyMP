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
        (folder/role/'scripts_disabled').mkdir()
        (folder/role/'scripts_disabled/old.script').write_bytes(b'disabled script')
        (folder/role/'bin').mkdir()
        (folder/role/'bin/obsolete.exe').write_bytes(b'old fake exe, never executed')
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
        # Anomaly's own layout: a top-level archive and a mod archive, mounted
        # before Lost Zone's; the release must keep that order in one folder.
        for rel in ('db/files.db0', 'db/mods/zz_mod.db0'):
            (folder/rel).parent.mkdir(parents=True, exist_ok=True)
            lzpack.make_db([('meshes\\'+Path(rel).stem+'.ogf',source)],folder/rel,'$fs_root$\\gamedata\\')
        (folder/('fsgame.template' if role=='client' else 'fsgame_server.template')).write_text(
            (root/'scripts/dist'/('fsgame_client.template' if role=='client' else 'fsgame_server.template')).read_text(encoding='utf-8'),encoding='utf-8')
    command=[sys.executable,str(root/'tools/lzpack/finalize_release.py'),'--out',str(out),'--artifact',str(artifact),'--expected-sha',expected,'--key',str(keyfile)]
    # A mismatched binary/key must be rejected before touching the packages.
    keyfile.write_bytes(bytes(reversed(key)));bad=subprocess.run(command,capture_output=True)
    assert bad.returncode!=0 and all(not (folder/'UPDATING.lock').exists()for folder in folders)
    keyfile.write_bytes(key)
    subprocess.run(command,capture_output=True,check=True)
    # one "resources" folder, order kept by name: 00 base < 60 mods < 90 Lost Zone
    assert os.path.samefile(folders[0]/'resources/90_lostzone_base.db0',folders[1]/'resources/90_lostzone_base.db0')
    for folder in folders:
        role='client'if folder==folders[0]else 'server'
        assert not (folder/'db').exists()
        names=sorted(p.name for p in (folder/'resources').iterdir() if p.suffix.startswith('.db'))
        assert names[:3]==['00_files.db0','60_mods_zz_mod.db0','90_lostzone_base.db0'],names
        assert all(n.startswith('90_lostzone_lz_') for n in names[3:]),names
        template=(folder/('fsgame.template' if role=='client' else 'fsgame_server.template')).read_text(encoding='utf-8')
        arch=[l for l in template.splitlines() if l.split('=')[0].strip().startswith('$arch_dir')]
        assert arch==['$arch_dir$ = false | false | {ROOT}resources\\'],arch
        assert '$game_arch_mp$ = false | false | {ROOT}resources\\mp\\' in template
        archive=folder/'resources/90_lostzone_base.db0';reader=lzpack.Reader(archive,key)
        assert reader.read(0,reader.size)==original[folder]
        assert not (folder/'UPDATING.lock').exists()
        assert not list(folder.rglob('*.script')) and not list(folder.rglob('*.key'))
        assert not (folder/role/'bin/obsolete.exe').exists()
        assert not (folder/'gamedata').exists() and not (folder/role/'bin').exists() and not (folder/'built-from.txt').exists() and not (folder/'lzpack-format.json').exists()
        for path in (folder/'resources').iterdir():
            if path.suffix.startswith('.db'):assert lzpack.Reader(path,key).size>0
    retained=list((out/'_work').glob('retained_plain_*'));assert len(retained)==1
    for folder in folders:
        assert (retained[0]/folder.name/'db/lostzone/base.db0').read_bytes()==original[folder]
        role='client'if folder==folders[0]else 'server'
        assert (retained[0]/folder.name/role/'scripts/fixture.script').read_bytes()==('return "'+role+'"').encode()
        assert (retained[0]/folder.name/role/'scripts_disabled/old.script').read_bytes()==b'disabled script'
        assert (retained[0]/folder.name/role/'bin/obsolete.exe').read_bytes()==b'old fake exe, never executed'
    copied=temp/'portable-copy';shutil.copytree(folders[0],copied)
    assert not os.path.samefile(copied/'resources/90_lostzone_base.db0',folders[0]/'resources/90_lostzone_base.db0')
    reader=lzpack.Reader(copied/'resources/90_lostzone_base.db0',key);assert reader.read(0,reader.size)==original[folders[0]]
    # a patch goes straight into resources and sorts after every base archive
    patch_src=temp/'patch';(patch_src/'gamedata/meshes').mkdir(parents=True);(patch_src/'gamedata/meshes/fixture.ogf').write_bytes(b'new')
    made=lzpack.patch(patch_src,temp/'patches',key,'000001')
    assert made.name=='99_lz_patch_000001.db0' and made.name>max(names)
    assert (out/'Compressor/private/lzpack-v1.key').read_bytes()==key
    assert (out/'Compressor/built-from.txt').read_text(encoding='utf-8')==expected and (out/'Compressor/lzpack-format.json').is_file()
    # The server add-on for a player's folder: only the server's own scripts
    # archive (renamed so it never shadows the game's), nothing that replaces
    # a game file; the same content sealed twice counts as the game's.
    import make_server_addon
    (folders[1]/'dedicated').mkdir(exist_ok=True)
    (folders[1]/'server/configs').mkdir(parents=True,exist_ok=True);(folders[1]/'server/configs/system.ltx').write_text('[x]',encoding='utf-8')
    (folders[1]/'hoster').mkdir(exist_ok=True);(folders[1]/'hoster/netcoop_cluster.ltx.six').write_text('[locations]',encoding='utf-8')
    (folders[1]/'hoster/netcoop_cluster.ltx.example').write_text('[x]',encoding='utf-8');(folders[1]/'hoster/changers_dump.txt').write_text('x',encoding='utf-8')
    addon=out/'Lost Zone Server Addon'
    copied,shared=make_server_addon.build(folders[0],folders[1],addon,key)
    assert len(copied)==1 and copied[0].startswith('95_server_lostzone_lz_scripts'),copied
    assert shared==len([p for p in (folders[1]/'resources').iterdir() if p.suffix.startswith('.db')])-1
    assert not any((folders[0]/p.relative_to(addon)).exists() for p in addon.rglob('*') if p.is_file())
    assert (addon/'server/scripts').is_dir() and not list((addon/'server/scripts').iterdir())
    assert lzpack.Reader(addon/'resources'/copied[0],key).size>0
    assert addon.name not in [p.name for p in folders[0].iterdir()]
    assert (addon/'hoster/netcoop_cluster.ltx.six').is_file() and not list((addon/'hoster').glob('*.example')) and not (addon/'hoster/changers_dump.txt').exists()
print('PASS actual protected release: mismatch rejected before mutation, exact original backups, deduplicated sealed archives, encrypted scripts/assets, one resources folder in mount order, patches sort last, independent portable copy, owner key outside distributables')
