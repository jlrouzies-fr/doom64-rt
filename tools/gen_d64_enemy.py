"""Height-correct and re-shade stock enemy replacement models for Doom 64.

Replaces the earlier POSS-only script. Two fixes, both offline:

  1. Height. The stock models were built to the DOOM II sprites (1px = 1 map
     unit). Doom 64 redrew every sprite larger at the same mapping, so each model
     is ~30-45% too short. The per-sprite ratio is derived here from the actual
     D64 sprite in the WAD rather than hardcoded.

  2. Normals. Stock enemy meshes are 100% axis-aligned, which is what makes them
     read as stacks of cubes. rt_voxel.shade_normal applies the Duke-RT 0.4.2
     neighbour-occupancy rule, constrained to each face's hemisphere.

This does NOT change the SHAPE -- the model stays the DOOM II one. Making an
enemy actually D64-shaped needs a reconstruction from the 8 rotation sprites,
which is a separate job.

Writes new sets rather than editing stock files; delete the output to revert.
Pass --out-set twice to publish the same content under two names: RTGL1 keeps
the first-read entry per mesh name and the log never says which file won, so
covering both ends of the sort order removes the guesswork.
"""

import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt_voxel as rv

STOCK_SET = "set_5_doom1a"
STRENGTH = 1.0  # how far the occupancy gradient may tilt a face normal

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


def d64_sprite_height(wad_path, sprite):
    """Pixel height of a sprite's A frame in the WAD -- the target model height."""
    with open(wad_path, "rb") as f:
        data = f.read()
    _, count, dirofs = struct.unpack_from("<4sii", data, 0)
    for i in range(count):
        ofs, size, name = struct.unpack_from("<ii8s", data, dirofs + i * 16)
        name = name.rstrip(b"\x00").decode("latin1")
        if name in (sprite + "A1", sprite + "A0"):
            blob = data[ofs : ofs + size]
            if blob[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack_from(">II", blob, 16)[1]
    return None


def rebake(doc, buf, prim, scale):
    """Welded positions/normals/uvs/indices for one primitive, re-shaded and scaled.

    Welding on (position, normal, uv) is effectively free here: the normal now
    belongs to the VOXEL rather than the face, and the uv is per-voxel too, so a
    voxel's 24 face-corners collapse to 8 distinct vertices. That lands below the
    stock vertex count even after re-shading, which matters because all
    replacements share one arena (replacementsMaxVertexCount, 32M in rt_main.cpp).
    """
    pos = rv.read_accessor(doc, buf, prim["attributes"]["POSITION"])
    uv = rv.read_accessor(doc, buf, prim["attributes"]["TEXCOORD_0"])
    idx = rv.read_indices(doc, buf, prim)

    tris = [idx[i : i + 3] for i in range(0, len(idx), 3)]
    tri_voxel = [rv.voxel_of_face(pos, t) for t in tris]
    occupied = rv.fill_interior({v for v in tri_voxel if v is not None})
    gradient = rv.occupancy_normals(occupied, {v for v in tri_voxel if v is not None})

    out_pos, out_nrm, out_uv, out_idx = [], [], [], []
    lookup = {}
    unchanged = 0
    for tri, voxel in zip(tris, tri_voxel):
        face = rv._dominant_axis_unit(
            rv._tri_normal(pos[tri[0]], pos[tri[1]], pos[tri[2]])
        ) or (0.0, 0.0, 1.0)
        n = rv.shade_normal(gradient.get(voxel) if voxel else None, face, STRENGTH)
        if n == face:
            unchanged += 1
        for corner in tri:
            p = pos[corner]
            key = (
                round(p[0] * scale, 6),
                round(p[1] * scale, 6),
                round(p[2] * scale, 6),
                round(n[0], 4),
                round(n[1], 4),
                round(n[2], 4),
                round(uv[corner][0], 6),
                round(uv[corner][1], 6),
            )
            j = lookup.get(key)
            if j is None:
                j = len(out_pos)
                lookup[key] = j
                out_pos.append(key[0:3])
                out_nrm.append(n)
                out_uv.append(uv[corner])
            out_idx.append(j)
    return out_pos, out_nrm, out_uv, out_idx, unchanged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wad", required=True)
    ap.add_argument("--sprite", action="append", required=True, help="e.g. POSS; repeatable")
    ap.add_argument(
        "--out-set",
        action="append",
        required=True,
        help="output set name; repeat to publish the same content under two names",
    )
    ap.add_argument("--replace-dir", action="append", required=True)
    args = ap.parse_args()

    src_dir = args.replace_dir[0]
    doc, buf = rv.load(f"{src_dir}/{STOCK_SET}.gltf")

    bb = rv.BufferBuilder()
    out_meshes, out_nodes = [], []
    used_materials = {}
    stock_verts = new_verts = 0

    for sprite in args.sprite:
        frames = [
            n for n in doc["nodes"] if n.get("name", "").startswith(sprite)
        ]
        if not frames:
            sys.exit(f"no {sprite}* nodes in {STOCK_SET}.gltf")

        a0 = doc["accessors"][
            doc["meshes"][frames[0]["mesh"]]["primitives"][0]["attributes"]["POSITION"]
        ]
        stock_h = (a0["max"][2] - a0["min"][2]) * rv.UNITS_PER_METRE
        d64_h = d64_sprite_height(args.wad, sprite)
        if not d64_h:
            sys.exit(f"no {sprite}A1/{sprite}A0 PNG sprite in the WAD")
        scale = d64_h / stock_h
        print(
            f"{sprite}: stock {stock_h:.1f} u -> D64 sprite {d64_h} px  scale {scale:.4f}"
            f"  ({len(frames)} frames)"
        )

        for node in frames:
            src_mesh = doc["meshes"][node["mesh"]]
            prims = []
            for prim in src_mesh["primitives"]:
                stock_verts += doc["accessors"][prim["attributes"]["POSITION"]]["count"]
                p, nn, uu, ii, _ = rebake(doc, buf, prim, scale)
                new_verts += len(p)

                src_mat = prim.get("material")
                if src_mat is not None and src_mat not in used_materials:
                    used_materials[src_mat] = len(used_materials)

                np_ = {
                    "attributes": {
                        "POSITION": bb.add(p, "VEC3", 5126, ARRAY_BUFFER, minmax=True),
                        "NORMAL": bb.add(nn, "VEC3", 5126, ARRAY_BUFFER),
                        "TEXCOORD_0": bb.add(uu, "VEC2", 5126, ARRAY_BUFFER),
                    },
                    "indices": bb.add(ii, "SCALAR", 5125, ELEMENT_ARRAY_BUFFER),
                }
                if src_mat is not None:
                    np_["material"] = used_materials[src_mat]
                prims.append(np_)

            out_meshes.append({"name": src_mesh["name"], "primitives": prims})
            out_nodes.append({"mesh": len(out_meshes) - 1, "name": node["name"]})

    # Carry over only the materials/textures/images actually referenced.
    mat_list, tex_remap, img_remap = [], {}, {}
    out_textures, out_images = [], []
    for src_idx in sorted(used_materials, key=lambda k: used_materials[k]):
        mat = json.loads(json.dumps(doc["materials"][src_idx]))

        def fix(ref):
            if not ref or "index" not in ref:
                return
            t = ref["index"]
            if t not in tex_remap:
                src_tex = doc["textures"][t]
                s = src_tex["source"]
                if s not in img_remap:
                    img_remap[s] = len(out_images)
                    out_images.append(doc["images"][s])
                nt = dict(src_tex)
                nt["source"] = img_remap[s]
                tex_remap[t] = len(out_textures)
                out_textures.append(nt)
            ref["index"] = tex_remap[t]

        pbr = mat.get("pbrMetallicRoughness", {})
        fix(pbr.get("baseColorTexture"))
        fix(pbr.get("metallicRoughnessTexture"))
        fix(mat.get("normalTexture"))
        fix(mat.get("emissiveTexture"))
        fix(mat.get("occlusionTexture"))
        mat_list.append(mat)

    root_index = len(out_nodes)
    out_nodes.append(
        {
            "name": "rtgl1_main_root",
            "children": list(range(root_index)),
            "rotation": [0, -0.7071068286895752, -0.7071068286895752, 0],
        }
    )

    print(
        f"\n{len(out_meshes)} frames, verts {stock_verts:,} -> {new_verts:,} "
        f"({new_verts / max(stock_verts, 1):.2f}x after welding), {len(bb.blob) / 1e6:.1f} MB"
    )

    for set_name in args.out_set:
        out = {
            "asset": {"generator": "Doom64-RT tools/gen_d64_enemy.py", "version": "2.0"},
            "scene": 0,
            "scenes": [{"name": "Scene", "nodes": [root_index]}],
            "nodes": out_nodes,
            "meshes": out_meshes,
            "materials": mat_list,
            "accessors": bb.accessors,
            "bufferViews": bb.views,
            "buffers": [{"byteLength": len(bb.blob), "uri": f"{set_name}.bin"}],
        }
        if out_textures:
            out["textures"] = out_textures
            out["images"] = out_images
            out["samplers"] = doc.get("samplers", [])
        for dest in args.replace_dir:
            with open(f"{dest}/{set_name}.gltf", "w", encoding="utf-8") as f:
                json.dump(out, f)
            with open(f"{dest}/{set_name}.bin", "wb") as f:
                f.write(bb.blob)
            print(f"wrote {dest}/{set_name}.gltf")


if __name__ == "__main__":
    main()
