"""Lost Zone room editor. All game resources stay on this computer."""
from pathlib import Path
import argparse, collections, datetime, gzip, hashlib, json, math, mimetypes
import os, secrets, shutil, struct, threading, time, urllib.parse, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from assets import Assets

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent/'gamma-runtime').exists() else HERE.parents[2]
RUNTIME = ROOT / 'gamma-runtime'
TOKEN = secrets.token_urlsafe(32)

def default_project():
    if (HERE/'default.room.json').is_file():
        return json.loads((HERE/'default.room.json').read_text(encoding='utf-8'))
    source = ROOT/'engine-steamnet/scripts/netcoop-overlay/client/meshes/netcoop/personal_room.json'
    manifest = json.loads(source.read_text())
    objects = []
    for i,o in enumerate(manifest['objects']):
        name = o['model']
        ident = 'netcoop/dev_pda.ogf' if 'dev_pda' in name else 'dynamics/decor/'+name+'.ogf'
        objects.append(dict(uid=str(i+1),asset=ident.lower(),name=o['name'],position=o['position'],
            rotation=[o['angles'][1],o['angles'][0],o['angles'][2]],scale=o['scale'],hidden=False))
    return dict(version=1,name='Личная комната',objects=objects,
        shell=dict(width=5.6,height=3,front=-3.4,back=2.24,
            floor='ston/ston_beton_pod_03',ceiling='ston/ston_beton_potolok2_iov',wall='crete/crete_beton_2',tile=2),
        views=[dict(name='Общий вид',eye=[0,1.35,-4.6],target=[0,1.25,.5]),
               dict(name='Карта / вход',eye=[-1.5,1.6,.9],target=[-1.5,1.65,2.14]),
               dict(name='КПК / настройки',eye=[1.4,1.7,.1],target=[1.5,.95,1.1]),
               dict(name='Сундук / инвентарь',eye=[-1.6,1,-.85],target=[-1.65,.36,.3])],
        lamp=[-1.4,2.7,-1.6])

def vector(v, scale=False):
    if not isinstance(v,list) or len(v)!=3: raise ValueError('Нужны три координаты')
    out = [float(x) for x in v]
    if any(not math.isfinite(x) or abs(x)>1000 for x in out): raise ValueError('Координаты за пределами редактора')
    if scale and any(x < .001 or x > 100 for x in out): raise ValueError('Масштаб: 0.001–100')
    return out

def validate(project):
    if project.get('version')!=1: raise ValueError('Неподдерживаемый проект')
    if not isinstance(project.get('objects'),list) or len(project['objects'])>1000: raise ValueError('Максимум 1000 объектов')
    for o in project['objects']:
        if not isinstance(o.get('asset'),str) or len(o['asset'])>256: raise ValueError('Неверная модель')
        for k in ['position','rotation','scale']: o[k] = vector(o[k],k=='scale')
    if len(project.get('views',[]))!=4: raise ValueError('В проекте нужны четыре камеры')
    for view in project['views']:
        view['eye'],view['target'] = vector(view['eye']),vector(view['target'])
        if math.dist(view['eye'],view['target'])<.1: raise ValueError('Камера слишком близко к цели')
    project['lamp'] = vector(project['lamp'])
    s=project['shell']
    for k in ['width','height','front','back','tile']:
        s[k]=float(s[k])
        if not math.isfinite(s[k]) or abs(s[k])>50: raise ValueError('Неверные размеры комнаты')
    if s['width']<1 or s['height']<1 or s['tile']<.1 or s['back']-s['front']<1:
        raise ValueError('Комната должна быть не меньше одного метра')
    for k in ['floor','ceiling','wall']:
        if not isinstance(s[k],str) or len(s[k])>200 or '\x00' in s[k]: raise ValueError('Неверная текстура')
    return project

def shell_parts(s):
    w,h,f,b = s['width']/2,s['height'],s['front'],s['back']
    planes=[(s['floor'],[[-w,0,f],[w,0,f],[w,0,b],[-w,0,b]],[0,1,0]),
            (s['ceiling'],[[-w,h,f],[w,h,f],[w,h,b],[-w,h,b]],[0,-1,0]),
            (s['wall'],[[-w,0,b],[w,0,b],[w,h,b],[-w,h,b]],[0,0,-1]),
            (s['wall'],[[-w,0,f],[-w,0,b],[-w,h,b],[-w,h,f]],[1,0,0]),
            (s['wall'],[[w,0,f],[w,0,b],[w,h,b],[w,h,f]],[-1,0,0])]
    result=[]
    for texture,corners,n in planes:
        a,bb,c,_=corners
        u,v=[bb[k]-a[k] for k in range(3)],[c[k]-a[k] for k in range(3)]
        cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        indices=[0,1,2,0,2,3] if sum(cross[k]*n[k] for k in range(3))>0 else [0,2,1,0,3,2]
        uu,vv=math.dist(a,bb)/s['tile'],math.dist(bb,c)/s['tile']
        result.append(dict(texture=texture,position=sum(corners,[]),normal=n*4,uv=[0,0,uu,0,uu,vv,0,vv],index=indices,emissive=False))
    return result

def rotate(v, angles):
    p,h,r=angles
    x,y,z=v
    x,y=x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r)
    y,z=y*math.cos(p)-z*math.sin(p),y*math.sin(p)+z*math.cos(p)
    return [x*math.cos(h)+z*math.sin(h),y,-x*math.sin(h)+z*math.cos(h)]

def bake(project, assets):
    validate(project)
    batches=collections.defaultdict(bytearray)
    def add(part, transform=None):
        texture=part['texture'].replace('/','\\')
        if not texture or len(texture.encode('cp1251'))>254: raise ValueError('У модели нет корректного материала')
        assets.read('textures/'+texture+'.dds')  # Fail before installing a room with missing materials.
        vertices=[]
        pos,norm,uv=part['position'],part['normal'],part['uv']
        for i in range(len(pos)//3):
            point,normal=pos[i*3:i*3+3],norm[i*3:i*3+3]
            if transform:
                point=rotate([point[k]*transform['scale'][k] for k in range(3)],transform['rotation'])
                point=[point[k]+transform['position'][k] for k in range(3)]
                normal=rotate([normal[k]/transform['scale'][k] for k in range(3)],transform['rotation'])
            length=math.sqrt(sum(x*x for x in normal)) or 1
            normal=[x/length for x in normal]
            emissive=part['emissive'] or ('lightbulb' in (transform or {}).get('asset','') and 'lampa_g' in texture)
            vertices.append(struct.pack('<3f3fI2f',*point,*normal,0xffffff|(0xff000000 if emissive else 0),*uv[i*2:i*2+2]))
        for index in part['index']: batches[texture].extend(vertices[index])
        if len(batches)>128 or len(batches[texture])//36>300000:
            raise ValueError('Комната слишком сложная для игрового меню: до 128 материалов и 100 000 треугольников на материал')
    for p in shell_parts(project['shell']): add(p)
    for o in project['objects']:
        if o.get('hidden'): continue
        for p in assets.mesh(o['asset'])['parts']: add(p,o)
    triangles=sum(len(b)//108 for b in batches.values())
    if triangles>200000: raise ValueError('Больше 200 000 треугольников: упростите комнату перед экспортом')
    data=bytearray(b'NCRM'+struct.pack('<II',2,len(batches)))
    for name,vertices in sorted(batches.items()):
        data.extend(name.encode('cp1251')+b'\0'+struct.pack('<I',len(vertices)//36)+vertices)
    return data,triangles,len(batches)

def camera_config(p):
    def fmt(v): return ', '.join(f'{x:.6f}' for x in v)
    lines=['[room]', 'lamp = '+fmt(p['lamp'])]
    for i,v in enumerate(p['views']):
        lines += [f'eye{i} = '+fmt(v['eye']),f'target{i} = '+fmt(v['target'])]
    return ('\n'.join(lines)+'\n').encode('ascii')

def safe_write(path, data, backup=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    if backup and path.exists():
        dest=HERE/'backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')/path.name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_bytes(data);os.replace(temp,path)

def camera_binary(p):
    values=[]
    for view in p['views']: values.extend(view['eye']+view['target'])
    return b'NCRC'+struct.pack('<I27f',1,*(values+p['lamp']))

class Handler(BaseHTTPRequestHandler):
    def reply(self, data, content='application/json', status=200):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode()
        compress=len(data)>2048 and 'gzip' in self.headers.get('Accept-Encoding','') and content!='image/png'
        if compress: data=gzip.compress(data,compresslevel=3)
        self.send_response(status)
        self.send_header('Content-Type',content+'; charset=utf-8' if content.startswith(('text/','application/json')) else content)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','private, max-age=3600' if content=='image/png' else 'no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if compress:self.send_header('Content-Encoding','gzip')
        try:
            self.end_headers();self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass  # Closing/reloading the preview cancels outstanding asset requests.

    def do_GET(self):
        u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
        arg=lambda name,default='':q.get(name,[default])[0]
        try:
            if u.path=='/api/config':
                self.reply(dict(tool='lostzone-room-editor',pid=os.getpid(),folder=str(HERE),token=TOKEN,runtime=str(RUNTIME),default=default_project()));return
            if u.path=='/api/catalog':
                search,category=arg('q').lower(),arg('category')
                rows=[o for o in ASSETS.catalog if (not search or all(s in o['id'].lower() or s in o['name'].lower() for s in search.split())) and (not category or o['category']==category)]
                page=max(0,int(arg('page','0')));size=20
                categories=collections.Counter(o['category'] for o in ASSETS.catalog)
                self.reply(dict(status=ASSETS.status,total=len(rows),count=len(ASSETS.catalog),items=rows[page*size:(page+1)*size],categories=categories,errors=ASSETS.errors));return
            if u.path=='/api/model':self.reply(ASSETS.mesh(arg('id')));return
            if u.path=='/api/texture':self.reply(ASSETS.texture(arg('id')),'image/png');return
            if u.path=='/api/textures':
                rows=[n[9:-4] for n in ASSETS.entries if n.endswith('.dds') and '_bump' not in n and arg('q','').lower() in n]
                self.reply(sorted(rows)[:300]);return
            if u.path=='/api/shell':self.reply(shell_parts(json.loads(arg('data'))));return
            path=(HERE/'web'/urllib.parse.unquote(u.path.lstrip('/') or 'index.html')).resolve()
            if path.is_relative_to((HERE/'web').resolve()) and path.is_file():
                self.reply(path.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream');return
            if u.path.startswith('/vendor/'):
                path=(HERE/u.path.lstrip('/')).resolve()
                if path.is_relative_to((HERE/'vendor').resolve()) and path.suffix in ('.js','.txt') and path.is_file():
                    self.reply(path.read_bytes(),'text/javascript' if path.suffix=='.js' else 'text/plain');return
            self.reply(dict(error='Не найдено'),status=404)
        except Exception as exc:self.reply(dict(error=str(exc)),status=400)

    def do_POST(self):
        try:
            if self.headers.get('X-Room-Token')!=TOKEN:raise ValueError('Откройте редактор с локального адреса')
            size=int(self.headers.get('Content-Length','0'))
            if size<1 or size>2*1024*1024:raise ValueError('Слишком большой проект')
            project=validate(json.loads(self.rfile.read(size)))
            if self.path=='/api/save':
                data=json.dumps(project,ensure_ascii=False,indent=2).encode()
                safe_write(HERE/'projects/last.room.json',data,True)
                self.reply(dict(ok=True,path=str(HERE/'projects/last.room.json')));return
            if self.path=='/api/export':
                data,tris,materials=bake(project,ASSETS)
                manifest=json.dumps(project,ensure_ascii=False,indent=2).encode()
                dest=HERE/'exports/personal_room.room'
                safe_write(dest,data,True)
                safe_write(dest.with_suffix('.editor.json'),manifest,True)
                config=camera_config(project)
                safe_write(HERE/'exports/personal_room.ltx',config,True)
                camera=camera_binary(project)
                safe_write(HERE/'exports/personal_room.camera',camera,True)
                for base in [RUNTIME/'gamedata',ROOT/'engine-steamnet/scripts/netcoop-overlay/client']:
                    safe_write(base/'meshes/netcoop/personal_room.room',data,True)
                    safe_write(base/'meshes/netcoop/personal_room.camera',camera,True)
                    safe_write(base/'configs/netcoop/personal_room.ltx',config,True)
                self.reply(dict(ok=True,path=str(dest),triangles=tris,materials=materials,
                    message='Комната установлена. Перезапустите клиент игры, чтобы увидеть изменения.'));return
            self.reply(dict(error='Не найдено'),status=404)
        except Exception as exc:self.reply(dict(error=str(exc)),status=400)

    def log_message(self, fmt, *args):
        if args and str(args[1] if len(args)>1 else '') != '200':super().log_message(fmt,*args)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=18743)
    parser.add_argument('--no-browser',action='store_true')
    options=parser.parse_args()
    ASSETS=Assets(RUNTIME,HERE)
    threading.Thread(target=ASSETS.index,daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',options.port),Handler)
    url=f'http://127.0.0.1:{options.port}/'
    print('Lost Zone Room Editor: '+url,flush=True)
    if not options.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
