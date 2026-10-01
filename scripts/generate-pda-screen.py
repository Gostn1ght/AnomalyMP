"""Generate a separate emissive screen for the standard world PDA housing.

Positions follow its front face/atlas layout; no existing model or texture
is changed. The owner frame replaces the user texture at runtime.
"""
from pathlib import Path
import struct, math

def chunk(kind, data):
    return struct.pack('<II', kind, len(data)) + data

positions = [(-.0365, .0175, .0588), (.0358, .0175, .0588),
             (-.0365, .0175, -.0425), (.0358, .0175, -.0425)]
uvs = [(0, 0), (1, 0), (0, 1), (1, 1)]
low = tuple(min(p[k] for p in positions) - .0001 for k in range(3))
high = tuple(max(p[k] for p in positions) + .0001 for k in range(3))
center = tuple((low[k] + high[k]) / 2 for k in range(3))
radius = math.dist(low, high) / 2
header = struct.pack('<BBH10f', 4, 0, 0, *low, *high, *center, radius)
vertices = struct.pack('<II', 0x112, 4)  # XYZ | NORMAL | TEX1
for pos, uv in zip(positions, uvs):
    vertices += struct.pack('<8f', *pos, 0, 1, 0, *uv)
indices = struct.pack('<I6H', 6, 0, 1, 2, 2, 1, 3)
data = (chunk(1, header) + chunk(2, b'$user$netcoop_pda_blank\0models\\selflight\0')
        + chunk(3, vertices) + chunk(4, indices))
target = Path(__file__).parent / 'netcoop-overlay/client/meshes/netcoop/pda_screen.ogf'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(data)
print(target, len(data), 'bytes')
