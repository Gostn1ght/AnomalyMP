"""Inventory installed original meshes for the hideout, including their bounds."""
from pathlib import Path
import sys, json
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools/room-editor'))
from assets import Assets
a=Assets(root.parent/'gamma-runtime',root/'tools/room-editor'); a.index()
terms=('sofa','divan','couch','safe','seif','ruck','backpack','gas_lamp','table','stove','bottle','light','poster','door','bed')
result=[]
for entry in a.catalog:
    ident=entry['id']
    if ident.startswith('level:') or not any(t in ident for t in terms): continue
    try:
        mesh=a.mesh(ident)
        xyz=[p['position'] for p in mesh['parts']]
        bounds=[[min(v[k::3]) for k in range(3)] for v in xyz]
        lower=[min(b[k] for b in bounds) for k in range(3)]
        upper=[max(max(v[k::3]) for v in xyz) for k in range(3)]
        result.append(dict(id=ident,min=lower,max=upper,triangles=sum(len(p['index'])//3 for p in mesh['parts'])))
    except Exception: pass
out=root.parent/'build-logs/hideout-assets.json'
out.write_text(json.dumps(result,indent=2))
print(json.dumps([r for r in result if any(t in r['id'] for t in ('sofa','divan','couch','safe','seif','ruck','backpack','gas_lamp','stove'))],indent=2))
print('Textures:', [n for n in a.entries if n.startswith(('textures/wood/','textures/wall/','textures/crete/')) and n.endswith('.dds') and '_bump' not in n][:110])
