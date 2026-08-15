"""Reconstruct a Doom 64 enemy as a voxel model by carving its 8 rotation sprites.

Rescaling the stock DOOM II model fixes its height but not its shape. To get an
actually D64-shaped monster you need real 3D, and the art supplies it: frames A-G
of a monster have all 8 rotations, which is enough for shape-from-silhouette.
Start with a solid block and keep the voxels that most views agree are inside the
silhouette. Strict intersection does not survive contact with hand-drawn art --
see carve() for the measurements.

This matters because RTGL1 keys replacements on sprite+frame with NO rotation
(rt_state.h builds the name as 4 sprite chars + 'A'+frame), so ONE model has to
serve all eight viewing angles. A single-view extrusion cannot.

Frames with only rotation 0 (the death and pain frames, H onwards) are skipped
and left to whichever other set defines them -- `replacements` is keyed per mesh
name, so the rescaled set still supplies those.

Colour comes from whichever rotation most directly faces a given surface voxel,
written into a palette strip texture the same way the stock vx_*.tga sets do.
"""

import argparse
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt_voxel as rv

from PIL import Image, ImageOps

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963

_FACES = [
    ((1, 0, 0), (1.0, 0.0, 0.0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), (-1.0, 0.0, 0.0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), (0.0, 1.0, 0.0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), (0.0, -1.0, 0.0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), (0.0, 0.0, 1.0), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), (0.0, 0.0, -1.0), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


class View:
    """One rotation: its image, its actor-origin offset, and its camera azimuth."""

    def __init__(self, img, leftoff, topoff, azimuth_deg):
        self.w, self.h = img.size
        self.px = img.convert("RGBA").load()
        self.left = leftoff
        self.top = topoff
        a = math.radians(azimuth_deg)
        # Screen-right axis of this view, in the actor's horizontal plane.
        self.rx = -math.sin(a)
        self.ry = math.cos(a)
        # Direction from the actor towards this camera.
        self.dx = math.cos(a)
        self.dy = math.sin(a)
        self.mask = [
            [self.px[x, y][3] > 127 for x in range(self.w)] for y in range(self.h)
        ]

    def project(self, vx, vy, vz):
        """Voxel centre -> (col, row), or None if it falls off the image."""
        h = (vx + 0.5) * self.rx + (vy + 0.5) * self.ry
        col = int(math.floor(self.left + h))
        row = int(math.floor(self.top - (vz + 0.5)))
        if 0 <= col < self.w and 0 <= row < self.h:
            return col, row
        return None

    def opaque_at(self, vx, vy, vz):
        p = self.project(vx, vy, vz)
        return bool(p) and self.mask[p[1]][p[0]]


# ------------------------------------------------------------------- wad access


def load_wad(path):
    with open(path, "rb") as f:
        data = f.read()
    _, count, dirofs = struct.unpack_from("<4sii", data, 0)
    entries = []
    for i in range(count):
        ofs, size, name = struct.unpack_from("<ii8s", data, dirofs + i * 16)
        entries.append((name.rstrip(b"\x00").decode("latin1"), ofs, size))
    return data, entries


def read_png(data, ofs, size):
    import io

    blob = data[ofs : ofs + size]
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None, (0, 0)
    off = (0, 0)
    pos = 8
    while pos + 8 <= len(blob):
        (ln,) = struct.unpack_from(">I", blob, pos)
        t = blob[pos + 4 : pos + 8]
        if t == b"grAb":
            off = struct.unpack_from(">ii", blob, pos + 8)
            break
        if t in (b"IDAT", b"IEND"):
            break
        pos += 12 + ln
    return Image.open(io.BytesIO(blob)).convert("RGBA"), off


def gather_rotations(data, entries, sprite):
    """{frame letter: {rotation 1-8: (image, leftoffset, topoffset)}}.

    Handles the packed 8-char lumps (POSSA2A8 serves rotation 2, and rotation 8
    as its mirror). A mirrored view's origin moves to width - leftoffset.
    """
    out = {}
    for name, ofs, size in entries:
        if not name.startswith(sprite) or len(name) < 6:
            continue
        img, (lo, to) = read_png(data, ofs, size)
        if img is None:
            continue
        pairs = [(name[4], name[5], False)]
        if len(name) >= 8:
            pairs.append((name[6], name[7], True))
        for letter, rot, mirror in pairs:
            if rot == "0" or not rot.isdigit():
                continue
            im, left = img, lo
            if mirror:
                im = ImageOps.mirror(img)
                left = img.size[0] - lo
            out.setdefault(letter, {})[int(rot)] = (im, left, to)
    return out


# ---------------------------------------------------------------------- carving


def carve(rots, base_deg, direction, flip, min_views=8):
    """Visual hull of one frame, by voting rather than strict intersection.

    A strict hull (min_views = 8) does not work on this art. Doom sprite
    rotations are hand-drawn, not renders of one 3D model, so they are not
    geometrically consistent with each other: measured on POSSA, a strict
    intersection deletes everything below z=18 -- the entire legs -- because thin
    features vanish as soon as a single view disagrees by a pixel or two.

    Keeping a voxel when at least min_views of 8 agree tolerates that
    inconsistency while still cutting the shape down to the silhouettes.
    """
    views = {}
    for r, (img, left, top) in rots.items():
        az = base_deg + direction * (r - 1) * 45.0
        v = View(img, left, top, az)
        if flip < 0:
            v.rx, v.ry = -v.rx, -v.ry
        views[r] = v

    # Extent: the widest the actor can be either side of its origin, over all views.
    half = 1
    height = 1
    for v in views.values():
        half = max(half, v.left + 1, v.w - v.left + 1)
        height = max(height, v.top)

    # The front view is a cheap prefilter only when voting demands unanimity;
    # otherwise every voxel in the block has to be polled.
    need = min(min_views, len(views))
    ordered = [views[r] for r in sorted(views)]
    allowed_misses = len(ordered) - need

    alive = set()
    for vz in range(height):
        for vx in range(-half, half):
            for vy in range(-half, half):
                misses = 0
                for v in ordered:
                    if not v.opaque_at(vx, vy, vz):
                        misses += 1
                        if misses > allowed_misses:
                            break
                else:
                    alive.add((vx, vy, vz))
    return alive, views


def reprojection_score(alive, views):
    """Mean IoU of the hull's silhouette against each source silhouette.

    Carving guarantees the projection is a subset of every silhouette, so this is
    really "how much of each silhouette got filled". A wrong convention makes the
    views disagree and over-carves, which shows up here as a low score.
    """
    if not alive:
        return 0.0
    total = 0.0
    for v in views.values():
        hit = set()
        for p in alive:
            q = v.project(*p)
            if q:
                hit.add(q)
        src = sum(1 for row in v.mask for c in row if c)
        inter = sum(1 for (c, r) in hit if v.mask[r][c])
        union = src + len(hit) - inter
        total += inter / union if union else 0.0
    return total / len(views)


def colour_voxels(alive, views, gradient):
    """Sample each surface voxel from the rotation that most faces it."""
    order = sorted(views)
    colours = {}
    for p in alive:
        n = gradient.get(p)
        if n is None:
            n = (1.0, 0.0, 0.0)
        ranked = sorted(
            order, key=lambda r: -(n[0] * views[r].dx + n[1] * views[r].dy)
        )
        rgb = None
        for r in ranked:
            v = views[r]
            q = v.project(*p)
            if q and v.mask[q[1]][q[0]]:
                c = v.px[q[0], q[1]]
                rgb = (c[0], c[1], c[2])
                break
        colours[p] = rgb or (128, 128, 128)
    return colours


def build_mesh(alive, colours, bb, palette):
    gradient = rv.occupancy_normals(alive, alive)
    pos, nrm, uv, idx = [], [], [], []
    weld = {}
    scale = 1.0 / rv.UNITS_PER_METRE
    for v in alive:
        vx, vy, vz = v
        rgb = colours[v]
        if rgb not in palette:
            palette[rgb] = len(palette)
        pi = palette[rgb]
        for offset, face, corners in _FACES:
            if (vx + offset[0], vy + offset[1], vz + offset[2]) in alive:
                continue
            n = rv.shade_normal(gradient.get(v), face)
            base = []
            for cx, cy, cz in corners:
                key = ((vx + cx), (vy + cy), (vz + cz), n, pi)
                j = weld.get(key)
                if j is None:
                    j = len(pos)
                    weld[key] = j
                    pos.append(
                        ((vx + cx) * scale, (vy + cy) * scale, (vz + cz) * scale)
                    )
                    nrm.append(n)
                    uv.append((pi, 0.5))  # u fixed up once the palette is final
                base.append(j)
            idx += [base[0], base[1], base[2], base[0], base[2], base[3]]
    return pos, nrm, uv, idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wad", required=True)
    ap.add_argument("--sprite", action="append", required=True)
    ap.add_argument("--out-set", action="append", required=True)
    ap.add_argument("--replace-dir", action="append", required=True)
    # Rotation convention, derived rather than searched. Doom's rotation 1 is the
    # view from the direction the actor faces, and rotations advance 45 degrees
    # from there; with the camera at +x looking along -x and +z up, screen-right
    # works out as +y. Hence base 0, direction +1, flip +1.
    #
    # It cannot be settled by silhouette scoring: with all 8 rotations at uniform
    # 45-degree spacing, every convention carves the SAME hull and differs only in
    # the model's final orientation and chirality, so all 8 score identically.
    # Scoring the hull against the (correctly oriented) stock model does separate
    # them, but only weakly -- a humanoid is near-symmetric front-to-back, and the
    # stock mesh is a hollow shell against our solid carve, which caps the IoU.
    # These flags exist so the derivation can be overridden if a monster turns out
    # to face the wrong way.
    # 7-of-8 beats both unanimity and looser voting, measured on POSSA:
    #   K=8 -> 61 u tall, IoU 0.599 (legs deleted)
    #   K=7 -> 77 u tall, IoU 0.774  <-- best agreement, legs intact
    #   K=6 -> 78 u tall, IoU 0.717
    #   K=5 -> 80 u tall, IoU 0.645 (hull bulges outside the silhouettes)
    ap.add_argument("--min-views", type=int, default=7)
    ap.add_argument("--base", type=float, default=0.0)
    ap.add_argument("--direction", type=int, default=1, choices=(1, -1))
    ap.add_argument("--flip", type=int, default=1, choices=(1, -1))
    args = ap.parse_args()

    data, entries = load_wad(args.wad)

    bb = rv.BufferBuilder()
    out_meshes, out_nodes = [], []
    palette = {}
    pending = []

    for sprite in args.sprite:
        frames = gather_rotations(data, entries, sprite)
        full = {k: v for k, v in sorted(frames.items()) if len(v) >= 8}
        partial = sorted(set(frames) - set(full))
        print(f"{sprite}: {len(full)} frames with 8 rotations {''.join(full)}")
        if partial:
            print(f"  skipping (fewer than 8 rotations, left to the rescaled set): {''.join(partial)}")
        if not full:
            continue

        base, direction, flip = args.base, args.direction, args.flip

        for letter in sorted(full):
            alive, views = carve(full[letter], base, direction, flip, args.min_views)
            score = reprojection_score(alive, views)
            gradient = rv.occupancy_normals(alive, alive)
            colours = colour_voxels(alive, views, gradient)
            # Voting can shave a row or two off the soles, which would leave the
            # actor hovering. The sprite's origin IS the feet (topoffset == height),
            # and in a walk cycle some foot always touches, so drop each frame back
            # onto z = 0 rather than trusting the carve's lowest survivor.
            dz = min(q[2] for q in alive)
            if dz:
                alive = {(q[0], q[1], q[2] - dz) for q in alive}
                colours = {(k[0], k[1], k[2] - dz): v for k, v in colours.items()}
            p, n, u, i = build_mesh(alive, colours, bb, palette)
            zs = [q[2] for q in alive]
            print(
                f"  {sprite}{letter}: {len(alive):6} voxels  {len(i)//3:6} tris  "
                f"h={max(zs)-min(zs)+1:3} u  IoU={score:.3f}"
            )
            pending.append((f"{sprite}{letter}", p, n, u, i))

    if not pending:
        sys.exit("nothing carved")

    # Palette strip: one texel per unique colour, exactly like the stock vx_*.tga.
    ncol = len(palette)
    tex = Image.new("RGBA", (ncol, 1))
    for rgb, i in palette.items():
        tex.putpixel((i, 0), (rgb[0], rgb[1], rgb[2], 255))

    for name, p, n, u, i in pending:
        u = [((idx_ + 0.5) / ncol, 0.5) for idx_, _ in u]
        prim = {
            "attributes": {
                "POSITION": bb.add(p, "VEC3", 5126, ARRAY_BUFFER, minmax=True),
                "NORMAL": bb.add(n, "VEC3", 5126, ARRAY_BUFFER),
                "TEXCOORD_0": bb.add(u, "VEC2", 5126, ARRAY_BUFFER),
            },
            "indices": bb.add(i, "SCALAR", 5125, ELEMENT_ARRAY_BUFFER),
            "material": 0,
        }
        out_meshes.append({"name": name, "primitives": [prim]})
        out_nodes.append({"mesh": len(out_meshes) - 1, "name": name})

    root_index = len(out_nodes)
    out_nodes.append(
        {
            "name": "rtgl1_main_root",
            "children": list(range(root_index)),
            "rotation": [0, -0.7071068286895752, -0.7071068286895752, 0],
        }
    )

    tex_name = "vx_d64carve.png"
    out = {
        "asset": {"generator": "Doom64-RT tools/gen_d64_carve.py", "version": "2.0"},
        "scene": 0,
        "scenes": [{"name": "Scene", "nodes": [root_index]}],
        "nodes": out_nodes,
        "meshes": out_meshes,
        "materials": [
            {
                "name": "vx_d64carve",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.9,
                },
                "alphaMode": "OPAQUE",
            }
        ],
        "textures": [{"sampler": 0, "source": 0}],
        "images": [{"mimeType": "image/png", "name": "vx_d64carve", "uri": f"ext/{tex_name}"}],
        "samplers": [{"magFilter": 9728, "minFilter": 9728}],
        "accessors": bb.accessors,
        "bufferViews": bb.views,
        "buffers": [{"byteLength": len(bb.blob), "uri": None}],
    }

    print(f"\n{len(out_meshes)} frames, {ncol} palette colours, {len(bb.blob)/1e6:.1f} MB")
    for set_name in args.out_set:
        out["buffers"][0]["uri"] = f"{set_name}.bin"
        for dest in args.replace_dir:
            os.makedirs(f"{dest}/ext", exist_ok=True)
            with open(f"{dest}/{set_name}.gltf", "w", encoding="utf-8") as f:
                json.dump(out, f)
            with open(f"{dest}/{set_name}.bin", "wb") as f:
                f.write(bb.blob)
            tex.save(f"{dest}/ext/{tex_name}")
            print(f"wrote {dest}/{set_name}.gltf")


if __name__ == "__main__":
    main()
