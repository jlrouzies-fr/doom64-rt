"""Shared helpers for RTGL1 glTF replacement models (rt/replace/set_*.gltf).

Two jobs:

  * read/write the glTF + .bin pair without a glTF library (pure stdlib), and
  * re-shade a voxel mesh the way Duke-RT 0.4.2 does -- normals computed at the
    whole-voxel level from neighbour occupancy, instead of per-face axis-aligned
    normals.

Why the normal trick works here at all: RTGL1 overwrites vertex normals with the
flat face normal in VertexPreprocessPartial.inl, but only for geometry flagged
GEOM_INST_FLAG_IS_DYNAMIC, and replacements are uploaded with
isDynamicVertexData = false (Scene.cpp -> ASManager::AddMeshPrimitive). So
normals baked into the glTF survive untouched. This is an offline-only fix.

Units: glTF positions are metres; one Doom map unit is 1/32 m (ONEGAMEUNIT_IN_METERS
in rt_main.cpp), and the stock voxel models use a 1-map-unit voxel.
"""

import json
import math
import struct
from collections import deque

UNITS_PER_METRE = 32.0

_COMPONENT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# --------------------------------------------------------------------------- io


def load(gltf_path):
    """Returns (doc, buffer_bytes). Assumes the single-buffer layout Blender emits."""
    with open(gltf_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    uri = doc["buffers"][0]["uri"]
    base = gltf_path.rsplit("/", 1)[0] if "/" in gltf_path else "."
    with open(f"{base}/{uri}", "rb") as f:
        return doc, f.read()


def read_accessor(doc, buf, index):
    """Reads an accessor into a list of tuples, honouring byteStride."""
    acc = doc["accessors"][index]
    ncomp = _NCOMP[acc["type"]]
    fmt, size = _COMPONENT[acc["componentType"]]
    view = doc["bufferViews"][acc["bufferView"]]
    off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or (size * ncomp)
    unpack = struct.Struct("<" + fmt * ncomp).unpack_from
    return [unpack(buf, off + i * stride) for i in range(acc["count"])]


def read_indices(doc, buf, prim):
    """Triangle corner indices; synthesises 0..n-1 for a non-indexed primitive."""
    if "indices" in prim:
        return [i[0] for i in read_accessor(doc, buf, prim["indices"])]
    count = doc["accessors"][prim["attributes"]["POSITION"]]["count"]
    return list(range(count))


class BufferBuilder:
    """Accumulates bufferViews/accessors into one binary blob."""

    def __init__(self):
        self.blob = bytearray()
        self.views = []
        self.accessors = []

    def _pad(self):
        while len(self.blob) % 4:
            self.blob.append(0)

    def add(self, values, gltf_type, component_type, target=None, minmax=False):
        self._pad()
        ncomp = _NCOMP[gltf_type]
        fmt, _ = _COMPONENT[component_type]
        offset = len(self.blob)
        packer = struct.Struct("<" + fmt * ncomp)
        for v in values:
            self.blob += packer.pack(*(v if ncomp > 1 else (v,)))
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(self.blob) - offset}
        if target is not None:
            view["target"] = target
        self.views.append(view)
        acc = {
            "bufferView": len(self.views) - 1,
            "componentType": component_type,
            "count": len(values),
            "type": gltf_type,
        }
        if minmax and values:
            cols = list(zip(*values)) if ncomp > 1 else [values]
            acc["min"] = [min(c) for c in cols]
            acc["max"] = [max(c) for c in cols]
        self.accessors.append(acc)
        return len(self.accessors) - 1


# ------------------------------------------------------------------ voxel logic


def _tri_normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def _dominant_axis_unit(n):
    """Snaps an axis-aligned face normal to a unit axis vector, or None if degenerate."""
    ax = [abs(c) for c in n]
    k = ax.index(max(ax))
    if ax[k] < 1e-12:
        return None
    out = [0.0, 0.0, 0.0]
    out[k] = 1.0 if n[k] > 0 else -1.0
    return tuple(out)


def voxel_of_face(positions, tri, voxel_units=1.0):
    """The voxel a surface triangle belongs to, as integer grid coords.

    Steps half a voxel inward from the face centroid along the inward normal, so
    the grid offset is discovered from the data rather than assumed.
    """
    a, b, c = (positions[i] for i in tri)
    n = _dominant_axis_unit(_tri_normal(a, b, c))
    if n is None:
        return None
    cx = (a[0] + b[0] + c[0]) / 3.0 * UNITS_PER_METRE
    cy = (a[1] + b[1] + c[1]) / 3.0 * UNITS_PER_METRE
    cz = (a[2] + b[2] + c[2]) / 3.0 * UNITS_PER_METRE
    half = voxel_units * 0.5
    return (
        int(math.floor((cx - n[0] * half) / voxel_units)),
        int(math.floor((cy - n[1] * half) / voxel_units)),
        int(math.floor((cz - n[2] * half) / voxel_units)),
    )


def fill_interior(surface):
    """Surface voxels plus everything they enclose.

    Interior voxels have no faces, so they never appear in the surface set -- but
    they decide whether a surface voxel's neighbour counts as empty. Getting this
    wrong makes solid regions read as convex shells. Flood-fills the outside of a
    padded bounding box; whatever the fill cannot reach is inside.
    """
    if not surface:
        return set()
    xs = [v[0] for v in surface]
    ys = [v[1] for v in surface]
    zs = [v[2] for v in surface]
    lo = (min(xs) - 1, min(ys) - 1, min(zs) - 1)
    hi = (max(xs) + 1, max(ys) + 1, max(zs) + 1)

    outside = set()
    start = lo
    queue = deque([start])
    outside.add(start)
    while queue:
        x, y, z = queue.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            p = (x + dx, y + dy, z + dz)
            if p in outside or p in surface:
                continue
            if not (lo[0] <= p[0] <= hi[0] and lo[1] <= p[1] <= hi[1] and lo[2] <= p[2] <= hi[2]):
                continue
            outside.add(p)
            queue.append(p)

    filled = set(surface)
    for x in range(lo[0], hi[0] + 1):
        for y in range(lo[1], hi[1] + 1):
            for z in range(lo[2], hi[2] + 1):
                p = (x, y, z)
                if p not in outside:
                    filled.add(p)
    return filled


_NEIGHBOURS_26 = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
]


def occupancy_normals(occupied, voxels):
    """Duke-RT 0.4.2's rule: normal = outward gradient of the occupancy field.

    For each voxel, sum the unit offsets to its 26 neighbours that are empty and
    normalise. A voxel on a flat wall gets the wall normal; one on a corner or a
    curve gets something in between, which is what removes the faceted look
    without touching the silhouette.

    Returns {voxel: (x, y, z)}; voxels with no empty neighbour are omitted.
    Do NOT use the result directly as a shading normal -- see shade_normal().
    """
    out = {}
    for v in voxels:
        sx = sy = sz = 0.0
        for dx, dy, dz in _NEIGHBOURS_26:
            if (v[0] + dx, v[1] + dy, v[2] + dz) in occupied:
                continue
            inv = 1.0 / math.sqrt(dx * dx + dy * dy + dz * dz)
            sx += dx * inv
            sy += dy * inv
            sz += dz * inv
        length = math.sqrt(sx * sx + sy * sy + sz * sz)
        if length > 1e-9:
            out[v] = (sx / length, sy / length, sz / length)
    return out


def shade_normal(gradient, face, strength=1.0):
    """Combines the occupancy gradient with a face normal, safely.

    The raw gradient cannot be used on its own. These models are thin shells --
    POSSA has 5046 surface voxels but only 9 interior cells -- and for a
    one-voxel-thick plate the empty neighbours sit symmetrically on BOTH sides,
    so the gradient is free to point straight through the surface. Measured on
    POSSA: 34.6% of faces got a gradient facing the wrong way, which shades
    worse than the blocky original.

    So keep only the part of the gradient tangential to the face normal. On a
    flat wall that part is ~zero and the normal is unchanged; on an edge or a
    curve it tilts the normal along the surface, which is the effect we want.
    The result is guaranteed to stay in the face's hemisphere.

    strength 1.0 allows up to a 45-degree tilt.
    """
    if gradient is None:
        return face
    d = gradient[0] * face[0] + gradient[1] * face[1] + gradient[2] * face[2]
    tx = gradient[0] - d * face[0]
    ty = gradient[1] - d * face[1]
    tz = gradient[2] - d * face[2]
    nx = face[0] + strength * tx
    ny = face[1] + strength * ty
    nz = face[2] + strength * tz
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-9:
        return face
    return (nx / length, ny / length, nz / length)
