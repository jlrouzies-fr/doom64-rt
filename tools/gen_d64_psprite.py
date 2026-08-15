"""Generate first-person weapon replacement models from Doom 64 sprite art.

A psprite has exactly one camera view, so depth has to be invented: thickness at
each pixel follows sqrt(distance to the silhouette edge), which reads as a
rounded solid that tapers to nothing at the outline rather than a slab with hard
sides. Nothing else is invented -- the silhouette and the colours are the art's.

Normals use rt_voxel.shade_normal: the Duke-RT 0.4.2 neighbour-occupancy rule,
constrained to each face's hemisphere. The extruded volume here is SOLID, so the
occupancy gradient is well conditioned (unlike the stock enemy meshes, which are
one-voxel shells where the raw gradient can point straight through the surface).

SCALE -- calibrated once, applied everywhere. A viewmodel is not at 1px = 1 map
unit. Its quad comes from HUDSprite::GetWeaponRect (hw_weapon.cpp), and the two
scale factors there depend only on viewwidth/viewheight, SCREENWIDTH/HEIGHT,
WidescreenRatio, screenblocks and baseScale -- NOT on the sprite. So one
RTWPNQUAD measurement fixes the metres-per-pixel for every weapon, and each
frame's own position follows from its grAb offsets:

    left_px = r.left - 160              r.left = -grAb.x
    top_px  = r.top  - C                r.top  = -grAb.y

with C absorbing the constant YAdjust/ftextureadj terms. Verified to reproduce a
measured PISGA quad to within a tenth of a millimetre on every edge.

To re-calibrate (different resolution or status bar), run the game with
`rt_wpn_debug 1`, take the RTWPNQUAD line for any weapon, and pass it as
--cal-sprite/--cal-frame/--cal-min/--cal-max.
"""

import argparse
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt_voxel as rv

from PIL import Image

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963

# Faces of a unit voxel: (offset to neighbour, outward normal, 4 corners ccw).
_FACES = [
    ((1, 0, 0), (1.0, 0.0, 0.0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), (-1.0, 0.0, 0.0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), (0.0, 1.0, 0.0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), (0.0, -1.0, 0.0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), (0.0, 0.0, 1.0), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), (0.0, 0.0, -1.0), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


# ------------------------------------------------------------------- wad access


def wad_lumps(path):
    with open(path, "rb") as f:
        data = f.read()
    _, count, dirofs = struct.unpack_from("<4sii", data, 0)
    out = {}
    for i in range(count):
        ofs, size, name = struct.unpack_from("<ii8s", data, dirofs + i * 16)
        out[name.rstrip(b"\x00").decode("latin1")] = (ofs, size)
    return data, out


def read_grab(blob):
    """Doom sprite offsets from a PNG's grAb chunk. Pillow drops these."""
    pos = 8
    while pos + 8 <= len(blob):
        (length,) = struct.unpack_from(">I", blob, pos)
        ctype = blob[pos + 4 : pos + 8]
        if ctype == b"grAb":
            return struct.unpack_from(">ii", blob, pos + 8)
        if ctype in (b"IDAT", b"IEND"):
            break
        pos += 12 + length
    return (0, 0)


def sprite_frames(data, lumps, sprite):
    """{frame letter: (RGBA image, grAb)} for one 4-letter psprite name."""
    import io

    frames = {}
    for name, (ofs, size) in lumps.items():
        if len(name) < 6 or name[:4] != sprite or name[5] != "0":
            continue
        blob = data[ofs : ofs + size]
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            print(f"  skipping {name}: not a PNG lump")
            continue
        frames[name[4]] = (Image.open(io.BytesIO(blob)).convert("RGBA"), read_grab(blob))
    return dict(sorted(frames.items()))


# --------------------------------------------------------------------- geometry


def distance_transform(mask, w, h):
    """Chamfer distance to the nearest transparent pixel (2-pass, 3-4 weights)."""
    INF = 1 << 30
    d = [0 if not mask[y * w + x] else INF for y in range(h) for x in range(w)]

    def at(x, y):
        return d[y * w + x] if 0 <= x < w and 0 <= y < h else 0

    for y in range(h):
        for x in range(w):
            if d[y * w + x]:
                d[y * w + x] = min(d[y * w + x], at(x - 1, y) + 3, at(x, y - 1) + 3,
                                   at(x - 1, y - 1) + 4, at(x + 1, y - 1) + 4)
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            if d[y * w + x]:
                d[y * w + x] = min(d[y * w + x], at(x + 1, y) + 3, at(x, y + 1) + 3,
                                   at(x + 1, y + 1) + 4, at(x - 1, y + 1) + 4)
    return [v / 3.0 for v in d]


def build_voxels(img, depth_k, max_depth):
    w, h = img.size
    px = img.load()
    mask = [px[x, y][3] > 127 for y in range(h) for x in range(w)]
    dist = distance_transform(mask, w, h)
    occupied = set()
    for y in range(h):
        for x in range(w):
            if not mask[y * w + x]:
                continue
            hz = int(round(min(max_depth, depth_k * math.sqrt(dist[y * w + x]))))
            for z in range(-hz, hz + 1):
                occupied.add((x, y, z))
    return occupied, w, h


def mesh_voxels(occupied, img_w, img_h, sx, sy, sz, origin):
    """Surface faces only, UV'd to the source pixel, with occupancy normals.

    Voxel space is (column, row-from-top, depth). Model space is CAMERA space --
    a replacement rides m_mainCameraView_Inverse as its transform -- i.e. the GL
    convention X right, Y up, -Z forward, NOT the Z-up of world-space enemies.
    The map (col, row, depth) -> (col, -row, depth) is applied to POSITIONS AND
    NORMALS alike; applying it to only one leaves half the faces lit from behind.
    Its determinant is -1, so the winding is reversed to match.
    """
    gradient = rv.occupancy_normals(occupied, occupied)
    pos, nrm, uv, idx = [], [], [], []
    weld = {}
    ox, oy, oz = origin
    for v in occupied:
        vx, vy, vz = v
        for offset, face, corners in _FACES:
            if (vx + offset[0], vy + offset[1], vz + offset[2]) in occupied:
                continue
            n = rv.shade_normal(gradient.get(v), face)
            n = (n[0], -n[1], n[2])
            # Sample the pixel centre so filtering cannot bleed a neighbouring
            # pixel (or the transparent surround) onto a face.
            u = (vx + 0.5) / img_w
            t = (vy + 0.5) / img_h
            quad = []
            for cx, cy, cz in corners:
                key = (vx + cx, vy + cy, vz + cz, n, u, t)
                j = weld.get(key)
                if j is None:
                    j = len(pos)
                    weld[key] = j
                    pos.append((ox + (vx + cx) * sx,
                                oy - (vy + cy) * sz,
                                oz + (vz + cz) * sy))
                    nrm.append(n)
                    uv.append((u, t))
                quad.append(j)
            idx += [quad[0], quad[2], quad[1], quad[0], quad[3], quad[2]]
    return pos, nrm, uv, idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wad", required=True)
    ap.add_argument("--sprite", action="append", required=True, help="4-letter psprite name; repeatable")
    ap.add_argument("--out-set", action="append", required=True)
    ap.add_argument("--replace-dir", action="append", required=True)
    ap.add_argument("--cal-sprite", default="PISG")
    ap.add_argument("--cal-frame", default="A")
    ap.add_argument("--cal-min", type=float, nargs=3, required=True, metavar=("X", "Y", "Z"))
    ap.add_argument("--cal-max", type=float, nargs=3, required=True, metavar=("X", "Y", "Z"))
    ap.add_argument("--depth-k", type=float, default=1.6, help="thickness per sqrt(px from edge)")
    ap.add_argument("--max-depth", type=float, default=10.0, help="half-depth cap, in voxels")
    args = ap.parse_args()

    data, lumps = wad_lumps(args.wad)

    # --- calibrate from the one measured quad -------------------------------
    cal = sprite_frames(data, lumps, args.cal_sprite)[args.cal_frame]
    cal_img, (cal_lo, cal_to) = cal
    cw, ch = cal_img.size
    SX = (args.cal_max[0] - args.cal_min[0]) / cw
    SY = (args.cal_max[1] - args.cal_min[1]) / ch
    Z = (args.cal_min[2] + args.cal_max[2]) / 2.0
    # left_px = (-grAb.x) - 160 must reproduce cal_min[0]/SX; solve the vertical
    # constant C the same way from the measured top edge.
    C = (-cal_to) - (-args.cal_max[1] / SY)
    print(f"calibration from {args.cal_sprite}{args.cal_frame} ({cw}x{ch}px, grAb {cal_lo},{cal_to}):")
    print(f"  {SX*1000:.4f} mm/px across, {SY*1000:.4f} mm/px down, plane z={Z:.4f} m, C={C:.2f}")
    lp = (-cal_lo) - 160
    tp = (-cal_to) - C
    print(f"  check: x[{lp*SX:+.4f},{(lp+cw)*SX:+.4f}] y[{-(tp+ch)*SY:+.4f},{-tp*SY:+.4f}]"
          f"  vs measured x[{args.cal_min[0]:+.4f},{args.cal_max[0]:+.4f}] "
          f"y[{args.cal_min[1]:+.4f},{args.cal_max[1]:+.4f}]")

    bb = rv.BufferBuilder()
    out_meshes, out_nodes, materials, textures, images = [], [], [], [], []
    tex_files = {}
    total_verts = 0

    for sprite in args.sprite:
        frames = sprite_frames(data, lumps, sprite)
        if not frames:
            print(f"{sprite}: no sprite lumps, skipping")
            continue
        print(f"{sprite}: {len(frames)} frames {''.join(frames)}")
        for letter, (img, (lo, to)) in frames.items():
            w, h = img.size
            left_px = (-lo) - 160
            top_px = (-to) - C
            origin = (left_px * SX, -top_px * SY, Z)

            occupied, _, _ = build_voxels(img, args.depth_k, args.max_depth)
            # Depth voxels stay cubic against the average of the two screen scales.
            p, n, u, i = mesh_voxels(occupied, w, h, SX, (SX + SY) * 0.5, SY, origin)
            total_verts += len(p)

            name = sprite + letter
            mi = len(materials)
            tex = f"vx_{name}.png"
            tex_files[tex] = img
            materials.append({
                "name": f"vx_{name}",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": mi},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.9,
                },
                "alphaMode": "MASK",
                "alphaCutoff": 0.5,
                "doubleSided": False,
            })
            textures.append({"sampler": 0, "source": mi})
            images.append({"mimeType": "image/png", "name": f"vx_{name}", "uri": f"ext/{tex}"})

            out_meshes.append({"name": name, "primitives": [{
                "attributes": {
                    "POSITION": bb.add(p, "VEC3", 5126, ARRAY_BUFFER, minmax=True),
                    "NORMAL": bb.add(n, "VEC3", 5126, ARRAY_BUFFER),
                    "TEXCOORD_0": bb.add(u, "VEC2", 5126, ARRAY_BUFFER),
                },
                "indices": bb.add(i, "SCALAR", 5125, ELEMENT_ARRAY_BUFFER),
                "material": mi,
            }]})
            out_nodes.append({"mesh": len(out_meshes) - 1, "name": name})
            print(f"  {name:8} {w:3}x{h:<3} {len(occupied):6} voxels {len(i)//3:6} tris {len(p):6} verts")

    root_index = len(out_nodes)
    out_nodes.append({
        "name": "rtgl1_main_root",
        "children": list(range(root_index)),
        "rotation": [0, -0.7071068286895752, -0.7071068286895752, 0],
    })

    out = {
        "asset": {"generator": "Doom64-RT tools/gen_d64_psprite.py", "version": "2.0"},
        "scene": 0,
        "scenes": [{"name": "Scene", "nodes": [root_index]}],
        "nodes": out_nodes,
        "meshes": out_meshes,
        "materials": materials,
        "textures": textures,
        "images": images,
        "samplers": [{"magFilter": 9728, "minFilter": 9728}],
        "accessors": bb.accessors,
        "bufferViews": bb.views,
        "buffers": [{"byteLength": len(bb.blob), "uri": None}],
    }

    print(f"\n{len(out_meshes)} frames, {total_verts:,} verts, {len(bb.blob)/1e6:.1f} MB")
    for set_name in args.out_set:
        out["buffers"][0]["uri"] = f"{set_name}.bin"
        for dest in args.replace_dir:
            os.makedirs(f"{dest}/ext", exist_ok=True)
            with open(f"{dest}/{set_name}.gltf", "w", encoding="utf-8") as f:
                json.dump(out, f)
            with open(f"{dest}/{set_name}.bin", "wb") as f:
                f.write(bb.blob)
            for tex, img in tex_files.items():
                img.save(f"{dest}/ext/{tex}")
            print(f"wrote {dest}/{set_name}.gltf")


if __name__ == "__main__":
    main()
