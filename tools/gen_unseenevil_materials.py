"""Generate RT materials for Doom 64: Unseen Evil's own art -- emissives and normals.

WHY THIS EXISTS. Retribution's walls "just worked" under RT because every one of
its textures is a named WAD lump, and every material (rt/mat/<NAME>_e/_n/_h/_orm
plus the textures.json rows) is keyed on that name. Unseen Evil's Terraformer
puts DIFFERENT art on DOOM II's walls: of its 442 wall targets, 80 are bare Doom
64 names (pixel-identical to Retribution's -- those get Retribution's materials
for free) and 362 are path-shaped -- 246 TEXTURES composites named by their
declared path and 116 plain PNGs that reach the renderer NAMELESS, because
GZDoom names a pk3 texture only when its basename fits 8 characters. Nothing
could ever match those, so 82% of the mod's walls carried no material at all.

Two halves fix that, and this script is the second:

  1. ENGINE (rt_buffers.h MakeTextureName): a nameless texture is now addressed
     by its file path minus the extension -- "textures/pepy/d64_brown1" -- and
     RTGL1 resolves that to rt/mat/textures/pepy/d64_brown1_e.png. Composites
     were already named by their declared path.

  2. THIS SCRIPT writes those files, automatically, from the mod's own data:

     _e  EMISSIVE, from the mod's GLDEFS brightmaps. This is the same source
         gen_world_emissives.py trusts first for Retribution ("the artist saying
         these texels are self-lit"). It matters more here than it looks: the
         engine's brightmap fallback for UE (rt_draw.cpp l_hasWorldBrightmap)
         only flags the primitive emissive with a MULTIPLIER -- the brightmap's
         pixels never reach RTGL1, which takes emission solely from an _e
         override. So a UE door indicator glowed as its ENTIRE face, dimly and
         unmasked. With a real _e the RAW mask is what is seen (ray-traced
         contract: _e is the emission colour itself, not a mask over albedo), so
         it is written as albedo colour x mask, the use_albedo_color rule from
         gen_world_emissives.make_e_from_brightmap.

     _n  NORMAL, a Sobel from luma (gen_detail_orm.make_normal) over a lightly
         blurred albedo. "Some normals": relief that reads under a moving light
         without the per-texel noise a raw top octave gives (the height-map
         lesson in docs/rt-blood-pools.md). No _h, no _orm -- an ORM needs a
         surface class per texture and the automatic way has none.

WHAT IS NEVER TOUCHED. Any name Retribution already has a material for. A short
stem (<= 8 chars) arrives as a bare uppercase name, and if Retribution-RT-
Materials carries that name the file is skipped, so a UE run cannot overwrite an
authored Retribution map. The 80 shared names therefore stay Retribution's.

WHERE IT WRITES -- all four material dirs, because developerMode reads mat_dev
and every build restages the tracked tree (memory: mat_dev wins and the build
resyncs it):
    build/RelWithDebInfo/rt/mat  and  rt/mat_dev            (live)
    Doom64-UnseenEvil/UnseenEvil-RT-Materials/rt/mat(_dev)  (staged by the build)
The UE dir is gitignored like every other UE overlay; this script is its source.

    py -3 tools/gen_unseenevil_materials.py            # census, writes nothing
    py -3 tools/gen_unseenevil_materials.py --write
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_unseenevil_textures_gallery as X  # noqa: E402  (UE/IWAD decoding)
from gen_detail_orm import make_normal  # noqa: E402

PROJ = Path(__file__).resolve().parents[1]
MOD = PROJ / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
TONE = PROJ / "Doom64-UnseenEvil" / "d64ue-brightmap-tone.pk3"
RET_MAT = PROJ / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat"
BUILD_RT = PROJ / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt"
UE_RT = PROJ / "Doom64-UnseenEvil" / "UnseenEvil-RT-Materials" / "rt"
MAT_DIRS = [BUILD_RT / "mat", BUILD_RT / "mat_dev", UE_RT / "mat", UE_RT / "mat_dev"]

NORMAL_STRENGTH = 1.2
NORMAL_BLUR = 0.6


def rt_name(ue: X.UeTextures, ref: str) -> str | None:
    """The name the engine will upload this texture under, or None."""
    key = ue.resolve(ref)
    if key is None:
        return None
    if key.startswith("def:"):
        # A composite is named by its declared path, spelling as declared.
        return key[4:]
    entry = key[5:]
    stem = entry.rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    if len(stem) <= 8:
        # GZDoom gives this one a classic short name.
        return stem.upper()
    # Nameless in GZDoom; the engine now keys it on the path minus extension.
    return entry.rsplit(".", 1)[0] if "." in entry.rsplit("/", 1)[-1] else entry


def is_retribution_owned(name: str) -> bool:
    if "/" in name:
        return False
    return any(RET_MAT.glob(f"{name}_*")) or any(RET_MAT.glob(f"{name}.*"))


def mapping_targets(z: zipfile.ZipFile) -> list[str]:
    out = []
    for n in z.namelist():
        if not n.lower().startswith("resources/d64ue_textures."):
            continue
        for ln in z.read(n).decode("latin1").splitlines():
            s = ln.strip()
            if not s or s.startswith(("//", "#")) or ":" not in s:
                continue
            tgt = s.split(":")[1].strip()
            if tgt and tgt.upper() != "BLANK":
                out.append(tgt)
    return out


def anim_and_switch_frames(z: zipfile.ZipFile) -> list[str]:
    """Every texture named by the mod's ANIMDEFS / SWITCHES: frames must carry
    their own materials, since the engine looks up the frame being drawn."""
    text = "".join(
        z.read(n).decode("latin1")
        for n in z.namelist()
        if n.upper().startswith(("ANIMDEFS", "SWITCHES"))
    )
    text = X.strip_comments(text)
    names = re.findall(r'(?im)^\s*(?:texture|flat|pic|switch|on|off)\s+"?([^"\s,]+)"?', text)
    return [n for n in names if n.lower() not in ("pic", "tics", "on", "off")]


def brightmap_bindings(z: zipfile.ZipFile) -> dict[str, str]:
    gl = "".join(z.read(n).decode("latin1") for n in z.namelist() if n.upper().startswith("GLDEFS"))
    gl = X.strip_comments(gl)
    out = {}
    for tex, bm in re.findall(r'(?is)material\s+texture\s+"([^"]+)"\s*\{[^}]*?brightmap\s+"([^"]+)"', gl):
        out[tex] = bm
    return out


def make_e(albedo: Image.Image, bm: Image.Image) -> Image.Image | None:
    """albedo colour x brightmap mask -- gen_world_emissives' use_albedo_color rule."""
    bm = bm.convert("RGBA")
    if bm.size != albedo.size:
        bm = bm.resize(albedo.size, Image.Resampling.NEAREST)
    out = Image.new("RGBA", albedo.size, (0, 0, 0, 0))
    ap, bp, op = albedo.load(), bm.load(), out.load()
    lit = 0
    for y in range(albedo.size[1]):
        for x in range(albedo.size[0]):
            r, g, b, a = bp[x, y]
            v = max(r, g, b)
            if a < 8 or v < 20:
                continue
            ar, ag, ab, aa = ap[x, y]
            if aa < 8:
                continue
            s = min(1.35, (v / 255.0) * 1.5)
            op[x, y] = (min(255, int(ar * s)), min(255, int(ag * s)), min(255, int(ab * s)), 255)
            lit += 1
    return out if lit else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--no-normals", action="store_true")
    args = ap.parse_args()

    d2p = X.find_iwad("doom2.wad")
    if d2p is None:
        sys.exit("no doom2.wad found -- set D64RT_UE_IWAD")
    d2 = X.IwadTextures(X.Wad(d2p.read_bytes()), "DOOM2")
    ue = X.UeTextures(MOD, d2.pal)
    X.IWAD_FALLBACK = lambda name: (
        d2.render_wall(name) if d2.has(name, "wall")
        else d2.render_flat(name) if d2.has(name, "flat") else None
    )
    z = zipfile.ZipFile(MOD)
    tone = zipfile.ZipFile(TONE) if TONE.exists() else None
    tone_paths = {n.lower(): n for n in tone.namelist()} if tone else {}

    def render_brightmap(ref: str) -> Image.Image | None:
        # The tone overlay loads after the mod, so its rescaled masks win.
        for cand in (ref.lower(), ref.lower() + ".png"):
            if cand in tone_paths:
                return Image.open(io.BytesIO(tone.read(tone_paths[cand]))).convert("RGBA")
        key = ue.resolve(ref)
        return ue.render(key) if key else None

    bms = brightmap_bindings(z)
    refs = mapping_targets(z) + anim_and_switch_frames(z) + list(bms)

    # One job per engine name.
    jobs: dict[str, str] = {}
    for ref in refs:
        name = rt_name(ue, ref)
        if name and name not in jobs:
            jobs[name] = ref
    bm_by_name = {}
    for tex, bm in bms.items():
        name = rt_name(ue, tex)
        if name:
            bm_by_name[name] = bm

    stats = dict(targets=len(jobs), skipped_retribution=0, unrendered=0, e=0, n=0, e_empty=0)
    plan: list[tuple[str, Image.Image | None, Image.Image | None]] = []
    for name, ref in sorted(jobs.items()):
        # PATH-SHAPED NAMES ONLY. A bare name is shared with Retribution by
        # construction -- the 80 bare mapping targets ARE Doom 64 names, and a
        # bare name with a textures.json row but no rt/mat file (DTWMD25) would
        # take a generated _n into the SHARED material dir, where Retribution
        # would wear it too. Subfolders cannot collide with anything it ships.
        if "/" not in name or is_retribution_owned(name):
            stats["skipped_retribution"] += 1
            continue
        key = ue.resolve(ref)
        albedo = ue.render(key) if key else None
        if albedo is None:
            stats["unrendered"] += 1
            continue
        albedo = albedo.convert("RGBA")
        e = None
        if name in bm_by_name:
            bm = render_brightmap(bm_by_name[name])
            e = make_e(albedo, bm) if bm is not None else None
            if e is None:
                stats["e_empty"] += 1
        n = None
        if not args.no_normals:
            soft = albedo.filter(ImageFilter.GaussianBlur(NORMAL_BLUR))
            n = make_normal(soft, NORMAL_STRENGTH)
        if e is not None:
            stats["e"] += 1
        if n is not None:
            stats["n"] += 1
        plan.append((name, e, n))

    print("Unseen Evil materials, automatic")
    for k, v in stats.items():
        print(f"  {k:22} {v}")
    print(f"  material dirs          {len(MAT_DIRS)}")
    if not args.write:
        print("\n(census only -- pass --write to write the files)")
        return

    written = 0
    for name, e, n in plan:
        for d in MAT_DIRS:
            base = d / name
            base.parent.mkdir(parents=True, exist_ok=True)
            if e is not None:
                e.save(f"{base}_e.png")
                written += 1
            if n is not None:
                n.save(f"{base}_n.png")
                written += 1
    print(f"\nwrote {written} files across {len(MAT_DIRS)} dirs ({written // len(MAT_DIRS)} per dir)")


if __name__ == "__main__":
    main()
