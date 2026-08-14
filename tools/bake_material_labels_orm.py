"""Bake hand-labelled metallic/roughness into the authored _orm.png maps.

`metallicDefault` / `roughnessDefault` in textures.json are only read when a
texture has NO occlusion-roughness-metallic map:

    HitInfo.inl:529
        if( tr.occlusionRougnessMetallicTexture != MATERIAL_NO_TEXTURE ) {
            h.roughness = orm[1];      // the map wins outright
            h.metallic  = orm[2];
        } else {
            h.roughness = tr.roughnessDefault;
            h.metallic  = tr.metallicDefault;
        }

Every texture this project authored has an _orm map, so labels written only to
textures.json are inert. This writes them where the renderer actually looks.

ORM channel layout: R = occlusion (preserved), G = roughness, B = metallic.

    python tools/bake_material_labels_orm.py tools/_material_labels/map01.json --dry-run
    python tools/bake_material_labels_orm.py tools/_material_labels/map01.json
    python tools/bake_material_labels_orm.py --revert

Materials live in FOUR directories and all four are written: the engine build
tree is what runs, and the Retribution-RT-Materials copy is what survives the
next build restaging over it.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]

MAT_DIRS = [
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat_dev",
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat_dev",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat",
]

BACKUP = ".pre_material_labels"


def load_labels(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("__")}


def bake_one(png: Path, metal: float, rough: float, keep_variation: bool, dry: bool):
    im = Image.open(png)
    had_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
    im = im.convert("RGBA" if had_alpha else "RGB")
    px = im.load()
    w, h = im.size

    g_target = max(0, min(255, round(rough * 255)))
    b_target = max(0, min(255, round(metal * 255)))

    if keep_variation:
        tot = 0
        for y in range(h):
            for x in range(w):
                tot += px[x, y][1]
        mean = tot / (w * h)
        shift = g_target - mean
    else:
        shift = None

    before = px[0, 0]
    if not dry:
        for y in range(h):
            for x in range(w):
                p = px[x, y]
                g = g_target if shift is None else max(0, min(255, round(p[1] + shift)))
                if had_alpha:
                    px[x, y] = (p[0], g, b_target, p[3])
                else:
                    px[x, y] = (p[0], g, b_target)

        backup = png.with_suffix(png.suffix + BACKUP)
        if not backup.exists():
            shutil.copy2(png, backup)
        im.save(png)

    return before, (before[0], g_target, b_target)


def revert():
    n = 0
    for d in MAT_DIRS:
        if not d.exists():
            continue
        for b in d.glob("*_orm.png" + BACKUP):
            shutil.copy2(b, b.with_suffix(""))
            n += 1
    print("restored %d files from backups" % n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--keep-variation", action="store_true",
                    help="shift the existing roughness pattern to the target mean "
                         "instead of flattening it")
    args = ap.parse_args()

    if args.revert:
        revert()
        return
    if not args.labels:
        ap.error("give a labels file, or --revert")

    labels = load_labels(Path(args.labels))
    print("%d labels from %s\n" % (len(labels), args.labels))

    written = 0
    no_orm = []
    for name, vals in sorted(labels.items()):
        metal = float(vals.get("metallicDefault", 0.0))
        rough = float(vals.get("roughnessDefault", 1.0))
        found = False
        for d in MAT_DIRS:
            png = d / (name + "_orm.png")
            if not png.exists():
                continue
            found = True
            before, after = bake_one(png, metal, rough, args.keep_variation, args.dry_run)
            written += 1
        if not found:
            no_orm.append(name)

    print("  %d _orm.png files %s across %d dirs"
          % (written, "would be written" if args.dry_run else "written", len(MAT_DIRS)))
    if no_orm:
        print("  %d labelled textures have NO _orm map, so textures.json"
              " metallicDefault/roughnessDefault covers them:" % len(no_orm))
        print("     " + ", ".join(no_orm[:12]) + (" ..." if len(no_orm) > 12 else ""))

    if args.dry_run:
        print("\ndry run - nothing written")
    else:
        print("\nBackups kept as *_orm.png%s (restore with --revert)." % BACKUP)
        print("No rebuild needed - developerMode reads these PNGs. Relaunch the game.")


if __name__ == "__main__":
    main()
