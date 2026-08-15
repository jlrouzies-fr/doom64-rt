"""Bake the sprite labelling page's export into per-frame _orm.png maps.

The wall/flat pipeline writes ONE metallic and ONE roughness per texture, into
textures.json (tools/apply_material_labels.py) and into a flat _orm
(tools/bake_material_labels_orm.py). A sprite cannot be answered that way: a
shotgun is a metal receiver, a wooden stock and two hands in the same image. So
this writes a PER-TEXEL map instead, and there is no textures.json half at all --
a scalar would be wrong for every sprite this tool exists for.

Input is the export from tools/gen_sprite_material_labeller.py, which carries the
cluster CENTROIDS as RGB. Pixels are assigned here by nearest centroid rather
than by re-running the generator's median-cut: quantisation is not reproducible
across Pillow versions, and a baker that silently disagrees with the page the
human labelled in is the worst possible failure.

ORM channel layout, as everywhere else in this project:
    R = ambient occlusion   G = roughness   B = metallic

R IS PRESERVED where an _orm already exists. Sprite AO is authored by other
tools and this one has no opinion about it.

THE ALBEDO IS NEVER REWRITTEN. Sprite PNGs carry grAb offset chunks and Pillow
drops them -- a regenerated sprite renders sunk into the floor, or misplaced on
screen for a viewmodel. Only _orm companions are written, and those carry no
offsets.

Usage:
    python tools\\bake_sprite_materials.py <export.json> [--dry-run]
    python tools\\bake_sprite_materials.py --revert
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import re
import struct
import sys
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parent.parent
WAD = PROJ_ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"

# The same four, in the same order, as bake_material_labels_orm.py. Editing
# fewer than all of them makes the change a ghost: developerMode reads mat_dev
# and the build resyncs it.
MAT_DIRS = [
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat_dev",
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat_dev",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat",
]

BACKUP_SUFFIX = ".pre_sprite_materials"

NAME_RE = re.compile(r"^([A-Z0-9]{4})([A-Z\[\\\]])([0-8])(?:([A-Z\[\\\]])([0-8]))?$")

# Applied to any pixel whose cluster the human never called. Deliberately a
# dielectric at the game's common roughness: an unlabelled cluster must never
# turn into metal by accident, because a wrongly-metal surface in a dark room
# goes black and reads as a rendering bug rather than a labelling gap.
UNLABELLED_METALLIC = 0.0
UNLABELLED_ROUGHNESS = 0.80


def read_lumps(data: bytes):
    n, o = struct.unpack_from("<II", data, 4)
    out = []
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", data, o + i * 16)
        out.append((name.split(b"\0")[0].decode("ascii", "replace"), off, sz))
    return out


def sprite_images(codes: set[str]) -> dict[str, Image.Image]:
    """Every stored frame of the wanted codes, by lump name.

    Mirrored rotations are not here and must not be: the WAD stores one image
    for e.g. rotations 2 and 8, and the engine flips it at draw time -- it will
    flip the _orm with it."""
    data = WAD.read_bytes()
    lumps = read_lumps(data)
    names = [nm for nm, _, _ in lumps]
    s0, s1 = names.index("SS_START"), names.index("SS_END")
    out = {}
    for nm, off, sz in lumps[s0 + 1 : s1]:
        if sz == 0:
            continue
        m = NAME_RE.match(nm)
        if not m or m.group(1) not in codes:
            continue
        raw = data[off : off + sz]
        if not raw.startswith(b"\x89PNG"):
            continue  # column-post effect sprites: no material work wanted
        try:
            out[nm] = Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            pass
    return out


def smooth_values(vals: list[float], mask: list[bool], w: int, h: int,
                  radius: int) -> list[float]:
    """Average a material channel over its neighbourhood, opaque pixels only.

    THE DITHER PROBLEM. Doom 64 sprites fake gradients by dithering -- adjacent
    pixels alternate between two colours. Those two colours land in different
    clusters, so when the human calls them differently (leather 0.70 beside
    flesh 0.60) the material map comes out as a CHECKERBOARD at dither
    frequency, and under specular light the sprite reads as a mosaic of beige
    and dark blocks. Measured on POSSA1 before this existed: 25.4% of
    neighbouring pixels carried a different material.

    A MODE FILTER CANNOT FIX THIS AND WAS TRIED FIRST. A checkerboard is
    majority-stable: in any odd window the centre's own colour is already the
    plurality, so the pattern survives every pass. It took 25.4% only to 13.6%.

    Averaging does fix it, because roughness is a CONTINUOUS quantity: the mean
    of a 0.60/0.70 checkerboard is a flat 0.65, which is the material the art
    was dithering toward in the first place. Real part boundaries -- a barrel
    against a hand -- are many pixels wide, so they survive as a one-pixel ramp
    instead of a hard edge, which is what a renderer wants anyway."""
    if radius <= 0:
        return vals
    out = list(vals)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if not mask[i]:
                continue
            acc = n = 0.0
            for dy in range(-radius, radius + 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                for dx in range(-radius, radius + 1):
                    xx = x + dx
                    if xx < 0 or xx >= w:
                        continue
                    j = yy * w + xx
                    if mask[j]:
                        acc += vals[j]
                        n += 1.0
            if n:
                out[i] = acc / n
    return out


def nearest(rgb, centroids):
    best, bd = -1, 1 << 30
    for i, c in enumerate(centroids):
        if c is None:
            continue
        d = (rgb[0] - c[0]) ** 2 + (rgb[1] - c[1]) ** 2 + (rgb[2] - c[2]) ** 2
        if d < bd:
            best, bd = i, d
    return best


def existing_ao(lump: str, size) -> Image.Image | None:
    for d in MAT_DIRS:
        p = d / f"{lump}_orm.png"
        if p.exists():
            try:
                im = Image.open(p).convert("RGB")
                if im.size == size:
                    return im
            except Exception:
                pass
    return None


def parse_overrides(specs: list[str]) -> dict[str, dict[str, float]]:
    """--rough leather=0.75 --metal leather=0

    RETUNING WITHOUT RE-LABELLING. A class's roughness is stored per cluster at
    the moment it is called, so changing the default in the page's SURFACES
    table does nothing to work already done -- and "leather reads flat" is a
    judgement made in game, long after the calling. This lets the whole class
    move in one pass, so a look can be A/B'd in seconds instead of re-called
    across five pages."""
    out: dict[str, dict[str, float]] = {}
    for kind, items in specs:
        for spec in items:
            name, _, val = spec.partition("=")
            if not val:
                sys.exit(f"--{kind} wants CLASS=VALUE, got {spec!r}")
            out.setdefault(name.strip().lower(), {})[kind] = float(val)
    return out


def bake(export_paths: list[Path], dry_run: bool,
         overrides: dict[str, dict[str, float]] | None = None,
         smooth: int = 1) -> int:
    overrides = overrides or {}
    # SEVERAL EXPORTS, ONE BAKE. There is a page per sprite section -- weapons,
    # monsters, projectiles, scenery -- and they are labelled at different
    # times, so applying one must not look like a reason to un-apply the rest.
    # Merging here rather than making the human paste four files into one keeps
    # each section's export the thing the page actually produced.
    codes: dict[str, dict] = {}
    for p in export_paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        got = doc.get("codes") or {}
        if not got:
            print(f"  {p.name}: no 'codes' -- did you press 'copy JSON'? skipped")
            continue
        clash = set(got) & set(codes)
        if clash:
            print(f"  {p.name}: {len(clash)} code(s) already given by an earlier "
                  f"file, later wins: {', '.join(sorted(clash)[:4])}")
        codes.update(got)
        print(f"  {p.name}: {len(got)} code(s)")
    if not codes:
        sys.exit("nothing to bake")

    images = sprite_images(set(codes))
    written = 0
    unlabelled_hits = 0

    for code, entry in sorted(codes.items()):
        clusters = entry.get("clusters") or []
        # EVERY centroid, called or not. A pixel belongs to whichever cluster
        # the page put it in; whether the human got round to calling that
        # cluster changes what it BAKES AS, never which cluster it is. Matching
        # against called centroids only is what made a half-finished sprite
        # bake wrong instead of merely incomplete -- skin snapping to the
        # barrel because the barrel was the only thing named.
        # (`None` survives only for exports written before this shape.)
        centroids = [(c or {}).get("rgb") for c in clusters]
        if not any(c and c.get("surface") for c in clusters):
            continue

        frames = [f for f in entry.get("frames", []) if f in images]
        missing = [f for f in entry.get("frames", []) if f not in images]
        if missing:
            print(f"  {code}: {len(missing)} frame(s) not in the WAD, skipped: "
                  f"{', '.join(missing[:4])}")

        for lump in frames:
            im = images[lump]
            w, h = im.size
            ao = existing_ao(lump, (w, h))
            ao_px = ao.load() if ao else None

            orm = Image.new("RGB", (w, h))
            out = orm.load()
            src = im.load()

            # Pass 1: which cluster each pixel belongs to. Kept as ids so the
            # mode filter can work on identity rather than on the ORM values --
            # averaging roughness across a boundary would invent a material that
            # nobody called.
            idcache: dict[tuple, int] = {}
            ids = [-1] * (w * h)
            for y in range(h):
                for x in range(w):
                    r, g, b, a = src[x, y]
                    if a == 0:
                        continue
                    key = (r, g, b)
                    k = idcache.get(key)
                    if k is None:
                        k = nearest(key, centroids)
                        idcache[key] = k
                    ids[y * w + x] = k

            # Pass 2: ids -> material values, then SMOOTHED before writing.
            valcache: dict[int, tuple] = {}
            rgh_a = [0.0] * (w * h)
            met_a = [0.0] * (w * h)
            mask = [False] * (w * h)
            for i, k in enumerate(ids):
                if k < 0:
                    continue
                hit = valcache.get(k)
                if hit is None:
                    c = clusters[k] if k >= 0 else None
                    if c is None or c.get("surface") is None:
                        met, rgh = UNLABELLED_METALLIC, UNLABELLED_ROUGHNESS
                        unlabelled_hits += 1
                    else:
                        met = float(c.get("metallicDefault", 0.0))
                        rgh = float(c.get("roughnessDefault", 0.8))
                        ov = overrides.get(str(c.get("surface", "")).lower())
                        if ov:
                            met = ov.get("metal", met)
                            rgh = ov.get("rough", rgh)
                            if "roughmin" in ov:
                                rgh = max(rgh, ov["roughmin"])
                    hit = (max(0.0, min(1.0, rgh)), max(0.0, min(1.0, met)))
                    valcache[k] = hit
                rgh_a[i], met_a[i], mask[i] = hit[0], hit[1], True

            rgh_a = smooth_values(rgh_a, mask, w, h, smooth)
            met_a = smooth_values(met_a, mask, w, h, smooth)

            for y in range(h):
                for x in range(w):
                    i = y * w + x
                    if not mask[i]:
                        out[x, y] = (255, 204, 0)
                        continue
                    occ = ao_px[x, y][0] if ao_px else 255
                    out[x, y] = (occ,
                                 int(round(rgh_a[i] * 255)),
                                 int(round(met_a[i] * 255)))

            for d in MAT_DIRS:
                if not d.is_dir():
                    continue
                target = d / f"{lump}_orm.png"
                if dry_run:
                    written += 1
                    continue
                # A ZERO-BYTE BACKUP MEANS "THIS FILE DID NOT EXIST".
                # Backing up only what is overwritten is not enough here and
                # that is not a detail: no weapon sprite has an _orm today, so
                # the first real bake CREATES every file it writes and a revert
                # that only restores overwrites silently leaves all of them
                # behind. The marker is what lets --revert delete them again.
                backup = target.with_suffix(target.suffix + BACKUP_SUFFIX)
                if not backup.exists():
                    backup.write_bytes(target.read_bytes() if target.exists() else b"")
                orm.save(target, "PNG", optimize=True)
                written += 1

        print(f"  {code}: {len(frames)} frame(s), "
              f"{sum(1 for c in clusters if c)} of {len(clusters)} clusters called")

    if unlabelled_hits:
        print(f"\n  NOTE: {unlabelled_hits} colour(s) fell on an uncalled cluster and "
              f"took the dielectric default ({UNLABELLED_ROUGHNESS} rough).")
    verb = "would be written" if dry_run else "written"
    print(f"\n  {written} _orm.png files {verb} across {len(MAT_DIRS)} dirs")
    return 0


def revert() -> int:
    restored = removed = 0
    for d in MAT_DIRS:
        if not d.is_dir():
            continue
        for backup in d.glob(f"*_orm.png{BACKUP_SUFFIX}"):
            target = backup.with_suffix("")
            if backup.stat().st_size == 0:
                # The marker: there was no _orm here before the bake.
                if target.exists():
                    target.unlink()
                    removed += 1
            else:
                target.write_bytes(backup.read_bytes())
                restored += 1
            backup.unlink()
    print(f"  restored {restored} file(s), removed {removed} the bake had created")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", nargs="*",
                    help="JSON export(s) from the labelling pages")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--smooth", type=int, default=1, metavar="RADIUS",
                    help="neighbourhood radius for smoothing the material channels, "
                         "which stops DITHERED art producing a checkerboard "
                         "material map. 0 disables it. Default 1 (a 3x3).")
    ap.add_argument("--rough", action="append", default=[], metavar="CLASS=VALUE",
                    help="override a whole class's roughness, e.g. leather=0.75")
    ap.add_argument("--roughmin", action="append", default=[], metavar="CLASS=VALUE",
                    help="raise a class to at least VALUE, keeping anything already "
                         "rougher. Preferred over --rough for a correction pass: the "
                         "per-cluster variation was deliberate work.")
    ap.add_argument("--metal", action="append", default=[], metavar="CLASS=VALUE",
                    help="override a whole class's metalness")
    args = ap.parse_args()

    if args.revert:
        sys.exit(revert())
    # cmd.exe does not expand wildcards for the callee, so a caller passing
    # sprites_*.json hands us the literal string. Expand it here or the wrapper
    # silently bakes nothing.
    paths: list[Path] = []
    for spec in args.export:
        if any(ch in spec for ch in "*?"):
            # glob.glob, not Path().glob: the wrapper passes an ABSOLUTE
            # pattern and pathlib refuses those outright.
            hits = sorted(Path(p) for p in glob.glob(spec))
            if not hits:
                sys.exit(f"no file matches {spec}")
            paths.extend(hits)
        else:
            paths.append(Path(spec))
    missing = [p for p in paths if not p.is_file()]
    if missing:
        sys.exit("no such file: " + ", ".join(str(p) for p in missing))
    if not paths:
        ap.error("give at least one export JSON, or --revert")
    ov = parse_overrides([("rough", args.rough), ("metal", args.metal),
                          ("roughmin", args.roughmin)])
    for name, vals in sorted(ov.items()):
        print("  override: %s -> %s" % (name, vals))
    sys.exit(bake(paths, args.dry_run, ov, args.smooth))


if __name__ == "__main__":
    main()
