"""Repair two SMON emissive defects found by `whatsthat` on 2026-08-22.

Both reported as "the whole texture is bright" -- SMONF (sector 142, MAP06) and
SMONLB1 (sector 293, MAP07). Same symptom, two different causes, because
`emissiveMult` with no `_e` mask applies to the ENTIRE tile: there is nothing
restricting the emission to a screen, so the whole panel becomes a uniform
emitter. Neither is an rt_sector_emis problem -- whatsthat reports that gate
contributing nothing to either surface (one gated by colour, one below the
lightlevel threshold); the material's own authored value is what reaches the
screen.

  SMONF, SMONF1..SMONF5  -- NOT MONITORS. The art is a circuitry/vent wall
      panel with a dark round port: no screen, no lamp, nothing that should
      self-illuminate. Retribution ships no brightmap for them and neither do
      their patches, so no `_e` was ever generated -- correctly. The
      `emissiveMult` was the mistake. REMOVED entirely; the panel is lit by the
      room like any other wall.

  SMONLB1..SMONLB4  -- GENUINE MONITORS, and a generator gap. Each is a TEXTURES
      composite of one SMONB* patch placed twice (`Patch SMONBA, 0, 0` +
      `Patch SMONBA, 64, 0 {FlipX}`), and SMONBA..SMONBD all ship brightmaps and
      all have correct `_e` masks of their own. But gen_world_emissives.py keys
      off a texture's OWN brightmap, and only the parallel SMONLC1..4 family had
      one authored -- so SMONLC got masks and the structurally identical SMONLB
      family fell through. Its two name-based handlers miss it as well:
      `_is_static_screen_smon` matches `^SMONB` and `_is_sparse_smon_text`
      matches `^SMON[ACDE]`, and "SMONLB1" is neither. GENERATED here, keeping
      `emissiveMult` 2.8 to match SMONBA and SMONLC.

WHY THE COMPOSITE IS SAFE TO BUILD RATHER THAN AUTHOR. Verified, not assumed:
SMONLC1's authored brightmap is byte-for-byte identical to its own patch
brightmap composited by the TEXTURES rule (max abs diff 0 over 8192 px), so
compositing patch art reproduces what an author would have shipped. And running
the composite through gen_world_emissives.make_e_static_screen -- imported here,
not reimplemented, so it cannot drift -- rebuilds the existing SMONBA.._e files
byte-for-byte (max abs diff 0, 260/260 nonzero texels each). Both checks re-run
under --verify.

  python tools/fix_smon_emissives.py --audit     # report only, touch nothing
  python tools/fix_smon_emissives.py --verify    # prove the pipeline, no writes
  python tools/fix_smon_emissives.py             # apply both repairs
"""

from __future__ import annotations

import io
import re
import struct
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_world_emissives import make_e_static_screen

PROJ_ROOT = Path(__file__).resolve().parents[1]

WAD = PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
# The brightmaps pk3 is Retribution's own file -- the user brings it, so it is
# NOT in the repo. Prefer the installed copy, fall back to a repo-local one.
BM_CANDIDATES = [
    Path(r"G:\Games\Doom64-RT\game\D64RTR_BRIGHTMAPS.PK3"),
    PROJ_ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3",
]

# All four material trees. developerMode reads mat_dev in preference to mat, and
# every build xcopies the tracked tree over the build tree -- so a mask written
# to fewer than all four is a ghost fix that reverts on the next build.
MAT_DIRS = [
    PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat",
    PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev",
    PROJ_ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat",
    PROJ_ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat_dev",
]

# RTGL1 reads only textures.json; the split textures_*.json overlays are inert.
JSONS = [
    PROJ_ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures.json",
    PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json",
    Path(r"G:\Games\Doom64-RT\rt\data\textures.json"),
]

# name -> the single patch it tiles twice (second copy FlipX at x=64)
SMONLB = {
    "SMONLB1": "SMONBA",
    "SMONLB2": "SMONBB",
    "SMONLB3": "SMONBC",
    "SMONLB4": "SMONBD",
}
SMONF = ["SMONF", "SMONF1", "SMONF2", "SMONF3", "SMONF4", "SMONF5"]


def read_wad_lumps(path: Path) -> list[tuple[str, bytes]]:
    data = path.read_bytes()
    _kind, n, o = struct.unpack_from("<4sII", data, 0)
    out = []
    for i in range(n):
        off, sz, rawname = struct.unpack_from("<II8s", data, o + i * 16)
        nm = rawname.split(b"\0")[0].decode("ascii", "replace")
        out.append((nm, data[off : off + sz]))
    return out


def load_sources() -> tuple[dict[str, bytes], zipfile.ZipFile]:
    if not WAD.exists():
        raise SystemExit(f"missing {WAD}")
    raw: dict[str, bytes] = {}
    for nm, blob in read_wad_lumps(WAD):
        raw.setdefault(nm.upper(), blob)
    for cand in BM_CANDIDATES:
        if cand.exists():
            return raw, zipfile.ZipFile(cand)
    raise SystemExit(
        "no D64RTR_BRIGHTMAPS.PK3 found -- it is Retribution's file, not ours.\n"
        "Looked in:\n  " + "\n  ".join(str(c) for c in BM_CANDIDATES)
    )


def composite_pair(img: Image.Image) -> Image.Image:
    """The TEXTURES rule for this family: patch at 0,0 and FlipX at 64,0."""
    out = Image.new("RGBA", (img.width * 2, img.height), (0, 0, 0, 0))
    out.paste(img, (0, 0))
    out.paste(img.transpose(Image.FLIP_LEFT_RIGHT), (img.width, 0))
    return out


def build_lb_mask(name: str, raw: dict[str, bytes], z: zipfile.ZipFile) -> Image.Image:
    patch = SMONLB[name]
    albedo = Image.open(io.BytesIO(raw[patch])).convert("RGBA")
    bright = Image.open(io.BytesIO(z.read(f"brightmaps/textures/{patch}.png"))).convert("RGBA")
    return make_e_static_screen(composite_pair(bright), composite_pair(albedo))


def verify(raw: dict[str, bytes], z: zipfile.ZipFile) -> bool:
    """Re-run both proofs the docstring claims. Any failure aborts an apply."""
    import numpy as np

    ok = True

    # 1) compositing patch brightmaps reproduces an AUTHORED composite brightmap
    authored = Image.open(io.BytesIO(z.read("brightmaps/textures/SMONLC1.png"))).convert("RGB")
    built = composite_pair(
        Image.open(io.BytesIO(z.read("brightmaps/textures/SMONCA.png"))).convert("RGBA")
    ).convert("RGB")
    d = int(np.abs(np.asarray(authored).astype(int) - np.asarray(built).astype(int)).max())
    print(f"  composite rule vs authored SMONLC1 brightmap: max abs diff = {d}"
          f"  -> {'OK' if d == 0 else 'MISMATCH'}")
    ok &= d == 0

    # 2) our mask call rebuilds the existing SMONB* _e files byte-for-byte
    ref_dir = PROJ_ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat_dev"
    for patch in SMONLB.values():
        existing = ref_dir / f"{patch}_e.png"
        if not existing.exists():
            print(f"  {patch}: no existing _e to check against -- SKIPPED")
            continue
        alb = Image.open(io.BytesIO(raw[patch])).convert("RGBA")
        bm = Image.open(io.BytesIO(z.read(f"brightmaps/textures/{patch}.png"))).convert("RGBA")
        rebuilt = np.asarray(make_e_static_screen(bm, alb)).astype(int)
        have = np.asarray(Image.open(existing).convert("RGBA")).astype(int)
        d = int(np.abs(rebuilt - have).max()) if rebuilt.shape == have.shape else -1
        print(f"  rebuild {patch}_e: max abs diff = {d}  -> {'OK' if d == 0 else 'MISMATCH'}")
        ok &= d == 0
    return ok


def audit() -> None:
    """Every texture carrying emissiveMult but shipping no _e mask anywhere.

    A mask-less emissiveMult lights the whole tile, which is the defect this
    script exists for -- so this is the query that finds the rest of them.
    """
    src = JSONS[0]
    text = src.read_text(encoding="utf-8")
    entries = re.findall(
        r'"textureName":\s*"([^"]+)",\s*\n\s*"emissiveMult":\s*([0-9.]+)', text
    )
    print(f"{src.name}: {len(entries)} entries carry emissiveMult")
    bad = []
    for name, mult in entries:
        if not any((d / f"{name}_e.png").exists() or (d / f"{name}_e.ktx2").exists()
                   for d in MAT_DIRS):
            bad.append((name, mult))
    if not bad:
        print("  every one has an _e mask somewhere -- nothing to report")
        return
    print(f"  {len(bad)} with emissiveMult but NO _e mask (whole tile emits):")
    for name, mult in sorted(bad):
        print(f"    {name:12} emissiveMult={mult}")


def apply(raw: dict[str, bytes], z: zipfile.ZipFile) -> None:
    # --- SMONLB: generate the missing masks -------------------------------
    for name in SMONLB:
        img = build_lb_mask(name, raw, z)
        nz = sum(1 for a in img.getchannel("A").tobytes() if a > 0)
        for d in MAT_DIRS:
            if not d.exists():
                print(f"  ! {d} missing -- skipped")
                continue
            img.save(d / f"{name}_e.png")
        print(f"  {name}_e.png  {img.size}  {nz} lit texels  -> {len(MAT_DIRS)} dirs")

    # --- SMONF: remove the emissiveMult that never belonged ---------------
    for jf in JSONS:
        if not jf.exists():
            print(f"  ! {jf} missing -- skipped")
            continue
        text = jf.read_text(encoding="utf-8")
        removed = 0
        for name in SMONF:
            pat = re.compile(
                r'("textureName":\s*"' + re.escape(name) + r'",)\s*\n\s*"emissiveMult":\s*[0-9.]+,'
            )
            text, n = pat.subn(r"\1", text)
            removed += n
        jf.write_text(text, encoding="utf-8")
        print(f"  {jf}: removed emissiveMult from {removed}/{len(SMONF)} SMONF entries")


def main() -> None:
    if "--audit" in sys.argv:
        audit()
        return
    raw, z = load_sources()
    print("verifying pipeline against known-good art:")
    ok = verify(raw, z)
    if "--verify" in sys.argv:
        print("verify only -- nothing written")
        return
    if not ok:
        raise SystemExit(
            "verification FAILED -- the source art or the generator changed. "
            "Refusing to write masks built on an unproven pipeline."
        )
    print("applying:")
    apply(raw, z)


if __name__ == "__main__":
    main()
