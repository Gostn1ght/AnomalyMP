"""Serve the room check page for the built menu room.

Needs the room editor asset server on 127.0.0.1:18743 for textures
(python tools/room-editor/server.py --no-browser). Then open
http://127.0.0.1:18745/ ; ?view=N picks a camera, the "check void" button
(window.scan()) renders from a grid of cameras inside the room and counts
empty-space pixels.
"""
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.request

root = Path(__file__).resolve().parents[1]
editor = root / 'tools/room-editor'
scene = root.parent / 'build-logs/lostzone-room.json'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/texture?'):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18743/api/texture?' + self.path.split('?', 1)[1], timeout=60) as f:
                    data = f.read()
            except Exception:
                self.send_error(404); return
            content = 'image/png'
        elif self.path == '/scene':
            data = scene.read_bytes(); content = 'application/json'
        elif self.path.startswith('/vendor/'):
            p = (editor / self.path.lstrip('/')).resolve()
            if not p.is_relative_to((editor / 'vendor').resolve()) or not p.is_file():
                self.send_error(404); return
            data = p.read_bytes(); content = 'text/javascript'
        else:
            data = (editor / 'room-check.html').read_bytes(); content = 'text/html; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


print('Room check http://127.0.0.1:18745', flush=True)
ThreadingHTTPServer(('127.0.0.1', 18745), Handler).serve_forever()
