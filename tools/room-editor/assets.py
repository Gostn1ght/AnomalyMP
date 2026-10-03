"""Read original X-Ray OGF, level geometry and DB assets without unpacking the game."""
from pathlib import Path
import collections, ctypes, hashlib, io, math, struct, threading
from PIL import Image

def chunks(data):
    p = 0
    while p + 8 <= len(data):
        kind, size = struct.unpack_from('<II', data, p)
        if p + size + 8 > len(data): raise ValueError('Повреждённый блок модели')
        if kind & 0x80000000:
            p += size + 8
            continue  # Motion blocks are not needed for the bind-pose preview.
        yield kind, memoryview(data)[p+8:p+8+size]
        p += size + 8
    # Some shipped OGF files end in the legacy writer's CRLF padding.
    if any(x not in (0,10,13,32) for x in data[p:]):
        raise ValueError('Повреждённое окончание модели')

def key(name):
    return str(name).replace('\\', '/').lower().strip('/')

class Assets:
    def __init__(self, runtime, here):
        self.runtime, self.here = Path(runtime), Path(here)
        self.entries, self.catalog, self.levels = {}, [], {}
        self.lock = threading.RLock()
        self.status = 'Чтение игровых архивов…'
        self.errors = []
        self.codec = ctypes.CDLL(str(here / 'vendor/xray-codecs.dll'))
        for fn in [self.codec.unpack_lzh, self.codec.unpack_lzo]:
            fn.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
            fn.restype = ctypes.c_int
        self.cache = here / 'cache/textures'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.models = collections.OrderedDict()

    def archive_index(self, path):
        with path.open('rb') as f:
            while raw := f.read(8):
                kind, size = struct.unpack('<II', raw)
                if kind & 0x7fffffff != 1:
                    f.seek(size, 1)
                    continue
                data = f.read(size)
                if kind & 0x80000000:
                    size = struct.unpack_from('<I', data)[0]
                    if size > 64*1024*1024: raise ValueError('Archive index too large')
                    out = ctypes.create_string_buffer(size)
                    with self.lock:
                        result = self.codec.unpack_lzh(data, len(data), out, size)
                    if result: raise ValueError('Archive index decode failed')
                    data = out.raw
                pos = 0
                while pos < len(data):
                    n, = struct.unpack_from('<H', data, pos)
                    pos += 2
                    real, packed, crc = struct.unpack_from('<3I', data, pos)
                    name = data[pos+12:pos+n-4].decode('cp1251')
                    ptr, = struct.unpack_from('<I', data, pos+n-4)
                    pos += n
                    if real and name.lower().endswith(('.ogf', '.dds', '.thm')):
                        self.entries[key(name)] = (path, ptr, packed, real)
                return

    def index(self):
        try:
            for path in sorted((self.runtime / 'db/meshes').glob('*.db*')):
                if path.name.startswith('anims'): continue
                self.archive_index(path)
            for path in sorted((self.runtime / 'db/textures').glob('*.db*')):
                self.archive_index(path)
            for folder, ext in [('meshes', '*.ogf'), ('textures', '*.dds'), ('textures', '*.thm')]:
                for path in (self.runtime / 'gamedata' / folder).rglob(ext):
                    self.entries[key(path.relative_to(self.runtime / 'gamedata'))] = path
            catalog = []
            for name, source in self.entries.items():
                if not name.endswith('.ogf'): continue
                ident = name[7:]
                parts = ident.split('/')
                category = parts[0] if len(parts) > 1 else 'other'
                if category == 'dynamics' and len(parts) > 2: category += '/' + parts[1]
                catalog.append(dict(id=ident, name=Path(ident).stem, category=category,
                                    source='Архив игры' if isinstance(source, tuple) else 'Установленная модель'))
            self.catalog = sorted(catalog, key=lambda x:x['id'])
            self.status = 'Чтение геометрии локаций…'
            for folder in sorted((self.runtime / 'gamedata/levels').iterdir()):
                if not (folder / 'level.geom').is_file() or not (folder / 'level').is_file(): continue
                try:
                    parts = dict(chunks((folder / 'level').read_bytes()))
                    shaders = bytes(parts[2])[4:].split(b'\0')
                    visuals = {}
                    for ident, data in chunks(parts[3]):
                        sections = dict(chunks(data))
                        header = struct.unpack_from('<BBH10f', sections[1])
                        if header[1] not in (0,2) or 21 not in sections: continue
                        material = shaders[header[2]].decode('cp1251')
                        if '/' not in material: continue
                        shader, texture = material.split('/', 1)
                        texture = texture.split(',')[0]
                        visuals[ident] = (bytes(sections[21]), texture, shader, header[3:9])
                        catalog_id = f'level:{folder.name}:{ident}'
                        self.catalog.append(dict(id=catalog_id, name=f'{folder.name} · {ident} · {Path(texture).name}',
                            category='levels/' + folder.name, source='Статическая геометрия локации'))
                    self.levels[folder.name] = (folder, visuals)
                except Exception as exc:
                    self.errors.append(f'{folder.name}: {exc}')
            self.status = 'Готово'
        except Exception as exc:
            self.errors.append(str(exc))
            self.status = 'Ошибка индексации'

    def read(self, name):
        source = self.entries.get(key(name))
        if source is None: raise FileNotFoundError(name)
        if isinstance(source, Path): return source.read_bytes()
        path, offset, packed, real = source
        if real > 256*1024*1024: raise ValueError('Слишком большой ресурс')
        with path.open('rb') as f:
            f.seek(offset)
            data = f.read(packed)
        if packed == real: return data
        out = ctypes.create_string_buffer(real)
        if self.codec.unpack_lzo(data, len(data), out, real): raise ValueError('Не удалось прочитать ресурс')
        return out.raw

    def texture(self, name):
        name = key(name).removesuffix('.dds')
        digest = hashlib.sha256(name.encode()).hexdigest()
        dest = self.cache / (digest + '.png')
        if not dest.exists():
            raw = self.read('textures/' + name + '.dds')
            image = Image.open(io.BytesIO(raw))
            image.thumbnail((1024,1024), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.convert('RGBA').save(out, format='PNG')
            # Parallel material requests may share this texture.
            with self.lock:
                if not dest.exists(): dest.write_bytes(out.getvalue())
        return dest.read_bytes()

    def mesh(self, ident):
        with self.lock:
            if ident in self.models:
                self.models.move_to_end(ident)
                return self.models[ident]
        result = self.level_mesh(ident) if ident.startswith('level:') else self.ogf_mesh(ident)
        if not result['parts']: raise ValueError('У объекта нет самостоятельной геометрии (эффект или ссылка)')
        with self.lock:
            self.models[ident] = result
            while len(self.models) > 24: self.models.popitem(last=False)
        return result

    def ogf_mesh(self, ident):
        result = {'parts':[], 'id':ident}
        def visit(data, depth=0):
            if depth > 8: raise ValueError('Слишком глубокая модель')
            sections = dict(chunks(data))
            if 9 in sections:
                for _, child in chunks(sections[9]): visit(child, depth+1)
            if 10 in sections:
                linked = bytes(sections[10])
                # OGF external names use zero-terminated paths; level child IDs are separate.
                count, = struct.unpack_from('<I', linked)
                for name in linked[4:].split(b'\0')[:count]:
                    if name:
                        path = name.decode('cp1251')
                        visit(self.read('meshes/' + path.removesuffix('.ogf') + '.ogf'), depth+1)
            if 3 not in sections or 4 not in sections: return
            texture, shader = bytes(sections.get(2,b'\0\0')).decode('cp1251').split('\0')[:2]
            if 'lightplanes' in shader: return
            vertices, indices = sections[3], sections[4]
            kind, count = struct.unpack_from('<II', vertices)
            if count > 500000: raise ValueError('Модель превышает 500 000 вершин')
            stride = (len(vertices)-8)//count if count else 0
            formats = {1:(60,0,48),2:(64,4,56),3:(70,6,62),4:(76,8,68),0x12071980:(60,0,48),2*0x12071980:(64,4,56),
                       4*0x12071980:(70,6,62),5*0x12071980:(76,8,68)}
            if kind in formats:
                expected, pos_offset, uv_offset = formats[kind]
                if stride != expected: raise ValueError('Неверный формат скелетной модели')
                normal_offset = pos_offset+12
            else:
                # D3D FVF, static XYZ+NORMAL+TEXn.
                if kind & 0x00e != 2: raise ValueError(f'Неподдерживаемый формат вершин {kind:#x}')
                pos_offset, normal_offset = 0, 12 if kind & 0x10 else None
                uv_offset = 12 + (12 if kind & 0x10 else 0) + (4 if kind & 0x40 else 0) + (4 if kind & 0x80 else 0)
            pos, normal, uv = [], [], []
            for i in range(count):
                start = 8+i*stride
                pos.extend(struct.unpack_from('<3f',vertices,start+pos_offset))
                normal.extend(struct.unpack_from('<3f',vertices,start+normal_offset) if normal_offset is not None else (0,1,0))
                uv.extend(struct.unpack_from('<2f',vertices,start+uv_offset) if kind>>8 & 0xf or kind in formats else (0,0))
            n, = struct.unpack_from('<I', indices)
            table = list(struct.unpack_from(f'<{n}H',indices,4))
            # Progressive meshes contain the index ranges of every LOD.
            if 6 in sections:
                sw = sections[6]
                number, = struct.unpack_from('<I',sw,16)
                if number:
                    offset, triangles, _ = struct.unpack_from('<IHH',sw,20)
                    table = table[offset:offset+triangles*3]
            if len(table)%3 or (table and max(table)>=count): raise ValueError('Повреждённые индексы модели')
            if not all(math.isfinite(x) for x in (*pos,*normal,*uv)): raise ValueError('Некорректные координаты')
            result['parts'].append(dict(texture=key(texture), shader=shader, position=pos,normal=normal,uv=uv,index=table,
                                        emissive='selflight' in shader))
        visit(self.read('meshes/' + key(ident)))
        return result

    def level_mesh(self, ident):
        _, name, number = ident.split(':')
        folder, visuals = self.levels[name]
        ref, texture, shader, bounds = visuals[int(number)]
        geom = dict(chunks((folder/'level.geom').read_bytes()))
        vb,vbase,vcount,ib,ibase,icount = struct.unpack_from('<6I',ref)
        sizes = [4,8,12,16,4,4,4,8,4,4,8,4,8,4,4,4,8]
        source, offset, buffers = geom[9], 4, []
        for _ in range(struct.unpack_from('<I',source)[0]):
            decl, stride = {}, 0
            while True:
                stream, start, kind, method, usage, index = struct.unpack_from('<HHBBBB',source,offset)
                offset += 8
                if stream == 255: break
                decl[usage,index] = (start,kind)
                stride = max(stride,start+sizes[kind])
            count, = struct.unpack_from('<I',source,offset)
            offset += 4
            buffers.append((source[offset:offset+count*stride],stride,decl))
            offset += count*stride
        source, offset, indices = geom[10], 4, []
        for _ in range(struct.unpack_from('<I',source)[0]):
            count, = struct.unpack_from('<I',source,offset)
            offset += 4
            indices.append(source[offset:offset+count*2]); offset += count*2
        data,stride,decl = buffers[vb]
        p,n,t = decl[0,0][0],decl[3,0][0],decl[5,0][0]
        origin = [(bounds[0]+bounds[3])/2,bounds[1],(bounds[2]+bounds[5])/2]
        pos,normal,uv = [],[],[]
        for i in range(vcount):
            off = (vbase+i)*stride
            pos.extend(x-origin[k] for k,x in enumerate(struct.unpack_from('<3f',data,off+p)))
            normal.extend(data[off+n+k]/127.5-1 for k in (2,1,0))
            u,v = struct.unpack_from('<2h',data,off+t)
            du = data[off+decl[6,0][0]+3]/255 if (6,0) in decl else 0
            dv = data[off+decl[7,0][0]+3]/255 if (7,0) in decl else 0
            uv.extend(((u+du)/1024,(v+dv)/1024))
        table = list(struct.unpack_from(f'<{icount}H',indices[ib],ibase*2))
        if table and max(table)>=vcount: raise ValueError('Повреждённые индексы локации')
        return dict(id=ident,parts=[dict(texture=key(texture),shader=shader,position=pos,normal=normal,uv=uv,index=table,emissive=False)])
