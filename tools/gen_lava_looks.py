"""Render candidate LOOKS for a stylized lava shader, as one contact sheet.

Why this exists. HLAVA1-5 (a 5-frame ping-pong, 5 tics each) and D64LAVA1/2
(warp2) get an albedo and a sparse _e emissive mask and nothing else. Under a
path tracer that reads as screen/lavanoemit_needshader.png: a black room with a
thin orange net floating in it. TWO separate things are wrong there and they are
easy to confuse --

  1. the lava lights nothing, so its own brown crust is unlit and therefore
     invisible. Most of what looks like "black lava" is just unlit rock.
  2. the surface is flat. No relief, no temperature, no motion; the cracks are
     painted lines on a plane rather than channels between plates.

Fixing (1) is a light, not a shader. This sheet exists to decide (2), and the
first two panels separate them so the decision is not made on the wrong
evidence.

Every panel is the same geometry, the same source flat and the same projection,
so the only variable is the surface treatment. Each maps to a specific set of
shader knobs -- see the LOOKS table.

This is a MOCKUP. The perspective is a fixed projection with a depth fade, the
room light is a painted gradient tinted by the candidate's own mean emission,
the relief is baked into the tile rather than sampled per pixel, and nothing
here is path traced. It answers "which of these do we want", not "what will it
look like in game".

Usage:
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_lava_looks.py
    ... --tex D64LAVA1 --out somewhere.png
"""

from __future__ import annotations

import argparse
import io
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WAD = ROOT / "Doom64-Retribution/D64RTR_v15.WAD"
MATS = ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat"

PANEL_W, PANEL_H = 660, 420
COLS = 3
PAD = 14
LABEL_H = 58
HORIZON = int(PANEL_H * 0.30)

EXPOSURE = 0.55  # the room in the screenshot is very dark; match it
SS = 3  # supersample: without it the far field is moire, not shading


# ---------------------------------------------------------------------------
# source art
# ---------------------------------------------------------------------------


def read_wad_lump(name: str) -> bytes:
    data = WAD.read_bytes()
    count, tbl = struct.unpack_from("<ii", data, 4)
    for i in range(count):
        off, size = struct.unpack_from("<ii", data, tbl + 16 * i)
        nm = data[tbl + 16 * i + 8 : tbl + 16 * i + 16].rstrip(b"\0").decode("latin1")
        if nm == name and size > 0:
            return data[off : off + size]
    raise SystemExit(f"ERROR: lump {name} not found in {WAD.name}")


def load_source(name: str) -> tuple[np.ndarray, np.ndarray]:
    """(albedo, authored emissive). The _e overlay is what ships today."""
    albedo = np.asarray(
        Image.open(io.BytesIO(read_wad_lump(name))).convert("RGB"), dtype=np.float32
    ) / 255.0

    e_path = MATS / f"{name}_e.png"
    if e_path.exists():
        e = np.asarray(Image.open(e_path).convert("RGB"), dtype=np.float32) / 255.0
        if e.shape[:2] != albedo.shape[:2]:
            e = np.asarray(
                Image.open(e_path).convert("RGB").resize(albedo.shape[1::-1], Image.NEAREST),
                dtype=np.float32,
            ) / 255.0
    else:
        e = np.zeros_like(albedo)
    return albedo, e


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def blur(a: np.ndarray, radius: int, passes: int = 3) -> np.ndarray:
    """Wrapped box blur, repeated for a gaussian-ish falloff. Tiles seamlessly,
    which matters: the flat repeats, so a halo must too."""
    out = a
    for _ in range(passes):
        k = 2 * radius + 1
        pad = np.concatenate([out[-radius:], out, out[:radius]], axis=0)
        cs = np.cumsum(pad, axis=0)
        out = (cs[k - 1 :] - np.concatenate([np.zeros_like(cs[:1]), cs[:-k]], axis=0)) / k
        pad = np.concatenate([out[:, -radius:], out, out[:, :radius]], axis=1)
        cs = np.cumsum(pad, axis=1)
        out = (cs[:, k - 1 :] - np.concatenate([np.zeros_like(cs[:, :1]), cs[:, :-k]], axis=1)) / k
    return out


def crack_mask(albedo: np.ndarray) -> np.ndarray:
    """0..1 mask of the molten cracks, from the art's own REDNESS.

    Not luminance: HLAVA1's crust is a mid brown that is brighter than plenty of
    crack pixels, so a luminance mask returns the rock. The cracks are the only
    strongly red-over-green thing in the flat, which separates them cleanly.
    Not the authored _e either -- that marks only a few of the cracks, so using
    it as the mask would bake today's sparseness into every candidate.
    """
    r, g = albedo[..., 0], albedo[..., 1]
    m = np.clip(r - g * 1.25, 0.0, 1.0)
    m = np.clip(m / max(float(np.percentile(m, 99.0)), 1e-4), 0.0, 1.0)
    # Floor the crust's own red noise away and stretch what is left, or the
    # network sits at 0.2 (dead red) while a handful of blobs pin at 1.0 (white)
    # -- which reads as spatter, not as a crack system.
    return np.clip((m - 0.22) / 0.78, 0.0, 1.0) ** 0.85


def value_noise(shape: tuple[int, int], cells: int, seed: int) -> np.ndarray:
    """Tiling multi-octave value noise, 0..1. The convection field."""
    rng = np.random.default_rng(seed)
    acc = np.zeros(shape, dtype=np.float32)
    amp, total = 1.0, 0.0
    for octave in range(3):
        c = cells * (2**octave)
        grid = rng.random((c, c), dtype=np.float32)
        grid = np.concatenate([grid, grid[:1]], axis=0)
        grid = np.concatenate([grid, grid[:, :1]], axis=1)  # wrap
        yi = np.linspace(0, c, shape[0], endpoint=False, dtype=np.float32)
        xi = np.linspace(0, c, shape[1], endpoint=False, dtype=np.float32)
        y0, x0 = yi.astype(int), xi.astype(int)
        fy, fx = (yi - y0)[:, None], (xi - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)  # smoothstep
        g = grid[np.ix_(y0, x0)]
        gx = grid[np.ix_(y0, x0 + 1)]
        gy = grid[np.ix_(y0 + 1, x0)]
        gxy = grid[np.ix_(y0 + 1, x0 + 1)]
        acc += amp * ((g * (1 - fx) + gx * fx) * (1 - fy) + (gy * (1 - fx) + gxy * fx) * fy)
        total += amp
        amp *= 0.5
    return acc / total


def temper(m: np.ndarray) -> np.ndarray:
    """Squash the top of the crack mask before the heat ramp.

    The mask is normalized on its 99th percentile, so a lot of it pins at 1.0
    and the ramp turns whole cracks white. Real white-hot is the thin core of
    an open channel, not the channel."""
    return np.clip(m, 0.0, 1.0) ** 1.1


def ramp(mask: np.ndarray, stops) -> np.ndarray:
    pos = np.array([s[0] for s in stops], dtype=np.float32)
    cols = np.array([s[1] for s in stops], dtype=np.float32)
    out = np.empty(mask.shape + (3,), dtype=np.float32)
    for c in range(3):
        out[..., c] = np.interp(mask, pos, cols[:, c])
    return out


def srgb(hex_str: str) -> tuple[float, float, float]:
    """#rrggbb as it should LOOK -> linear, which is what the shading uses.

    Worth the detour: a linear (1.0, 0.62, 0.20) sounds like a hot orange and
    displays as pale salmon, because gamma lifts the small channels hard. Every
    hand-picked "orange" in the first three passes of this sheet came out cream
    for exactly that reason. Pick the colour you want to SEE and convert.
    """
    v = [int(hex_str[i : i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


# Temperature ramp: cool crust -> deep red -> orange -> the pale core of an open
# channel. Not a real Planck curve; a real one runs through a washed pink at the
# top that reads as overexposure rather than heat, and it says nothing about
# what the CRUST should be, which is most of the screen.
HEAT = [
    (0.00, srgb("#100402")),
    (0.35, srgb("#4a0e04")),
    (0.60, srgb("#a32908")),
    (0.80, srgb("#ff5a14")),
    (0.93, srgb("#ff9a2a")),
    (1.00, srgb("#ffd46a")),
]

ROCK = np.array(srgb("#3a2a22"), dtype=np.float32)  # cold basalt


# ---------------------------------------------------------------------------
# relief
# ---------------------------------------------------------------------------


def relief(m: np.ndarray, strength: float, depth: float = 1.0):
    """Height and normal for the crust: plates stand proud, cracks are channels.

    Height is 1-mask, so the molten line is the LOW point -- which is what a
    crack is. The normal comes from its gradient. Returned as (height, nx, ny)
    with nz implied 1, because that is all the shading below needs.
    """
    h = blur(1.0 - m, 2, passes=2) ** (1.0 / max(depth, 0.05))
    gy, gx = np.gradient(h)
    return h, -gx * strength * 64.0, -gy * strength * 64.0


def lit_by_cracks(m: np.ndarray, nx: np.ndarray, ny: np.ndarray, reach: int = 4):
    """Diffuse term for light coming OUT OF the cracks onto the plates.

    This is the whole "physical, not flat" difference. The only light source
    down here is the molten channel itself, so it grazes the plate walls from
    below and to the side: a plate face turned toward a crack is bright, its top
    is dim, and the far side of a plate is dark. A flat surface cannot show any
    of that, no matter how good the emissive mask is.
    """
    glow = blur(m, reach)
    gy, gx = np.gradient(blur(m, reach + 2))
    scale = 1.0 / (np.abs(gx).max() + np.abs(gy).max() + 1e-5)
    lx, ly, lz = gx * scale * 60.0, gy * scale * 60.0, 0.55
    inv = 1.0 / np.sqrt(lx * lx + ly * ly + lz * lz)
    ninv = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
    ndl = (nx * lx + ny * ly + lz) * inv * ninv
    return np.clip(ndl, 0.0, 1.0) * glow, glow


# ---------------------------------------------------------------------------
# the candidates
#
# Each returns (albedo, emissive). In a room this dark almost nothing reaches
# albedo, so emissive is what you actually see -- which is exactly the point
# panel 1 is making.
# ---------------------------------------------------------------------------


def look_current(src, m, noise):
    """On screen today: unlit rock (i.e. black) plus the sparse authored _e."""
    albedo, e = src
    return albedo, e * 1.6


def look_lightonly(src, m, noise):
    """No shader at all. The same texture, with the lava lighting the room.

    Most of the complaint about the screenshot is answered here: the crust stops
    being a void and the flat's own painted cracks come back. Worth looking at
    before buying any of the rest.
    """
    albedo, e = src
    glow = blur(m, 5)
    return albedo, e * 1.6 + albedo * (0.10 + 0.85 * glow[..., None])


def look_heat_flat(src, m, noise):
    """Blackbody cracks over a lit crust, but the surface is still FLAT.

    The control for panels 4-9: everything they add is relief, so this shows how
    much of the improvement is the temperature ramp alone.
    """
    albedo, _ = src
    e = ramp(temper(m), HEAT) * (0.15 + 1.00 * m[..., None])
    glow = blur(m, 5)
    a = ROCK[None, None, :] * (0.35 + 1.5 * albedo.mean(axis=2, keepdims=True) * 3.0)
    return a, e + a * (0.12 + 1.4 * glow[..., None])


def look_relief(src, m, noise):
    """The physical one: plates with real relief, lit from inside the cracks.

    Height = 1 - crack mask, normal from its gradient, and the diffuse term
    comes from the molten channel itself. Plate walls facing a crack catch the
    light and their tops stay dark, so the crust reads as broken slabs rather
    than as a painted plane.
    """
    albedo, _ = src
    h, nx, ny = relief(m, 0.035)
    diff, glow = lit_by_cracks(m, nx, ny)
    a = ROCK[None, None, :] * (0.55 + 0.9 * h[..., None])
    e = ramp(temper(m), HEAT) * (0.15 + 1.00 * m[..., None])
    return a, e + a * (0.10 + 3.2 * diff[..., None])


def look_deep(src, m, noise):
    """Deeper channels: more height, and the plate tops shadowed.

    Same shading, stronger displacement, plus a cavity term so light does not
    reach the middle of a plate. The most three-dimensional of the set, and the
    furthest from the original art's flat read.
    """
    albedo, _ = src
    h, nx, ny = relief(m, 0.085, depth=1.9)
    diff, glow = lit_by_cracks(m, nx, ny, reach=3)
    cavity = np.clip(1.25 - h, 0.0, 1.0)
    a = ROCK[None, None, :] * (0.45 + 1.1 * h[..., None])
    e = ramp(temper(m), HEAT) * (0.15 + 1.10 * m[..., None])
    return a, e + a * (0.08 + 4.2 * (diff * cavity)[..., None])


def look_convection(src, m, noise):
    """Relief, modulated by a large low-frequency field.

    Real crust does not glow evenly: whole plates cool while others stay open.
    Uniform cracks are the single thing that most reads as "texture with a glow
    map". In the shader this field scrolls slowly, which also gives the surface
    motion without animating the flat.
    """
    albedo, _ = src
    f = 0.25 + 1.70 * noise**1.7
    h, nx, ny = relief(m, 0.035)
    diff, glow = lit_by_cracks(m, nx, ny)
    a = ROCK[None, None, :] * (0.55 + 0.9 * h[..., None])
    e = ramp(temper(np.clip(m * f, 0, 1)), HEAT) * (0.15 + 1.00 * m[..., None]) * f[..., None]
    return a, e + a * (0.10 + 3.2 * (diff * f)[..., None])


def look_halo(src, m, noise):
    """Relief plus a wide soft halo: heat and dust in the air above the flow."""
    albedo, _ = src
    h, nx, ny = relief(m, 0.035)
    diff, glow = lit_by_cracks(m, nx, ny)
    wide = blur(m, 6)
    a = ROCK[None, None, :] * (0.55 + 0.9 * h[..., None])
    e = ramp(temper(m), HEAT) * (0.15 + 1.00 * m[..., None])
    e = e + ramp(temper(np.clip(wide * 1.4, 0, 1)), HEAT) * wide[..., None] * 0.9
    return a, e + a * (0.10 + 3.2 * diff[..., None])


def look_molten(src, m, noise):
    """Relief, narrow white-hot cores, and a WET sheen on the cracks only.

    Not a reflection -- lava does not mirror, which is the whole reason it
    cannot reuse the water path. A tight specular lobe on the open channels
    only, lit by the lava itself, so they read as liquid and the crust does not.
    """
    albedo, _ = src
    h, nx, ny = relief(m, 0.05, depth=1.4)
    diff, glow = lit_by_cracks(m, nx, ny)
    narrow = np.clip(m, 0, 1) ** 1.8
    core = np.clip((m - 0.70) / 0.30, 0, 1) ** 0.5
    slope = np.clip(np.abs(np.gradient(m)[0]) + np.abs(np.gradient(m)[1]), 0, 1)
    a = ROCK[None, None, :] * (0.55 + 0.9 * h[..., None])
    e = ramp(temper(narrow), HEAT) * (0.15 + 1.10 * narrow[..., None])
    e += core[..., None] * np.array([1.0, 0.90, 0.66], dtype=np.float32) * 0.85
    e += (core * (0.3 + slope))[..., None] * np.array([1.0, 0.72, 0.35], dtype=np.float32) * 0.8
    return a, e + a * (0.10 + 3.2 * diff[..., None])


def look_retro(src, m, noise):
    """Relief, then the whole result quantized to 12 steps. No bloom, no halo.

    The conservative option: keeps Doom 64's crisp banded look and reads as the
    original art with a light and a surface, rather than as a modern material.
    """
    a, e = look_relief(src, m, noise)
    return a, np.floor(e * 12.0) / 12.0


# ---------------------------------------------------------------------------
# the ART-PRESERVING candidates
#
# Verdict on the first sheet: "2 (light only) seems the best, strangely". Not
# strangely at all. Panels 3-9 there all THROW THE ART AWAY -- they replace the
# painted crust with a synthetic heat ramp keyed on a mask derived from it, so
# the artist's per-crack shading, the warm/cool variation between plates and the
# hand-placed hot spots are all flattened into one gradient. What comes back is
# smooth and generic, and the pixel art was neither.
#
# So this set inverts the rule: the albedo is never replaced, only lit and
# MODULATED. Every panel starts from panel 2 -- the real flat, lit by its own
# cracks -- and adds exactly one thing on top, so the art keeps its authorship
# and the shader only does what the texture cannot do for itself.
# ---------------------------------------------------------------------------


def _base(albedo, e, m, ndl=None, gain=1.0):
    """Panel 2: the real flat lit by its own cracks, plus the authored _e.

    ndl, when given, replaces the isotropic glow with directional shading from
    the cracks -- the SAME light, just with a direction. That is the whole
    difference between a lit texture and a surface.
    """
    glow = blur(m, 5) * gain
    shade = glow if ndl is None else glow * (0.30 + 1.7 * ndl)
    # the painted cracks are hot rock, not lit rock: a little self-emission in
    # the flat's OWN colour, so their hue still comes from the art
    self_emit = albedo * (m[..., None] ** 1.3) * 1.5 * gain
    return e * 1.6 + albedo * (0.10 + 0.85 * shade[..., None]) + self_emit


def art_relief(src, m, noise):
    """Panel 2 + relief. The one addition a texture cannot make for itself.

    Height is 1 - crack mask, so the molten line is the LOW point, and the light
    comes out of it. Plate faces turned toward a crack brighten, plate tops go
    dark. Nothing about the albedo changes.
    """
    albedo, e = src
    h, nx, ny = relief(m, 0.035)
    ndl, _ = lit_by_cracks(m, nx, ny)
    return albedo, _base(albedo, e, m, ndl=ndl)


def art_relief_deep(src, m, noise):
    """Same, with the channels cut deeper and the plate middles occluded."""
    albedo, e = src
    h, nx, ny = relief(m, 0.085, depth=1.9)
    ndl, _ = lit_by_cracks(m, nx, ny, reach=3)
    return albedo, _base(albedo, e, m, ndl=ndl * np.clip(1.25 - h, 0, 1) * 1.6)


def art_convection(src, m, noise):
    """Panel 2 + a large low-frequency field over the crack light.

    Whole plates cool while others stay open. Uniform cracks are the single
    thing that most reads as "texture with a glow map"; in the shader this field
    scrolls, which gives the surface motion without touching the flat.
    """
    albedo, e = src
    f = 0.35 + 1.45 * noise**1.6
    return albedo, _base(albedo, e, m * f, gain=1.0) * (0.55 + 0.75 * f[..., None])


def art_cores(src, m, noise):
    """Panel 2 + white-hot cores on the top few percent of the mask only.

    Not a ramp over the whole crack -- just the open centre of the widest
    channels, left in the art's hue everywhere else.
    """
    albedo, e = src
    core = np.clip((m - 0.80) / 0.20, 0, 1) ** 0.7
    hot = np.array(srgb("#ffb347"), dtype=np.float32)
    return albedo, _base(albedo, e, m) + core[..., None] * hot * 2.2


def art_halo(src, m, noise):
    """Panel 2 + a soft wide halo: heat and dust in the air over the flow."""
    albedo, e = src
    wide = blur(m, 6)
    tint = (albedo * m[..., None]).reshape(-1, 3).sum(axis=0)
    tint = tint / max(float(tint.max()), 1e-4)
    return albedo, _base(albedo, e, m) + wide[..., None] * tint * 0.55


def art_wet(src, m, noise):
    """Panel 2 + relief + a WET sheen on the open cracks only.

    The answer to "lava does not reflect": no mirror, no environment -- a tight
    specular lobe on the molten channels, lit by the lava itself, so they read
    as liquid while the crust stays matte.
    """
    albedo, e = src
    h, nx, ny = relief(m, 0.05, depth=1.4)
    ndl, _ = lit_by_cracks(m, nx, ny)
    slope = np.clip(np.abs(np.gradient(m)[0]) + np.abs(np.gradient(m)[1]), 0, 1)
    spec = np.clip(m - 0.55, 0, 1) * (0.35 + slope)
    return albedo, _base(albedo, e, m, ndl=ndl) + spec[..., None] * np.array(
        srgb("#ff8c3c"), dtype=np.float32
    ) * 1.6


def art_proposal(src, m, noise):
    """Relief + convection + cores. The three that do not fight the art.

    Relief for the shape the texture cannot carry, convection so the flow is not
    uniform and moves, cores so the widest channels read as open. Albedo
    untouched throughout.
    """
    albedo, e = src
    f = 0.40 + 1.35 * noise**1.6
    h, nx, ny = relief(m, 0.035)
    ndl, _ = lit_by_cracks(m, nx, ny)
    core = np.clip((m - 0.80) / 0.20, 0, 1) ** 0.7
    hot = np.array(srgb("#ffb347"), dtype=np.float32)
    out = _base(albedo, e, m * f, ndl=ndl) * (0.60 + 0.65 * f[..., None])
    return albedo, out + core[..., None] * hot * 1.9 * f[..., None]


ART_LOOKS = [
    ("1. current (the screenshot)", "unlit rock + the sparse authored _e", look_current, False),
    ("2. light only  [the baseline]", "the real flat, lit by its own cracks", look_lightonly, True),
    ("3. + relief", "same art, light now has a direction", art_relief, True),
    ("4. + deeper channels", "relief with the plate middles occluded", art_relief_deep, True),
    ("5. + convection", "low-freq field; plates cool unevenly", art_convection, True),
    ("6. + hot cores", "top 20% of the mask only, art elsewhere", art_cores, True),
    ("7. + heat halo", "soft wide bloom in the flat's own hue", art_halo, True),
    ("8. + wet cracks", "relief + specular on the channels only", art_wet, True),
    ("9. relief + convection + cores", "the proposal: all three, albedo untouched", art_proposal, True),
]


# The first sheet: every panel from 3 on REPLACES the albedo with a heat ramp.
# Kept because it is the evidence for why the art-preserving set exists.
RAMP_LOOKS = [
    ("1. current (the screenshot)", "unlit rock + the sparse authored _e", look_current, False),
    ("2. light only, no shader", "same texture, lava lights the room", look_lightonly, True),
    ("3. heat ramp, still flat", "blackbody cracks, no relief", look_heat_flat, True),
    ("4. relief crust", "plates lit from inside the cracks", look_relief, True),
    ("5. deep channels", "more height + cavity shadowing", look_deep, True),
    ("6. relief + convection", "low-freq field; plates cool unevenly", look_convection, True),
    ("7. relief + heat halo", "soft wide bloom over the flow", look_halo, True),
    ("8. molten skin", "white-hot cores, wet sheen on cracks only", look_molten, True),
    ("9. retro ramp", "relief, quantized to 12 steps", look_retro, True),
]


# ---------------------------------------------------------------------------
# panel rendering
# ---------------------------------------------------------------------------


def tonemap(rgb: np.ndarray) -> np.ndarray:
    """Reinhard on the CHANNEL MAX, applied uniformly, then gamma.

    Per-channel Reinhard compresses red hardest because red is the largest
    channel here, so every hot pixel drifts to cream and the whole sheet reads
    as sand rather than as lava. Scaling all three by one factor keeps the hue
    and lets the highlights stay orange.
    """
    x = np.clip(rgb, 0.0, None) * EXPOSURE
    peak = np.maximum(x.max(axis=-1, keepdims=True), 1e-6)
    x = x * (1.0 / (1.0 + peak))
    return np.clip(x, 0.0, 1.0) ** (1.0 / 2.2)


def mip_chain(a: np.ndarray, levels: int = 7) -> list[np.ndarray]:
    """Box mip pyramid. The floor runs to a horizon, so without mips the
    distance is aliasing rather than shading and the panels stop comparing."""
    chain, cur = [a], a
    while len(chain) < levels and min(cur.shape[:2]) > 2:
        h, w = (cur.shape[0] // 2) * 2, (cur.shape[1] // 2) * 2
        cur = cur[:h, :w].reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3))
        chain.append(cur)
    return chain


def tile_inset(albedo: np.ndarray, emissive: np.ndarray, size: int = 150) -> Image.Image:
    """The shaded tile head-on, 1:1.

    The perspective view answers "how does this read in the room"; at that scale
    relief is a few pixels and the candidates all converge. This answers "what
    is actually on the surface", which is the thing being chosen.
    """
    im = Image.fromarray((tonemap(emissive + albedo * 0.03) * 255.0 + 0.5).astype(np.uint8))
    return im.resize((size, size), Image.NEAREST)


def render_panel(albedo: np.ndarray, emissive: np.ndarray, lit: bool) -> Image.Image:
    """A dark room with this lava on the floor, framed like the screenshot."""
    surface = emissive + albedo * 0.03  # 0.03 = the ambient this room has
    mips = mip_chain(surface)

    H, W = PANEL_H * SS, PANEL_W * SS
    hz = HORIZON * SS
    img = np.zeros((H, W, 3), dtype=np.float32)

    ys = np.arange(hz, H, dtype=np.float32)
    v = (ys - hz + 0.5) / (H - hz)
    depth = 1.0 / np.maximum(v, 1e-3)
    xs = (np.arange(W, dtype=np.float32) - W * 0.5) / W

    # UV per unit depth, tuned so one tile spans about a third of the frame at
    # the camera's feet -- the scale the screenshot shows.
    u = xs[None, :] * depth[:, None] * 2.4
    w = depth[:, None] * 1.5 + np.zeros_like(u)

    lod = np.clip(np.log2(np.maximum(depth * 0.16, 1.0)), 0, len(mips) - 1.001)
    floor = np.zeros((len(ys), W, 3), dtype=np.float32)
    lo = lod.astype(int)
    frac = (lod - lo)[:, None, None]
    for level in range(len(mips)):
        for which, weight in ((lo == level, 1.0 - frac), (lo + 1 == level, frac)):
            rows = np.nonzero(which)[0]
            if rows.size == 0:
                continue
            t = mips[level]
            th, tw = t.shape[:2]
            su = ((u[rows] % 1.0) * tw).astype(int) % tw
            sv = ((w[rows] % 1.0) * th).astype(int) % th
            floor[rows] += t[sv, su] * weight[rows]

    fade = np.clip(1.0 / (1.0 + depth[:, None] * 0.55), 0.0, 1.0)[..., None]
    img[hz:] = floor * fade

    # Painted, not traced: a dim warm falloff off the floor line, tinted by THIS
    # candidate's own mean emission, because a white-hot flow and a deep red one
    # do not light a room the same colour. Deliberately weak -- the point of the
    # screenshot is how dark this room is.
    if lit:
        mean = surface.reshape(-1, 3).mean(axis=0)
        peak = max(float(mean.max()), 1e-4)
        tint = mean / peak
        rise = np.arange(hz, dtype=np.float32) / hz
        fall = (1.0 - rise) ** 3.0
        wall_x = 0.5 + 0.5 * np.cos(np.linspace(-1.35, 1.35, W, dtype=np.float32))
        img[:hz] = (fall[:, None] * wall_x[None, :])[..., None] * tint * min(peak * 2.2, 0.30)

    for cx, half in ((0.17, 0.06), (0.73, 0.08)):
        x0, x1 = int((cx - half) * W), int((cx + half) * W)
        img[int(hz * 0.08) : hz, x0:x1] *= 0.18

    img = tonemap(img)
    img = img.reshape(PANEL_H, SS, PANEL_W, SS, 3).mean(axis=(1, 3))
    return Image.fromarray((img * 255.0 + 0.5).astype(np.uint8))


def font(size: int):
    for name in ("consola.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default="HLAVA1", help="source flat lump (default HLAVA1)")
    ap.add_argument(
        "--set",
        dest="which",
        choices=("art", "ramp"),
        default="art",
        help="art (default): keep the albedo, add shading on top. "
        "ramp: the first pass, which replaced it with a heat ramp.",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    looks = ART_LOOKS if args.which == "art" else RAMP_LOOKS
    if args.out is None:
        args.out = str(ROOT / f"screen/lava_looks_{args.which}.png")

    src = load_source(args.tex)
    m = crack_mask(src[0])
    noise = value_noise(m.shape, cells=3, seed=7)

    rows = (len(looks) + COLS - 1) // COLS
    W = COLS * PANEL_W + (COLS + 1) * PAD
    H = rows * (PANEL_H + LABEL_H) + (rows + 1) * PAD + 44
    sheet = Image.new("RGB", (W, H), (16, 15, 16))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (PAD, 13),
        f"lava shader — candidate looks on {args.tex}"
        + (
            "   —  ALBEDO KEPT, shading added on top"
            if args.which == "art"
            else "   —  albedo REPLACED by a heat ramp"
        )
        + "   (mockup: fixed perspective, painted room light, baked relief)",
        font=font(19),
        fill=(190, 185, 180),
    )

    f_title, f_sub = font(21), font(16)
    for i, (title, sub, fn, lit) in enumerate(looks):
        r, c = divmod(i, COLS)
        x = PAD + c * (PANEL_W + PAD)
        y = 44 + PAD + r * (PANEL_H + LABEL_H + PAD)
        a, e = fn(src, m, noise)
        panel = render_panel(a, e, lit)
        inset = tile_inset(a, e)
        panel.paste(inset, (PANEL_W - inset.width - 10, 10))
        ImageDraw.Draw(panel).rectangle(
            [PANEL_W - inset.width - 11, 9, PANEL_W - 10, 10 + inset.height],
            outline=(120, 108, 100),
        )
        sheet.paste(panel, (x, y))
        draw.text((x, y + PANEL_H + 8), title, font=f_title, fill=(238, 224, 208))
        draw.text((x, y + PANEL_H + 33), sub, font=f_sub, fill=(146, 140, 136))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out}  ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
