"""Read-only browser scene inspection. Geometry is identical; lighting is WebGL."""
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
import urllib.request
root=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/texture?'):
            with urllib.request.urlopen('http://127.0.0.1:18743/api/texture?'+self.path.split('?',1)[1],timeout=60) as f:data=f.read()
            content='image/png'
        elif self.path=='/scene': data=(root.parent/'build-logs/hideout-preview.json').read_bytes();content='application/json'
        elif self.path.startswith('/vendor/'):
            p=(root/'tools/room-editor'/self.path.lstrip('/')).resolve()
            if not p.is_relative_to((root/'tools/room-editor/vendor').resolve()):self.send_error(404);return
            data=p.read_bytes();content='text/javascript'
        else:data=(root/'tools/room-editor/hideout-preview.html').read_bytes();content='text/html; charset=utf-8'
        self.send_response(200);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
print('Hideout preview http://127.0.0.1:18744',flush=True)
HTTPServer(('127.0.0.1',18744),Handler).serve_forever()
