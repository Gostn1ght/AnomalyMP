from pathlib import Path
import json, os, subprocess, sys, time, urllib.request, webbrowser

here=Path(__file__).resolve().parent
url='http://127.0.0.1:18743/'
def alive():
    try:
        with urllib.request.urlopen(url+'api/config',timeout=1) as response:
            return json.load(response).get('tool')=='lostzone-room-editor'
    except Exception:return False
if not alive():
    log=(here/'editor.log').open('a',encoding='utf-8')
    process=subprocess.Popen([sys.executable,'-X','utf8',str(here/'server.py'),'--no-browser'],
        cwd=here,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    (here/'editor.pid').write_text(str(process.pid))
    for _ in range(100):
        if alive():break
        if process.poll() is not None:break
        time.sleep(.1)
if alive():webbrowser.open(url)
else:os.startfile(str(here/'editor.log'))
