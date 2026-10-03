"""Package a separate editor folder with a private Python runtime."""
from pathlib import Path
import json, shutil, urllib.request, zipfile
import PIL
from server import default_project, ROOT
here=Path(__file__).resolve().parent
dest=ROOT/'LostZoneRoomEditor'
dest.mkdir(exist_ok=True)
def copy(source,target):
    source,target=Path(source),Path(target)
    if target.is_file() and source.read_bytes()==target.read_bytes():return str(target)
    return shutil.copy2(source,target)
for name in ['assets.py','server.py','launch.pyw','stop.pyw','README.md']:
    copy(here/name,dest/name)
for folder in ['web','vendor','native']:
    shutil.copytree(here/folder,dest/folder,dirs_exist_ok=True,copy_function=copy,
                    ignore=shutil.ignore_patterns('*.obj','*.lib','*.exp','*.pdb'))
(dest/'default.room.json').write_text(json.dumps(default_project(),ensure_ascii=False,indent=2),encoding='utf-8')
runtime=dest/'runtime'
runtime.mkdir(exist_ok=True)
archive=dest/'cache/python-3.13.7-embed-amd64.zip'
archive.parent.mkdir(exist_ok=True)
if not archive.exists():urllib.request.urlretrieve('https://www.python.org/ftp/python/3.13.7/python-3.13.7-embed-amd64.zip',archive)
with zipfile.ZipFile(archive) as z:
    for entry in z.infolist():
        target=runtime/entry.filename
        if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
        elif not target.exists() or target.read_bytes()!=z.read(entry):
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(entry))
(runtime/'python313._pth').write_text('python313.zip\n.\nLib/site-packages\n..\nimport site\n')
packages=runtime/'Lib/site-packages'
shutil.copytree(Path(PIL.__file__).parent,packages/'PIL',dirs_exist_ok=True,copy_function=copy,ignore=shutil.ignore_patterns('__pycache__'))
for folder in Path(PIL.__file__).parent.parent.glob('pillow.libs'):
    shutil.copytree(folder,packages/folder.name,dirs_exist_ok=True,copy_function=copy)
for folder in Path(PIL.__file__).parent.parent.glob('pillow-*.dist-info'):
    shutil.copytree(folder/'licenses',packages/'Pillow-licenses',dirs_exist_ok=True,copy_function=copy)
for name,script in [('Start Editor.cmd','launch.pyw'),('Stop Editor.cmd','stop.pyw')]:
    (dest/name).write_text(f'@echo off\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0{script}"\r\n',encoding='ascii',newline='')
for folder in ['projects','exports','backups']:(dest/folder).mkdir(exist_ok=True)
print(dest)
