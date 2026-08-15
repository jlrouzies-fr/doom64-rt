"""Tone down Unseen Evil's fullbright brightmaps.

THE DEFECT. A GZDoom brightmap is a mask, and the mod's own shaders read it as
"how much to ignore the room's light":

    shaders/d64ue/brightermap.fp
        float bright = grayscale(texture(brighttexture, uv));
        mat.Base = mix(getTexel(uv), baseTex, bright);

`getTexel()` is the normally-lit texel and `baseTex` is the raw texture, so a mask
pixel at 255 means the surface renders at full brightness no matter how dark the
room is. `brightermap_dynamic.fp`, used by 26 of the 96 material blocks, then goes
further:

    vec4 brightMix = baseTex * colorOverlay * vec4(1.5,1.5,1.5,1.0);

i.e. 1.5x ON TOP of raw. A 255 mask under that shader lands near 380% of the
texture, which is the "sticks out" this was reported as.

WHY 192, AND WHY ONLY SOME MASKS. This is not a number invented here -- it is the
mod's own convention. Of the 40 distinct masks, 27 already peak between 40 and
240 (the SMONE* monitors sit at 192, doors at 188-224): the author toned them
deliberately. Only 13 peak at 255, and 12 of those also carry the 1.5x shader.
Those 13 are the outliers, so they are brought to the modal ceiling the rest of
the pack already uses.

WHAT THIS DOES NOT DO. Nothing is removed. No material block is deleted, no
texture stops glowing, no mask changes shape, and every channel is scaled by the
SAME factor so hue is preserved exactly -- key trims and door lights keep their
colour, they just stop being blown out. The families these masks mark (switches,
keys, monitors, exit signs, light panels) are the ones this project deliberately
keeps lit; stripping them is what the notes in scan_painted_light.py call the
CRTRAKA mistake.

The 6 pointlights in GLDEFS.lights are real dynamic lights and are untouched.

OUTPUT is an overlay pk3 loaded AFTER the mod. The original stays a pristine
redistributable and the change is reversible by dropping the overlay.

    python tools/tone_unseenevil_brightmaps.py            # census (dry run)
    python tools/tone_unseenevil_brightmaps.py --write    # build the overlay
    python tools/tone_unseenevil_brightmaps.py --verify   # check a built overlay
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

MOD = PROJ_ROOT / r"Doom64-UnseenEvil\D64UnseenEvil-v1.0.3.pk3"
OVERLAY = PROJ_ROOT / r"Doom64-UnseenEvil\d64ue-brightmap-tone.pk3"

# A mask is an outlier if it reaches this; it is then scaled so its peak lands on
# CEILING. 250 rather than 255 because a couple of masks peak at 251-254 from
# resampling and are the same defect.
TRIGGER = 250
CEILING = 192

GLDEFS = "GLDEFS.brightmaps"


def material_blocks(text: str) -> list[tuple[str, str, str]]:
    """-> [(texture, brightmap_path, shader_path)] straight out of GLDEFS."""
    out = []
    for tex, body in re.findall(
        r'(?is)material\s+texture\s+"?([^"\s{]+)"?\s*\{(.*?)\}', text
    ):
        bm = re.search(r'(?i)brightmap\s+"?([^"\s]+)"?', body)
        sh = re.search(r'(?i)shader\s+"?([^"\s]+)"?', body)
        out.append((tex, bm.group(1) if bm else "", sh.group(1) if sh else ""))
    return out


def composite_patches(zf: zipfile.ZipFile) -> dict[str, list[str]]:
    """TEXTURES-lump texture name -> the patch files it is built from.

    Needed because 40 of the 96 material blocks name a brightmap that is NOT a
    file: it is a composite defined in a TEXTURES lump, which then references the
    real PNG as a Patch. A file-only lookup silently skips all of them, and that
    hid a second tier of 255 masks -- every switch family (they share
    d64_lockswitch_bm.png) and the exit sign, whose brightmap patch is literally
    allwhite.png, i.e. the whole sign fullbright.
    """
    out: dict[str, list[str]] = {}
    for name in zf.namelist():
        base = name.upper().split("/")[-1]
        if not base.startswith("TEXTURES"):
            continue
        try:
            text = zf.read(name).decode("latin-1")
        except Exception:
            continue
        for m in re.finditer(
            r'(?is)\b(?:texture|walltexture|flat|graphic|sprite)\s+"?([^",\s]+)"?'
            r'\s*,\s*\d+\s*,\s*\d+\s*\{(.*?)\n\}', text
        ):
            patches = re.findall(r'(?i)patch\s+"?([^",\s]+)"?', m.group(2))
            if patches:
                out.setdefault(m.group(1).lower(), []).extend(patches)
    return out


def resolve(zf: zipfile.ZipFile, path: str,
            comps: dict[str, list[str]] | None = None) -> list[str]:
    """-> every real image file behind a GLDEFS brightmap reference.

    A list, not a single name: a composite can be built from more than one patch
    and each would need toning independently. References are extensionless and
    case-insensitive.
    """
    if not path:
        return []
    lut = {n.lower(): n for n in zf.namelist()}

    def direct(p: str) -> str | None:
        for cand in (p, p + ".png", p + ".lmp"):
            hit = lut.get(cand.lower())
            if hit:
                return hit
        return None

    hit = direct(path)
    if hit:
        return [hit]
    found = []
    for patch in (comps or {}).get(path.lower(), []):
        for prefix in ("", "patches/", "textures/", "brightmaps/"):
            hit = direct(prefix + patch)
            if hit:
                found.append(hit)
                break
    return list(dict.fromkeys(found))


def measure(blob: bytes):
    """-> (image, peak channel over visible pixels, count of non-black pixels)"""
    im = Image.open(io.BytesIO(blob)).convert("RGBA")
    px = list(im.getdata())
    vis = [p for p in px if p[3] > 0]
    lit = [p for p in vis if max(p[:3]) > 0]
    peak = max((max(p[:3]) for p in lit), default=0)
    return im, peak, len(lit)


def rescale(im: Image.Image, factor: float) -> Image.Image:
    """Scale RGB by one factor, keep alpha.

    max(1, ...) on anything already non-zero: without it a mask pixel at 1 would
    round to 0 and that texel would stop glowing entirely, which would be a shape
    change rather than a level change -- exactly what this must not do.
    """
    out = []
    for r, g, b, a in im.getdata():
        if max(r, g, b) == 0:
            out.append((r, g, b, a))
            continue
        out.append((
            max(1, round(r * factor)) if r else 0,
            max(1, round(g * factor)) if g else 0,
            max(1, round(b * factor)) if b else 0,
            a,
        ))
    new = Image.new("RGBA", im.size)
    new.putdata(out)
    return new


def collect(zf: zipfile.ZipFile):
    """-> (rows, targets). rows is every distinct mask; targets are the outliers."""
    text = zf.read(GLDEFS).decode("latin-1")
    blocks = material_blocks(text)
    comps = composite_patches(zf)
    seen: dict[str, dict] = {}
    for tex, bm, sh in blocks:
        for real in resolve(zf, bm, comps):
            rec = seen.setdefault(real, {"users": [], "dynamic": False})
            rec["users"].append(tex)
            if "dynamic" in sh.lower():
                rec["dynamic"] = True
    rows = []
    for real, rec in seen.items():
        try:
            im, peak, lit = measure(zf.read(real))
        except Exception:
            continue
        rows.append({"path": real, "peak": peak, "lit": lit,
                     "users": rec["users"], "dynamic": rec["dynamic"],
                     "size": im.size})
    rows.sort(key=lambda r: (-r["peak"], r["path"]))
    targets = [r for r in rows if r["peak"] >= TRIGGER]
    return rows, targets, len(blocks)


def census(zf):
    rows, targets, nblocks = collect(zf)
    print(f"{GLDEFS}: {nblocks} material blocks -> {len(rows)} distinct masks resolved")
    print(f"outliers at peak >= {TRIGGER}: {len(targets)}  "
          f"({sum(1 for r in targets if r['dynamic'])} on the 1.5x dynamic shader)")
    print(f"already toned (left alone): {len(rows) - len(targets)}")
    print()
    print(f"{'mask':52}{'peak':>5}{'lit px':>8}  shader   textures")
    for r in targets:
        print(f"{r['path']:52}{r['peak']:5}{r['lit']:8}  "
              f"{'dynamic' if r['dynamic'] else 'plain  '}  {len(r['users'])}")
    return rows, targets


def write_overlay(zf):
    rows, targets = census(zf)
    print()
    if OVERLAY.exists():
        OVERLAY.unlink()
    with zipfile.ZipFile(OVERLAY, "w", zipfile.ZIP_DEFLATED) as out:
        for r in targets:
            src = zf.read(r["path"])
            im, peak, lit = measure(src)
            factor = CEILING / peak
            new = rescale(im, factor)
            buf = io.BytesIO()
            new.save(buf, format="PNG")
            out.writestr(r["path"], buf.getvalue())
            _, npeak, nlit = measure(buf.getvalue())
            print(f"  {r['path']:52} peak {peak} -> {npeak}  "
                  f"lit {lit} -> {nlit}  x{factor:.3f}")
    print(f"\nwrote {OVERLAY}  ({len(targets)} masks)")


def verify(zf):
    if not OVERLAY.exists():
        sys.exit(f"no overlay at {OVERLAY} -- run with --write first")
    rows, targets, nblocks = collect(zf)
    ov = zipfile.ZipFile(OVERLAY)
    names = set(ov.namelist())
    bad = []

    want = {r["path"] for r in targets}
    if names != want:
        bad.append(f"overlay contents differ from the target set: "
                   f"extra={sorted(names - want)} missing={sorted(want - names)}")

    for r in rows:
        if r["path"] not in names:
            continue  # untouched by design
        src_im, src_peak, src_lit = measure(zf.read(r["path"]))
        new_im, new_peak, new_lit = measure(ov.read(r["path"]))
        if new_peak != CEILING:
            bad.append(f"{r['path']}: peak {new_peak}, expected {CEILING}")
        if new_lit != src_lit:
            bad.append(f"{r['path']}: lit pixels {src_lit} -> {new_lit} "
                       f"(mask shape changed)")
        if new_im.size != src_im.size:
            bad.append(f"{r['path']}: size changed")
        # hue: every channel scaled by one factor, so ratios survive rounding
        f = CEILING / src_peak
        for (r0, g0, b0, a0), (r1, g1, b1, a1) in zip(src_im.getdata(),
                                                      new_im.getdata()):
            if a0 != a1:
                bad.append(f"{r['path']}: alpha changed")
                break
            for before, after in ((r0, r1), (g0, g1), (b0, b1)):
                if before and abs(after - max(1, round(before * f))) > 0:
                    bad.append(f"{r['path']}: channel {before} -> {after} "
                               f"off the scale factor")
                    break
            else:
                continue
            break

    # every material block must still resolve once the overlay is loaded
    text = zf.read(GLDEFS).decode("latin-1")
    comps = composite_patches(zf)
    unresolved = [tex for tex, bm, _sh in material_blocks(text)
                  if bm and not resolve(zf, bm, comps)]
    print(f"masks in overlay: {len(names)}   untouched: {len(rows) - len(names)}")
    print(f"material blocks whose brightmap does not resolve to a file: "
          f"{len(unresolved)}"
          f"{'  (TEXTURES-lump composites, not PNGs)' if unresolved else ''}")
    if bad:
        print("\nFAIL:")
        for b in bad[:20]:
            print("  -", b)
        sys.exit(1)
    print("\nPASS: peaks at the ceiling, mask shapes unchanged, hue preserved.")


def main():
    if not MOD.exists():
        sys.exit(f"mod not found: {MOD}")
    zf = zipfile.ZipFile(MOD)
    if "--write" in sys.argv:
        write_overlay(zf)
    elif "--verify" in sys.argv:
        verify(zf)
    else:
        census(zf)


if __name__ == "__main__":
    main()
