"""
Generate RT emissive + attached-light meta for Retribution FX sprites.

- Idle barrels (BAR1*): poison green glow/light
- Barrel boom (BEXP*): toxic green (not rocket orange)
- Rockets (MISL*): keep fire orange (shared MISL boom also used by 64BarrelExplosion)
- Projectiles / enemy shots / weapon flashes / torches / pickups: color from sprite
  sample + category intensity defaults (stock RT patterns where known)
- Monster gun fire frames (POSSF/SPOSF/CPOSF/…): brief attached muzzle light around the
  shooter. Player weapons get RT_AddMuzzleFlash via A_Light1/2 extralight; monsters do not.

Writes/merges into:
  build/RelWithDebInfo/rt/data/textures.json
  build/.../scenes/d64rtr_v15_map01/textures.json  (upsert)
  Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_fx.json
"""
from __future__ import annotations

import io
import json
import re
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
IWAD = Path(r"D:\Games\GZDoom\doom2.wad")
BM_PK3 = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
RT_DATA = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data"
GLOBAL_JSON = RT_DATA / "textures.json"
SCENE_JSON = RT_DATA / r"scenes\d64rtr_v15_map01\textures.json"
OVERLAY_FX = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_fx.json"
OVERLAY_SCENE = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json"
)
MAT_DIR = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OVERLAY_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"

# Forced profiles (override sampling). HEX without '#'.
#
# NO noShadow ON THE BARRELS, and the intensity stays low. Reported as
# screen/barrelsBlinkFizzle.png: white speckles crawling across the sprite in a
# band at mid-height, on top of a core blown out to white.
#
# That band is where RTGL1 puts the light. MakeLightsForPrimitive() merges the two
# triangles of a sprite quad into ONE sphere light at the average of their
# centroids -- the geometric centre of the sprite. With noShadow the quad cannot
# occlude it, so a 520-intensity light illuminates its own surface from a distance
# of about zero, the 1/r^2 term explodes, and the few samples that land there are
# far too hot for the denoiser to resolve. They survive as speckles, and they move
# because the sampling jitters every frame.
#
# The _e mask proves it is not the art: BAR1A0_e is 3.3% coverage confined to rows
# 0..20 of 50 -- the TOP of the sprite -- peaking at 224 with no saturated pixel.
# It cannot produce a white core in the MIDDLE. (The small bright patch at the very
# top of the reported screenshot IS the mask; the blob below it is the light.)
#
# This is pitfall 4 for the third time in this generator: the Lost Soul and the
# rocket HUD flash were both "lightIntensity plus noShadow on the same sprite",
# and both were fixed by removing noShadow -- "noShadow is the part that blows
# out". Barrels kept both because they came in through FORCE rather than through
# PREFIX_RULES, which is also why line ~577's no_shadow=True never applied to them.
#
# 180/150 is roughly where these sat before bump_bar1_light.py took them to
# 420/360 and this table to 520/420. A sphere light coplanar with a flat quad is a
# degenerate case that self-shadowing alone does not fix, so the intensity has to
# come down as well as the flag coming off.
#
# emissiveMult is deliberately UNCHANGED -- it is the authored green glow, it is
# what the blink reads as, and at 3.3% coverage it was never the fizzle.
FORCE: dict[str, dict] = {
    # Poison barrel idle — classic GLDEFS BARREL is green
    "BAR1A0": {
        "emissiveMult": 1.6,
        "lightIntensity": 180,
        "lightColorHEX": "3dff4a",
    },
    "BAR1B0": {
        "emissiveMult": 1.4,
        "lightIntensity": 150,
        "lightColorHEX": "2ecc40",
    },
    # Green and blue armor. Here rather than in PREFIX_RULES because the light has to
    # differ PER FRAME, which a prefix cannot express -- the same reason the barrel
    # above is here. Being in FORCE also means the entry ships exactly as written, so
    # these never pick up the `noShadow` that main() adds to prefix-matched FX (see
    # the note at the end of this block).
    #
    # WHY THE LIGHT BLINKS, AND WHY A IS THE BRIGHT ONE. Asked for in play: the
    # sprites blink, so should the light. It costs nothing -- the attached light is a
    # property of the TEXTURE, so tying it to the frame syncs it by construction, with
    # no thinker and no phase to keep.
    #
    # The phase is the part worth checking rather than assuming, because vanilla marks
    # the B frame `bright` (ARM1 A 6 / ARM1 B 7 bright; ARM2 A 6 / ARM2 B 6 bright) and
    # that is the OPPOSITE of what RT shows. Measured, per pixel, A against B:
    #
    #     alpha masks identical, ZERO pixels brighter in B
    #     per-pixel B/A luminance   ARM1 median 0.424   ARM2 median 0.478
    #     whole-sprite output       ARM1 A = 2.29x B    ARM2 A = 2.13x B
    #
    # So B is a flat ~0.44x darkening of the same art -- the classic palette-shift
    # blink, a whole-sprite brightness pulse with no moving highlight anywhere in it.
    # Vanilla pairs that darker paint with fullbright so it reads as a twinkle under
    # sector light. Under RT there is no such pairing: forceSpriteUnlitAlbedo
    # (rt_draw.cpp) drops lightlevel from sprite vertex colour and the path tracer
    # lights the billboard, so the `bright` flag does nothing and what the player sees
    # is the paint. A is therefore the bright frame ON SCREEN, and the light follows
    # the screen, not the flag.
    #
    # The ratios are the art's own: 160/2.29 = 70, 200/2.13 = 94. The HUE does not
    # change between frames (sampled 145.7 vs 147.1 deg for ARM1, 214.3 vs 213.7 for
    # ARM2) and must not be made to -- a hue that moves with the blink reads as colour
    # flicker rather than a pulse. Only intensity carries it.
    #
    # emissiveMult stays flat at 0.6 on both frames on purpose: the sprite's own glow
    # is baseColor * emissiveMult, and baseColor already carries the 2.29x, so the
    # GLOW blinks in time for free. The attached light was the only part that was a
    # fixed number and therefore the only part that needed the second value.
    #
    # Rate is the sprite's own: 13 tics for green (0.371 s, 2.7 Hz), 12 for blue
    # (0.343 s, 2.9 Hz). That is fast for a light, and the SMONBA monitors are the
    # warning next door -- but they were 199 fixtures pulsing in phase across a wall,
    # and this is 39 pickups over 34 maps, about one per level. If it reads as too
    # busy, raise the B values toward A (a 1.5x swing is 105 and 133); do not slow it,
    # because the sprite's rhythm is not ours to change.
    #
    # NO `noShadow` ON ANY OF THESE. It was on the first version, copied from the key
    # profile, and was reported straight back as the armors no longer casting a
    # flashlight shadow. The flag is not scoped to the sprite's own light: TextureMeta
    # turns it into RG_MESH_PRIMITIVE_NO_SHADOW, the primitive lands in PV_WORLD_1,
    # and rayCullMaskWorld_Shadow is WORLD_0|RESERVED_0 -- invisible to EVERY shadow
    # ray in the scene. The other pickups keep it because their attached light sits at
    # the quad's centre, in the billboard's own plane, so an occluding billboard can
    # shadow its own light; the armors are the case where the missing shadow is the
    # worse artefact. See docs/sprite-illumination.md Case 11.
    "ARM1A0": {
        "emissiveMult": 0.6,
        "lightIntensity": 160,
        "lightColorHEX": "44ff88",
    },
    "ARM1B0": {
        "emissiveMult": 0.6,
        "lightIntensity": 70,
        "lightColorHEX": "44ff88",
    },
    "ARM2A0": {
        "emissiveMult": 0.6,
        "lightIntensity": 200,
        "lightColorHEX": "4488ff",
    },
    "ARM2B0": {
        "emissiveMult": 0.6,
        "lightIntensity": 94,
        "lightColorHEX": "4488ff",
    },
}

# Unmaker laser — beam, muzzle flash and impact puff all share one hex.
UNMAKER_RED = "ff1408"

# Shared flame palette. Every torch/flame in the game draws from these four, so a colour
# fix lands everywhere at once. Each is within 10 deg of its measured sprite art and
# matches the mod's own GLDEFS intent (TORCHLONG*/TORCHSHORT*/*TORCH) without GLDEFS'
# fully-primary saturation, which bleaches under path tracing.
# tools/gen_torch_emissives.py mirrors these for the TL*/TS* standing torches — keep the
# two in step (the LPUF regression happened exactly this way).
FLAME_BLUE = "4488ff"
FLAME_GREEN = "44ff66"
FLAME_RED = "ff4020"
FLAME_YELLOW = "ffcc33"

# Prefix rules: (emissiveMult, lightIntensity, optional forced HEX or None=sample)
# Intensity 0 => emissive only (no analytic light).
# Do NOT add SKUL* here — owned by gen_enemy_eye / pack_lostsoul_rt.
PREFIX_RULES: list[tuple[str, float, float, str | None]] = [
    # barrels / toxic boom
    # Dead for BAR1A0/BAR1B0, which FORCE owns -- kept in step with FORCE so a new
    # barrel frame does not silently arrive at 480 + no_shadow=True (line ~577
    # applies noShadow to everything that comes through THIS table) and bring the
    # mid-sprite fizzle back. See the FORCE note.
    ("BAR1", 1.5, 180, "3dff4a"),
    ("BEXP", 0.65, 2400, "66ff44"),  # toxic green boom
    # rockets / barrel secondary boom (fire) — keep orange
    ("MISL", 0.45, 2200, "ff9a40"),
    ("MISL", 0.4, 1400, "ffaa44"),  # rocket in flight
    ("MISF", 0.25, 0, "ffb060"),  # rocket launcher HUD flash — no same-sprite light
    # imp / hell projectiles
    ("BAL1", 0.35, 700, "ff6f00"),
    # 64CacodemonBall. Was "b65cff" — a pale violet inherited from stock RTGL1's own
    # BAL2A0/B0 entries. The sprite is red-orange (flight frames avg (99,24,8), hot core
    # aside), so the cast light read near-white lavender on a red projectile. Normalized
    # art is ff3e14; lifted a little so lit surfaces don't go blood-dark.
    ("BAL2", 0.35, 900, "ff5a28"),
    # 64NightmareImpBall. The sprite is violet — its brightest texels are (88,48,184),
    # peak-normalizing to ~7a42ff — so the orange-red ff5533 this used to carry lit the
    # room like an ordinary fireball while the projectile itself read purple. Lifted a
    # little off the raw art so lit surfaces read violet rather than near-black blue.
    ("BAL3", 0.35, 800, "9a5cff"),
    ("BAL7", 0.35, 1000, "66ff55"),  # baron green
    # 64BaronBall2 — same miss as BAL2, opposite direction. BAL8 is BAL7 recoloured RED
    # (brightest texels (248,48,0) on the death frames, (248,104,80) in flight); it was
    # pinned green "88ff66" because it shares BAL7's frame layout, so the hell-knight
    # shot lit rooms baron-green.
    ("BAL8", 0.35, 1000, "ff4a20"),
    # 64MotherBall (Mother Demon). Deep red — the art has literally zero blue and the
    # death frames normalize to ff0000. The old "ff4040" carried equal G and B, so it
    # washed pink/white rather than reading red.
    ("RBAL", 0.4, 1100, "ff2606"),
    # 64TracerMissile. Orange, not tan: flight frames normalize to ~ff8840 and the death
    # frames redden to ff5e1f. "ffaa55" was pale enough to read yellow-cream.
    ("TRCR", 0.45, 1200, "ff8a38"),
    ("RECT", 0.25, 400, "ff8844"),  # revenant missile trail-ish
    ("MANF", 0.4, 1200, "ff8c20"),  # 64FatShot — orange, matches its art (ff7b3c..ff8229)
    # 64ArachnotronPlasma is BLUE-VIOLET: every frame has r == g with a dominant blue
    # (APLSA0 (43,43,111) → 6262ff). "88fa84" green was a straight mis-pin.
    ("APLS", 0.4, 1000, "6666ff"),
    # APBX is the vanilla plasma boom and is unreachable in Retribution — the mod's
    # 64ArachnotronPlasma REPLACES the stock actor and fades out on APLSE0–H0 instead.
    # Kept in step with APLS so it cannot flash green if a vanilla actor ever spawns.
    ("APBX", 0.4, 1200, "6666ff"),
    ("FATB", 0.35, 900, "ff7020"),
    # plasma / bfg
    # Plasma bolt + impact. Measured down from 0.45/900-1100, which was the real cause
    # of "the weapon is invisible while shooting": at point-blank the bolt's glare is a
    # screen-filling white disc that swallows the gun, and sustained fire keeps one on
    # screen permanently (screen/weapon_probe_plasma-auto_v2 vs _fxlow). Colour also
    # moved off the old cyan 55aaff/66bbff — see PLASMA_BLUE in gen_hud_gun_emissive.py.
    ("PLSS", 0.15, 300, "3355ff"),
    ("PLSE", 0.15, 300, "3355ff"),
    # No PLSG / PLSF / BFGG rule here — tools/gen_hud_gun_emissive.py owns those.
    # They are all first-person GUN BODY sprites (Retribution's PLSF frames are the
    # whole rifle drawn on the WEAPON layer during Fire, not a small muzzle overlay),
    # and a blanket emissiveMult makes the WHOLE gun emit: solid white on a dark
    # backdrop (screen/plasmagunissue.png, screen/bfgbug.png), see-through on a bright
    # one (screen/plasmariflegettingtransparent.png). They get a core-masked _e map
    # instead, so only the electric core emits. Run that tool after this one.
    ("CPLS", 0.15, 300, "3355ff"),
    ("BFS1", 0.5, 3000, "66ff33"),
    ("BFE1", 0.5, 3000, "66ff33"),
    ("BFE2", 0.45, 2500, "66ff33"),
    ("BFGF", 0.3, 0, "66ff33"),  # HUD BFG flash
    ("CBFG", 0.8, 1600, "66ff33"),
    ("CRCK", 0.5, 1400, "ffaa33"),  # custom rocket-ish
    # puffs / fog
    ("PUFF", 0.6, 250, "ffd0a0"),
    ("PUF2", 0.5, 220, "ffd0a0"),
    ("PUF3", 0.5, 220, "ffd0a0"),
    # Unmaker laser puff. Never blue — the old "aaccff" was fixed in the JSON by hand
    # (see docs/sprite-illumination.md) but the rule here was left stale, so a re-run of
    # this tool would have reverted it. It is also not orange: "f15a26" came from the
    # few hot rim texels, while the mass of the sprite normalizes to ff4004 / ff0d04.
    # Shares UNMAKER_RED with UNMF/UNML below — one weapon, one colour.
    ("LPUF", 0.55, 300, UNMAKER_RED),
    ("TFOG", 0.75, 1200, "40ff40"),  # Retribution 64TeleportFog — GLDEFS DTFOG is green
    # 64ItemFog is BLUE, not a second green teleport fog. Its texels carry zero red and
    # near-zero green (brightest (0,57,247), normalizing to 0000ff-000cff); the old
    # "66ffaa" mint came from assuming it matched TFOG. Lifted a touch off pure blue so
    # it is not a single-channel light.
    ("IFOG", 0.65, 1000, "1a44ff"),
    # weapon HUD flashes — low emissiveMult (1.0 bleached PISF pure white under PT).
    # Scene cast comes from engine RT_AddMuzzleFlash (rt_mzlflsh*); same-sprite
    # lightIntensity bleaches the HUD flash (Lost Soul lesson) — keep 0 here.
    ("PISF", 0.22, 0, "ffcc88"),
    ("SHTF", 0.22, 0, "ffcc88"),
    ("SSGF", 0.25, 0, "ffcc88"),
    ("CHGF", 0.22, 0, "ffcc88"),
    ("CLCG", 0.22, 0, "66bbff"),
    ("CPIS", 0.22, 0, "ffcc88"),
    ("CSHT", 0.22, 0, "ffcc88"),
    ("CSSG", 0.25, 0, "ffcc88"),
    ("RLFT", 0.2, 0, "ff8844"),
    ("PUNF", 0.2, 0, "ffcc88"),
    ("SAWG", 0.15, 0, "ffcc88"),
    # unmaker / custom beams (world/projectile — keep some attached light).
    # The Unmaker fires a PURE RED laser: UNMLA0 is literally (255,0,0), UNMFA0
    # normalizes to ff0b08. The old ff3366 / ff2255 were pink — enough magenta to read
    # wrong on white walls. UNMAKER_RED keeps a token 20/8 of G/B so the light is not a
    # degenerate single-channel source.
    ("UNMF", 0.35, 900, UNMAKER_RED),
    ("UNML", 0.3, 800, UNMAKER_RED),
    # --- OPEN FLAMES: emissive only, intensity 0 on purpose ------------------------
    # Everything from here to CAND is a real fire, and every one of them is lit by the
    # engine now, by RT_UploadFlameLights in rt_main.cpp (cvar rt_flame_light_on), NOT by
    # the attached light below. Two things texture meta cannot express:
    #   * OFFSET. RTGL1 puts a sprite light at the centre of the billboard quad, so a
    #     100-unit torch lit itself from the midriff. GLDEFS lifts these 8..80 units up
    #     onto the flame and there is no offset field here.
    #   * FLICKER. Meta is static, and the props all spawn at map load, so a per-frame
    #     intensity ramp would pulse every torch in the level in lockstep.
    # The intensities are kept in the rows as documentation of the old balance; a 0 in the
    # intensity column writes `lightIntensity: 0`, which casts nothing (same convention as
    # the muzzle flashes above). emissiveMult stays: the flame must still glow on screen.
    # If you ever re-attach a light here, delete the engine entry in RT_FLAME_KINDS in the
    # same commit or the flame gets lit twice, from two different places.
    ("A030", 0.35, 0, None),  # was 700 -> engine (RT_FLAME_YELLOW, +24u)
    ("A031", 0.35, 0, None),  # was 700 -> engine (RT_FLAME_BLUE,   +24u)
    ("A032", 0.35, 0, None),  # was 700 -> engine (RT_FLAME_RED,    +24u)
    # torches / flames
    # 64BigFire, and the Mother Demon's fireball + trail, which share the sprite. This DID
    # carry its attached light on the grounds that it "is not a GLDEFS flame prop" — wrong:
    # the WAD has `flickerlight BIGFIRE { size 32 offset 0 32 0 }` bound to frame FIRE on
    # all three actors. 117 placements across nine maps, so this was the biggest hole in
    # the flame work. The mask keeps ff8020 and RT_FLAME_BIGFIRE matches it.
    ("FIRE", 0.7, 0, "ff8020"),  # was 700 -> engine (RT_FLAME_BIGFIRE, +32u)
    ("BFLM", 0.8, 0, FLAME_BLUE),    # was 650 -> engine, +8u
    ("RFLM", 0.8, 0, FLAME_RED),     # was 650 -> engine, +8u
    ("YFLM", 0.8, 0, FLAME_YELLOW),  # was 650 -> engine, +8u
    ("GFLM", 0.8, 0, FLAME_GREEN),   # was 650 -> engine, +8u
    # Wall torches. These ARE drawn BRIGHT (`GTCH ABCDE 4 BRIGHT`) and are almost all
    # flame, so a blanket emissiveMult is safe. The TL*/TS* standing torches are not —
    # see tools/gen_torch_emissives.py, which owns those 40 sprites. Do not add TL/TS
    # prefixes here.
    ("GTCH", 0.7, 0, FLAME_GREEN),  # was 500 -> engine (RT_FLAME_GREEN, +24u)
    # The candle's light was ffaa55 @ 280 — a straight amber, the same hue family as a
    # pitch torch four times its size. A candle is one wick: the engine gives it a warm
    # red (RT_FLAME_CANDLE ff4a14) at 260, so it reads as a dim ember rather than a small
    # torch. Art check: CAND?0 is 8x31, brightest texel (232,168,0), but that amber is the
    # wax body catching the light as much as the flame itself.
    ("CAND", 0.5, 0, "ffaa55"),  # was 280 -> engine (RT_FLAME_CANDLE, +16u)
    # pickups (soft glow)
    ("ART1", 0.6, 220, "66ffaa"),
    ("ART2", 0.6, 220, "66aaff"),
    ("ART3", 0.6, 220, "ff66aa"),
    ("PINS", 0.5, 200, "66ff99"),
    ("PINV", 0.5, 200, "aaaaff"),
    ("SOUL", 0.6, 260, "4488ff"),
    ("MEGA", 0.7, 300, "8866ff"),
    ("SUIT", 0.35, 120, "44ff66"),
    ("BKEY", 0.6, 160, "4488ff"),
    ("RKEY", 0.6, 160, "ff4444"),
    ("YKEY", 0.6, 160, "ffcc33"),
    ("BSKU", 0.6, 160, "4488ff"),
    ("RSKU", 0.6, 160, "ff4444"),
    ("YSKU", 0.6, 160, "ffcc33"),
]


# Monster fire frames only (…F). Aim frames (…E) must stay dark.
# Color matches player rt_mzlflsh_color (0xFF8C52). No noShadow — that kills enemy shadows.
# Intensities below HUD weapon flashes so body-centered lights do not lantern.
MONSTER_MUZZLE_RULES: list[tuple[str, float, float, str | None]] = [
    ("POSSF", 0.35, 480, "ff8c52"),  # Zombieman
    ("SPOSF", 0.4, 720, "ff8c52"),  # ShotgunGuy
    ("CPOSF", 0.35, 520, "ff8c52"),  # ChaingunGuy (IWAD sprites)
    ("PLAYF", 0.35, 480, "ff8c52"),  # 64MarineBot + player world fire frames
    ("SSWVF", 0.35, 480, "ff8c52"),  # WolfensteinSS
]


def wad_images(path: Path) -> dict[str, bytes]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz <= 0:
            continue
        out[nm] = d[off : off + sz]
    return out


def open_sprite(data: bytes) -> Image.Image | None:
    if len(data) < 16:
        return None
    # PNG / other PIL formats
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def sample_hex(img: Image.Image) -> str | None:
    """Average of bright / saturated opaque pixels → RRGGBB."""
    px = img.getdata()
    acc = [0, 0, 0]
    n = 0
    for r, g, b, a in px:
        if a < 40:
            continue
        s = r + g + b
        if s < 180:
            continue
        # prefer saturated / bright
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx < 60:
            continue
        if (mx - mn) < 25 and s < 420:
            continue
        w = 1 + (mx - mn) // 40 + s // 300
        acc[0] += r * w
        acc[1] += g * w
        acc[2] += b * w
        n += w
    if n < 8:
        # fallback: any opaque above mid
        for r, g, b, a in px:
            if a < 40:
                continue
            if r + g + b < 120:
                continue
            acc[0] += r
            acc[1] += g
            acc[2] += b
            n += 1
    if n <= 0:
        return None
    r, g, b = (min(255, acc[i] // n) for i in range(3))
    # boost saturation a bit for light color
    mx = max(r, g, b) or 1
    scale = 255 / mx
    r, g, b = (min(255, int(c * scale * 0.92)) for c in (r, g, b))
    return f"{r:02x}{g:02x}{b:02x}"


def make_emissive_png(img: Image.Image, out: Path, boost: float = 1.4) -> None:
    """Keep bright pixels, kill dark — simple _e companion."""
    px = list(img.getdata())
    out_px = []
    for r, g, b, a in px:
        if a < 40:
            out_px.append((0, 0, 0, 0))
            continue
        s = r + g + b
        if s < 200:
            out_px.append((0, 0, 0, 0))
            continue
        # emphasize channel dominance
        out_px.append(
            (
                min(255, int(r * boost)),
                min(255, int(g * boost)),
                min(255, int(b * boost)),
                a,
            )
        )
    e = Image.new("RGBA", img.size)
    e.putdata(out_px)
    out.parent.mkdir(parents=True, exist_ok=True)
    e.save(out)


# Doom II WORLD fire/lava textures — NOT archvile flame sprites. The FIRE
# prefix rule must not swallow these: they got lightIntensity 700 + noShadow
# on a world texture (wash + killed wall shadows). Owned by world emis if wanted.
WORLD_TEX_RE = re.compile(r"^(FIRELAV|FIREWAL|FIREMAG|FIREBLU|FIREWALL)", re.I)


def rule_for(name: str) -> tuple[float, float, str | None] | None:
    u = name.upper()
    if WORLD_TEX_RE.match(u):
        return None
    for pref, em, li, hx in PREFIX_RULES:
        if u.startswith(pref):
            return em, li, hx
    return None


def monster_muzzle_rule(name: str) -> tuple[float, float, str | None] | None:
    u = name.upper()
    for pref, em, li, hx in MONSTER_MUZZLE_RULES:
        if u.startswith(pref):
            return em, li, hx
    return None


def fx_meta(
    name: str,
    em: float,
    li: float,
    color: str,
    *,
    no_shadow: bool,
) -> dict:
    meta: dict = {
        "textureName": name,
        "emissiveMult": em,
        "lightColorHEX": color,
    }
    # Omit lightIntensity when 0 — HUD flashes use rt_mzlflsh; same-sprite light bleaches white.
    if li > 0:
        meta["lightIntensity"] = li
    if no_shadow:
        meta["noShadow"] = True
    return meta


def parse_textures_json(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        if "//" in line:
            line = line[: line.index("//")]
        lines.append(line)
    text = "\n".join(lines)
    out: dict[str, dict] = {}
    for m in re.finditer(r"\{([^{}]+)\}", text):
        body = m.group(1)
        if "textureName" not in body:
            continue
        entry: dict = {}
        for km in re.finditer(
            r'"(\w+)"\s*:\s*("([^"]*)"|true|false|-?\d+(?:\.\d+)?)', body
        ):
            k, raw = km.group(1), km.group(2)
            if raw.startswith('"'):
                entry[k] = km.group(3)
            elif raw in ("true", "false"):
                entry[k] = raw == "true"
            else:
                entry[k] = float(raw) if "." in raw else int(raw)
        name = entry.get("textureName")
        if name:
            out[str(name)] = entry
    return out


def upsert_json(path: Path, entries: dict[str, dict], replace: bool = False) -> None:
    if path.exists() and not replace:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # stock-style with comments — rebuild from parsed + merge
            parsed = parse_textures_json(path)
            data = {"version": 0, "array": list(parsed.values())}
    else:
        data = {"version": 0, "array": []}
    by = {e["textureName"]: dict(e) for e in data.get("array", []) if "textureName" in e}
    for name, meta in entries.items():
        cur = by.get(name, {"textureName": name})
        cur.update(meta)
        cur["textureName"] = name
        # Authored meta without lightIntensity must clear stale attached lights.
        # ...and the same for noShadow, for the same reason. An upsert can ADD a
        # key but never REMOVE one, so a flag deleted at the source lives forever
        # in every overlay it already reached. That is exactly how the barrels
        # kept noShadow after it came off FORCE: the global JSON lost it, MAP01's
        # scene overlay kept it, and scene overlays WIN -- so the fizzle would have
        # survived the fix on the one map you see barrels first.
        # Any key this generator owns must be cleared when the new meta omits it.
        for owned in ("lightIntensity", "noShadow"):
            if owned not in meta:
                cur.pop(owned, None)
        by[name] = cur
    data["version"] = data.get("version", 0)
    data["array"] = list(by.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def patch_global_inline(path: Path, entries: dict[str, dict]) -> None:
    """Overwrite first textureName hit in stock textures.json (keeps comments).

    RTGL keeps the *first* textureName hit — appending trailing one-liners while
    an earlier pretty-printed stock block still has lightIntensity does nothing.
    """
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for name, meta in entries.items():
        parts = [f'"textureName":"{name}"']
        for k, v in meta.items():
            if k == "textureName":
                continue
            if isinstance(v, bool):
                parts.append(f'"{k}":{"true" if v else "false"}')
            elif isinstance(v, float) and v == int(v):
                parts.append(f'"{k}":{int(v)}')
            elif isinstance(v, (int, float)):
                parts.append(f'"{k}":{v}')
            else:
                parts.append(f'"{k}":"{v}"')
        body = "  ,".join(parts)

        def repl_line(m: re.Match[str]) -> str:
            lead = m.group(1) or "    ,   "
            return f"{lead}{{ {body} }}"

        pat = re.compile(
            rf'^([ \t]*,?[ \t]*)\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}"[^}}\n]*\}}[ \t]*$',
            re.M,
        )
        if pat.search(text):
            text = pat.sub(repl_line, text, count=1)
        else:
            # Pretty-printed multiline object — replace whole first block.
            #
            # The comma after the name is OPTIONAL, and that is not a nicety: an
            # entry carrying no other fields is written `{ "textureName": "X" }`
            # across three lines with nothing after the name. ARM1A0 and ARM2A0 were
            # exactly that, so neither this pattern nor the single-line one above
            # matched them, and the armor pickups fell through to the append branch
            # (which bug 2 below then ate). Net effect: the generator reported
            # success and wrote nothing at all — four entries missing with no error
            # anywhere. Any bare entry hits this; the armors were just the first to
            # be given fields.
            pat_multi = re.compile(
                rf'(\{{\s*\n\s*"textureName"\s*:\s*"{re.escape(name)}"\s*,?)(.*?)(\n\s*\}})',
                re.S,
            )
            mm = pat_multi.search(text)
            if mm:
                indent = "      "
                lines = [f'{{\n{indent}"textureName": "{name}",']
                keys = [k for k in meta if k != "textureName"]
                for i, k in enumerate(keys):
                    v = meta[k]
                    comma = "," if i < len(keys) - 1 else ""
                    if isinstance(v, bool):
                        lines.append(f'{indent}"{k}": {"true" if v else "false"}{comma}')
                    elif isinstance(v, float) and v == int(v):
                        lines.append(f'{indent}"{k}": {int(v)}{comma}')
                    elif isinstance(v, (int, float)):
                        lines.append(f'{indent}"{k}": {v}{comma}')
                    else:
                        lines.append(f'{indent}"{k}": "{v}"{comma}')
                lines.append("    }")
                text = text[: mm.start()] + "\n".join(lines) + text[mm.end() :]
            else:
                line = f"    ,   {{ {body} }}"
                text = re.sub(r"\n(\s*\]\s*\}\s*)$", "\n" + line + r"\n\1", text, count=1)
        # Drop any LATER single-line duplicates for this name.
        #
        # "Later" has to be measured against the first occurrence in the file, and
        # this used to drop every match unconditionally — including the one the
        # append branch had just written three lines above, when that was the only
        # entry for the name. Appending and then immediately deleting reads as a
        # clean run: the generator prints the entry in its summary, the file never
        # gets it. RTGL keeps the FIRST hit, so the rule is drop-after-the-first,
        # not drop-all.
        first = re.search(
            rf'"textureName"\s*:\s*"{re.escape(name)}"', text
        )
        if first:
            dup = re.compile(
                rf'^\s*,\s*\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}"[^}}\n]*\}}\s*$\n?',
                re.M,
            )
            text = dup.sub(
                lambda m: "" if m.start() > first.start() else m.group(0), text
            )
    path.write_text(text, encoding="utf-8")


def brightmap_names() -> set[str]:
    names: set[str] = set()
    if not BM_PK3.exists():
        return names
    with zipfile.ZipFile(BM_PK3) as z:
        for n in z.namelist():
            if n.endswith("/"):
                continue
            stem = Path(n).stem.upper()
            # brightmaps often named after texture
            names.add(stem)
            if stem.startswith("BRIGHTMAP") or stem.startswith("BM_"):
                continue
            names.add(stem)
    return names


def main() -> None:
    lumps = wad_images(WAD)
    if IWAD.exists():
        # Chaingunner / Wolf SS fire frames live in the IWAD, not Retribution.
        for name, data in wad_images(IWAD).items():
            if monster_muzzle_rule(name) and name not in lumps:
                lumps[name] = data
    # candidates = anything matching a prefix rule, present as a lump
    candidates: list[str] = []
    for name in lumps:
        if rule_for(name) or monster_muzzle_rule(name) or name in FORCE:
            # skip HUD-only
            if name.endswith("HUD"):
                continue
            candidates.append(name)
    candidates = sorted(set(candidates))

    entries: dict[str, dict] = {}
    e_png = 0
    by_pref: dict[str, int] = defaultdict(int)

    for name in candidates:
        if name in FORCE:
            meta = {"textureName": name, **FORCE[name]}
            entries[name] = meta
            by_pref[name[:4]] += 1
            continue

        mz = monster_muzzle_rule(name)
        if mz:
            em, li, hx = mz
            color = hx or "ff8c52"
            entries[name] = fx_meta(name, em, li, color, no_shadow=False)
            by_pref[name[:5] if len(name) >= 5 else name[:4]] += 1
            continue

        rule = rule_for(name)
        if not rule:
            continue
        em, li, hx = rule
        img = open_sprite(lumps[name])
        sampled = sample_hex(img) if img else None
        color = hx or sampled or "ffffff"
        # If brightmap exists and we forced no hex, prefer sample
        if hx is None and sampled:
            color = sampled

        entries[name] = fx_meta(name, em, li, color, no_shadow=True)
        by_pref[name[:4]] += 1

        # Write _e.png for idle barrels + a few hero FX (devMode PNGs)
        if img and name.startswith(("BAR1", "BEXP", "BAL7", "BAL8", "GFLM", "APLS")):
            for d in (MAT_DIR, MAT_DEV, OVERLAY_MAT):
                d.mkdir(parents=True, exist_ok=True)
                make_emissive_png(img, d / f"{name}_e.png")
            e_png += 1

    # Also bump stock entries that are emis-only weapon flashes / MISL body if still weak
    stock = parse_textures_json(GLOBAL_JSON)
    for name, e in stock.items():
        if name in entries:
            continue
        mz = monster_muzzle_rule(name)
        if mz:
            em, li, hx = mz
            entries[name] = fx_meta(name, em, li, hx or "ff8c52", no_shadow=False)
            by_pref[name[:5] if len(name) >= 5 else name[:4]] += 1
            continue
        rule = rule_for(name)
        if not rule:
            continue
        em, li, hx = rule
        if e.get("lightIntensity"):
            continue
        # overwrite stock with authored FX profile (do not keep old high emisMult)
        entries[name] = fx_meta(
            name,
            em,
            li,
            hx or e.get("lightColorHEX") or "ffffff",
            no_shadow=True,
        )
        by_pref[name[:4]] += 1

    print(f"FX metas: {len(entries)}  _e.png: {e_png}")
    for k in sorted(by_pref, key=lambda x: -by_pref[x])[:30]:
        print(f"  {k}: {by_pref[k]}")
    print("BAR1", entries.get("BAR1A0"), entries.get("BAR1B0"))
    print("BEXPC0", entries.get("BEXPC0"))
    print("BAL7A1A5", entries.get("BAL7A1A5"))
    print("RBALA1", entries.get("RBALA1"))
    print("TRCRA1", entries.get("TRCRA1"))
    print("POSSF1", entries.get("POSSF1"))
    print("SPOSF1", entries.get("SPOSF1"))
    print("CPOSF1", entries.get("CPOSF1"))
    print("PLAYF1", entries.get("PLAYF1"))
    print("PUFFA0", entries.get("PUFFA0"))
    print("PISFA0", entries.get("PISFA0"))

    patch_global_inline(GLOBAL_JSON, entries)
    upsert_json(SCENE_JSON, entries, replace=False)
    upsert_json(OVERLAY_FX, entries, replace=True)
    if OVERLAY_SCENE.exists():
        upsert_json(OVERLAY_SCENE, entries, replace=False)

    # Keep explosion-only overlay in sync conceptually
    print("done ->", GLOBAL_JSON)
    print("overlay ->", OVERLAY_FX)


if __name__ == "__main__":
    main()
