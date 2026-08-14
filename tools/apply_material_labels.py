"""Merge hand-labelled metallic/roughness values into the RT texture metadata.

Input is what the Metal-or-Not labelling page exports (see
`docs/plan-metal-labelling.md`): a flat map of texture name -> the two fields,
plus `__skipped` and `__meta` which are ignored.

    python tools/apply_material_labels.py tools/_material_labels/map01.json
    python tools/apply_material_labels.py <file> --dry-run
    python tools/apply_material_labels.py --revert

Two rules this exists to enforce, both of which have cost this project time:

1. **Write BOTH trees.** RTGL1 reads `rt/data/textures.json` out of the engine
   build directory, which is gitignored; `Retribution-RT-Materials` is the copy
   that is tracked and that `build-gzdoom-rt.cmd` restages from. Writing only the
   first means the change dies at the next build; only the second means the game
   never sees it.
2. **MERGE, never rewrite.** Those entries already carry `emissiveMult`,
   `lightIntensity`, `lightColorHEX`, `isMirror` and friends from the emissive and
   water work. This touches `metallicDefault` and `roughnessDefault` and nothing
   else.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys

PROJ_ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "data" / "textures.json",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "data" / "textures.json",
]

FIELDS = ("metallicDefault", "roughnessDefault")
BACKUP_SUFFIX = ".pre_material_labels"


def load_labels(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for name, val in raw.items():
        if name.startswith("__"):
            continue
        if not isinstance(val, dict):
            sys.exit("label for %s is not an object" % name)
        entry = {}
        for f in FIELDS:
            if f in val:
                entry[f] = float(val[f])
        if entry:
            out[name] = entry
    return out, raw.get("__meta", {})


def apply_to(target: Path, labels, dry_run):
    doc = json.loads(target.read_text(encoding="utf-8"))
    arr = doc["array"]
    by_name = {}
    for e in arr:
        n = e.get("textureName")
        if n is not None:
            by_name.setdefault(n, e)          # first wins, as RTGL1 does

    updated = added = unchanged = 0
    for name, vals in labels.items():
        e = by_name.get(name)
        if e is None:
            e = {"textureName": name}
            e.update(vals)
            arr.append(e)
            by_name[name] = e
            added += 1
            continue
        before = {f: e.get(f) for f in FIELDS}
        e.update(vals)                        # only the two fields; rest untouched
        if before == {f: e.get(f) for f in FIELDS}:
            unchanged += 1
        else:
            updated += 1

    if not dry_run:
        backup = target.with_suffix(target.suffix + BACKUP_SUFFIX)
        if not backup.exists():
            shutil.copy2(target, backup)
        target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    return updated, added, unchanged, len(arr)


def revert():
    for t in TARGETS:
        b = t.with_suffix(t.suffix + BACKUP_SUFFIX)
        if b.exists():
            shutil.copy2(b, t)
            print("  restored %s" % t)
        else:
            print("  no backup for %s" % t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="?", help="JSON exported by the labelling page")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true",
                    help="restore both trees from the pre-apply backup")
    args = ap.parse_args()

    if args.revert:
        revert()
        return
    if not args.labels:
        ap.error("give a labels file, or --revert")

    labels, meta = load_labels(Path(args.labels))
    metal = sum(1 for v in labels.values() if v.get("metallicDefault", 0) >= 0.5)
    print("%d labels  (%d metal, %d not)  from %s"
          % (len(labels), metal, len(labels) - metal, args.labels))
    if meta:
        print("  exported %s, scope %s" % (meta.get("exported", "?"), meta.get("scope", "?")))

    rough = {}
    for v in labels.values():
        r = v.get("roughnessDefault")
        rough[r] = rough.get(r, 0) + 1
    print("  roughness: " + ", ".join("%s x%d" % (k, rough[k]) for k in sorted(rough)))

    print()
    for t in TARGETS:
        if not t.exists():
            print("  ! missing, skipped: %s" % t)
            continue
        u, a, s, total = apply_to(t, labels, args.dry_run)
        where = "build tree " if "build" in str(t) else "tracked    "
        print("  %s %4d updated  %3d added  %3d already right   (%d entries)"
              % (where, u, a, s, total))

    if args.dry_run:
        print("\ndry run - nothing written")
    else:
        print("\nwritten. Backups kept as *%s (restore with --revert)." % BACKUP_SUFFIX)
        print("No rebuild needed: RTGL1 reads this at startup. Relaunch the game.")


if __name__ == "__main__":
    main()
