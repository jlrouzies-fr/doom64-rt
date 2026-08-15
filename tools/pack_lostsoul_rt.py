"""Pack Lost Soul yellow-fire sprites + flame cast light (no actor replace).

The stock 64LostSoul stays unchanged (BRIGHT / SoulTrans). Fire color comes from
sprite replacements + mat/_e, and the light is attached to those same SKUL fire
frames: the flame itself is the emitter.

Two dead ends are recorded here so they are not retried:

1. Sprite offsets. Every SKUL lump carries a PNG grAb chunk (the Doom draw
   offset). PIL drops ancillary chunks, so tinting each frame through PIL
   shipped all 40 replacements with no offset; GZDoom then falls back to zero,
   which hangs the sprite BELOW the actor origin -- every Lost Soul rendered
   buried in the floor. See png_set_grab(); it is mandatory, not an optimisation.

2. The LSGL carrier blob (removed 2026-08-08). The old design spawned a separate
   disc actor to hold the light, so the fire texture would not self-bleach. It
   cannot work under RT: the play launcher sets rt_translucent_minalpha 0.72,
   which FLOORS translucent sprite alpha for the path tracer, so the disc renders
   near-opaque no matter how low Alpha goes -- it read as a solid orange ball on
   every soul. Dimming it instead via emissiveMult does not help either, because
   RTGL1 derives the attached light from emissive coverage: drop the emissive and
   the cast light dies with it. The two are coupled, not independent knobs.
   Lighting the fire frames directly avoids all of it and is what the effect
   actually is, physically.
"""
from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

from PIL import Image

from gen_enemy_eye_emissives import (
    ENEMY_GALLERY_SCENE,
    MAT,
    MAT_DEV,
    OMAT,
    open_img,
    patch_global,
    save_albedo,
    tone_skul_albedo,
    upsert_json,
    wad_lumps,
)

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
OUT_DIR = ROOT / r"tools\d64r-lostsoul-rt"
OUT_PK3 = ROOT / r"Doom64-Retribution\d64r-lostsoul-rt.pk3"
SPR_DIR = OUT_DIR / "sprites"

# The flame IS the light. These ride on the SKUL fire frames themselves.
#
#   SKUL_LIGHT (lightIntensity) -- how far/hard the flame lights the room.
#   SKUL_EMIS  (emissiveMult)   -- how bright the fire pixels look. RTGL1 derives
#                                  the attached light from emissive coverage, so
#                                  these two are COUPLED: dropping the emissive to
#                                  hide a glow also kills the cast light. Tune
#                                  SKUL_LIGHT first; only raise SKUL_EMIS if the
#                                  fire itself looks flat.
#
# The old note "attached light on the same sprite white-blooms the fire" came from
# gen_fx_emissives PREFIX_RULES applying lightIntensity 700 *plus* noShadow to
# these frames. noShadow is the part that blows out (it also killed enemy
# shadows); a bounded intensity with shadows left on does not.
SKUL_LIGHT = 450.0
SKUL_EMIS = 0.35
SKUL_HEX = "ff9028"

# Only the living/flight frames carry fire. G0 onward is the death and gib
# sequence -- a corpse must not go on lighting the room.
SKUL_LIT_FRAMES = "ABCDEF"


def read_grab(png: bytes) -> tuple[int, int] | None:
    """Return the (left, top) sprite offset from a PNG's grAb chunk, if present."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    i = 8
    while i + 8 <= len(png):
        (ln,) = struct.unpack_from(">I", png, i)
        typ = png[i + 4 : i + 8]
        if typ == b"grAb":
            return struct.unpack_from(">ii", png, i + 8)
        if typ == b"IEND":
            break
        i += 12 + ln
    return None


def png_set_grab(png: bytes, xoff: int, yoff: int) -> bytes:
    """Rewrite a PNG with the given grAb sprite offset.

    PIL silently drops every ancillary chunk it does not understand, and grAb --
    the Doom sprite offset -- is one of them. A replacement sprite without it
    makes GZDoom fall back to a zero offset, which hangs the whole sprite BELOW
    the actor origin instead of above it. That is why every Lost Soul rendered
    buried in the floor, and why the removed LSGL glow disc read as a dome half-sunk in
    the ground: the tinting pass round-tripped all 40 SKUL sprites through PIL.
    """
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    body = bytearray(png[:8])
    chunk = struct.pack(">ii", xoff, yoff)
    grab = struct.pack(">I", len(chunk)) + b"grAb" + chunk
    grab += struct.pack(">I", zlib.crc32(b"grAb" + chunk) & 0xFFFFFFFF)
    i = 8
    inserted = False
    while i + 8 <= len(png):
        (ln,) = struct.unpack_from(">I", png, i)
        typ = png[i + 4 : i + 8]
        nxt = i + 12 + ln
        if typ == b"grAb":  # drop any stale offset
            i = nxt
            continue
        body += png[i:nxt]
        if typ == b"IHDR" and not inserted:
            body += grab  # grAb must precede IDAT
            inserted = True
        i = nxt
        if typ == b"IEND":
            break
    if not inserted:
        raise ValueError("PNG had no IHDR")
    return bytes(body)


def write_skul_meta(names: list[str]) -> None:
    """Attach the cast light to the SKUL fire frames themselves."""
    entries = {}
    for name in names:
        frame = name[4:5].upper()
        meta = {"textureName": name, "emissiveMult": SKUL_EMIS}
        if frame in SKUL_LIT_FRAMES:
            meta["lightIntensity"] = SKUL_LIGHT
            meta["lightColorHEX"] = SKUL_HEX
            meta["lightEvenOnDynamic"] = True
            # No noShadow: it is what blew the fire out before, and it also
            # kills the monster's own shadow (see AGENTS.md eye policy).
        entries[name] = meta

    # Drop accidental mat/textures.json stubs from earlier experiments.
    for stub in (MAT / "textures.json", MAT_DEV / "textures.json"):
        if stub.is_file() and stub.stat().st_size < 2048:
            stub.unlink()

    patch_global(entries)
    overlay_scene = (
        ROOT
        / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes"
        / "d64renemyg_map98"
        / "textures.json"
    )
    for path in (ENEMY_GALLERY_SCENE, overlay_scene):
        path.parent.mkdir(parents=True, exist_ok=True)
        upsert_json(path, entries, replace=False)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SPR_DIR.mkdir(parents=True, exist_ok=True)
    # ZSCRIPT/MAPINFO defined the LSGL glow actor + its EventHandler, and
    # LSGLA0 was its sprite. All three are gone with the blob; leaving any of
    # them behind would keep spawning the ball or dangle AddEventHandlers at a
    # class that no longer exists.
    for stale in ("DECORATE", "ZSCRIPT", "MAPINFO"):
        p = OUT_DIR / stale
        if p.exists():
            p.unlink()
    for stale_spr in SPR_DIR.glob("LSGL*.png"):
        stale_spr.unlink()

    lumps = wad_lumps()
    n = 0
    names: list[str] = []
    no_offset: list[str] = []
    for name, data in lumps.items():
        if not name.startswith("SKUL"):
            continue
        img = open_img(data)
        if img is None:
            continue
        toned = tone_skul_albedo(img)
        # Carry the original sprite offset across the PIL round-trip, or the
        # replacement renders sunk into the floor. See png_set_grab().
        grab = read_grab(data)
        spr = SPR_DIR / f"{name}.png"
        toned.save(spr)
        if grab is None:
            no_offset.append(name)
        else:
            spr.write_bytes(png_set_grab(spr.read_bytes(), *grab))
        save_albedo(name, toned)
        names.append(name)
        n += 1

    write_skul_meta(names)

    if no_offset:
        # Loud, because a silently offset-less sprite is exactly the failure
        # this pass exists to prevent.
        print(f"WARNING: {len(no_offset)} SKUL lump(s) had no grAb: {', '.join(no_offset)}")

    if OUT_PK3.exists():
        OUT_PK3.unlink()
    with zipfile.ZipFile(OUT_PK3, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SPR_DIR.glob("*.png")):
            z.write(p, arcname=f"sprites/{p.name}")
    lit = sum(1 for x in names if x[4:5].upper() in SKUL_LIT_FRAMES)
    print(
        f"wrote {OUT_PK3} ({n} SKUL sprites, all with grAb; "
        f"{lit} fire frames lit at light={SKUL_LIGHT} emis={SKUL_EMIS})"
    )


if __name__ == "__main__":
    main()
