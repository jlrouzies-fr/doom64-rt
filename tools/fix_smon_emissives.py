"""Repair two SMON emissive defects found by `whatsthat` on 2026-08-22.

Both reported as "the whole texture is bright" -- SMONF (sector 142, MAP06) and
SMONLB1 (sector 293, MAP07). Same symptom, two different causes, because
`emissiveMult` with no `_e` mask applies to the ENTIRE tile: there is nothing
restricting the emission to a screen, so the whole panel becomes a uniform
emitter. Neither is an rt_sector_emis problem -- whatsthat reports that gate
contributing nothing to either surface (one gated by colour, one below the
lightlevel threshold); the material's own authored value is what reaches the
screen.

  SMONF..SMONF5 -- A BLINKING INDICATOR, and the frames disagree. The panel
      itself is circuitry/vent wall art that must never glow, but a round cyan
      bulb and a row of small LEDs along the bottom ramp up across the frames:

          frame    max luminance   blue-dominant texels
          SMONF              129                      0   bulb OFF
          SMONF1             129                      0   bulb OFF
          SMONF2             139                    111
          SMONF3             161                    111
          SMONF4             186                    157
          SMONF5             238                    157   fully lit

      Retribution ships no brightmap for any of them, so no `_e` was ever
      generated and `emissiveMult` lit the WHOLE PANEL on every frame. Fixed
      per frame, because a shared mask would make the dark frames glow (the
      same per-frame rule as tools/sync_anim_relief_maps.py):

        SMONF, SMONF1 -- genuinely dark. No mask, and `emissiveMult` REMOVED.
        SMONF2..F5    -- mask covering ONLY the bulb and the LED row (2.7-3.8%
              of the tile), `emissiveMult` kept so they still cast. The mask
              keeps the frame's OWN albedo RGB rather than a flat tint, so the
              blink ramp comes straight from the art -- a dim frame yields a
              dim mask -- instead of being authored per frame.

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
# The blink frames whose bulb+LEDs are genuinely dark: no mask, no emissiveMult.
SMONF_DARK = ["SMONF", "SMONF1"]
# The lit frames: mask the bulb+LEDs only, keep emissiveMult so they cast.
SMONF_LIT = ["SMONF2", "SMONF3", "SMONF4", "SMONF5"]
# Matches SMONBA and SMONLC; the per-frame ramp lives in the mask, not here.
SMONF_MULT = "2.8"


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


def make_e_blue_indicator(
    img: Image.Image, *, gain: float = 1.25, blue_over: int = 28, blue_min: int = 70
) -> Image.Image:
    """Cyan bulb + LED row only: blue-dominant texels, the frame's own RGB kept.

    Blue-dominance is what separates the indicator from the panel: the
    circuitry is brown/grey (r >= b), the bulb and LEDs are the only things on
    the tile where blue leads. Keeping albedo RGB instead of slapping a flat
    tint is what makes the BLINK work without authoring a ramp -- a dim frame
    yields a dim mask, so the animation comes out of the art itself.
    """
    img = img.convert("RGBA")
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip, op = img.load(), out.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            if not (b >= r + blue_over and b >= blue_min):
                continue
            op[x, y] = (
                min(255, int(r * gain)),
                min(255, int(g * gain)),
                min(255, int(b * gain)),
                255,
            )
    return out


def set_emissive_mult(text: str, name: str, value: str | None) -> tuple[str, bool]:
    """Set (or with value=None remove) one entry's emissiveMult. Idempotent."""
    have = re.compile(
        r'("textureName":\s*"' + re.escape(name) + r'",)(\s*\n\s*"emissiveMult":\s*)[0-9.]+(,)'
    )
    if have.search(text):
        if value is None:
            return have.sub(r"\1", text), True
        return have.sub(lambda m: m.group(1) + m.group(2) + value + m.group(3), text), True
    if value is None:
        return text, True  # already absent
    # Absent and wanted: insert straight after the name line, same indent.
    add = re.compile(r'(\n(\s*)"textureName":\s*"' + re.escape(name) + r'",)')
    m = add.search(text)
    if not m:
        return text, False
    return add.sub(lambda mm: mm.group(1) + f'\n{mm.group(2)}"emissiveMult": {value},', text), True


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

    # 3) the blink selector must find NOTHING on the frames whose bulb is off.
    #    If it lights those, it is picking up panel circuitry and the dark half
    #    of the animation would glow -- the exact defect this repairs.
    for name in SMONF_DARK:
        n = int((np.asarray(make_e_blue_indicator(
            Image.open(io.BytesIO(raw[name])).convert("RGBA")))[..., 3] > 0).sum())
        print(f"  {name} (bulb off) lit texels = {n}  -> {'OK' if n == 0 else 'LEAKS'}")
        ok &= n == 0
    prev = -1
    for name in SMONF_LIT:
        m = np.asarray(make_e_blue_indicator(
            Image.open(io.BytesIO(raw[name])).convert("RGBA"))).astype(int)
        lit = m[..., 3] > 0
        mean_b = int(m[..., 2][lit].mean()) if lit.any() else 0
        print(f"  {name} lit texels = {int(lit.sum()):4}  mean blue = {mean_b:3}"
              f"  -> {'OK' if mean_b > prev else 'NOT BRIGHTER THAN PREVIOUS FRAME'}")
        ok &= mean_b > prev
        prev = mean_b
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

    # --- SMONF lit frames: mask the bulb + LED row, per frame -------------
    for name in SMONF_LIT:
        img = make_e_blue_indicator(Image.open(io.BytesIO(raw[name])).convert("RGBA"))
        nz = sum(1 for a in img.getchannel("A").tobytes() if a > 0)
        for d in MAT_DIRS:
            if not d.exists():
                continue
            img.save(d / f"{name}_e.png")
        print(f"  {name}_e.png  {img.size}  {nz} lit texels "
              f"({100*nz/(img.width*img.height):.1f}% of tile)  -> {len(MAT_DIRS)} dirs")

    # --- SMONF dark frames: no mask must exist, or the blink stays lit -----
    for name in SMONF_DARK:
        for d in MAT_DIRS:
            stale = d / f"{name}_e.png"
            if stale.exists():
                stale.unlink()
                print(f"  removed stale {stale}")

    # --- textures.json: mult only where a mask now scopes it --------------
    for jf in JSONS:
        if not jf.exists():
            print(f"  ! {jf} missing -- skipped")
            continue
        text = jf.read_text(encoding="utf-8")
        for name in SMONF_DARK:
            text, ok = set_emissive_mult(text, name, None)
            if not ok:
                raise SystemExit(f"{jf}: no entry for {name}")
        for name in SMONF_LIT:
            text, ok = set_emissive_mult(text, name, SMONF_MULT)
            if not ok:
                raise SystemExit(f"{jf}: no entry for {name}")
        jf.write_text(text, encoding="utf-8")
        print(f"  {jf.name}: SMONF/F1 mult removed, SMONF2..F5 mult={SMONF_MULT}")


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
