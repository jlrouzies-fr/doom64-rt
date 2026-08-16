"""Measure RINGING at edges in a SINGLE frame -- no control frame, no medium.

WHY THIS EXISTS, and why it is not measure_edge_outlines.py:

`measure_edge_outlines.py` answers "does the smoked frame differ from the
control in a way transmittance cannot explain". That question presupposes the
artefact is something the medium does. Two results in
docs/rt-volumetric-edge-outlines.md say it is not:

  * `rt_volume_postcomp 1` keeps the medium OUT of the upscaler's input
    entirely, and the outline is unchanged (S7.2). So the upscaler is not
    mis-reconstructing the medium.
  * The 40% that survives `rt_volume_edgesoft` sits on ALBEDO seams, where
    there is no depth step and nothing for the medium to step across (S7.4).

The remaining story consistent with both: the upscaler lays a one-pixel dark
undershoot beside EVERY contrast edge, always, in every frame -- and the veil
does not create it, it REVEALS it, by compressing local contrast so the fixed
ring stops being masked. If that is true, the ring is measurable in a frame with
NO SMOKE IN IT AT ALL, and the whole investigation moves out of the volumetric
code.

THE MEASUREMENT. For every clean vertical step edge, take the luminance profile
across it, oriented so +offset is always the brighter side, and NORMALISE it by
that edge's own step height:

        0.0 = the dark plateau        1.0 = the bright plateau

A filter with only positive weights (a box, a Gaussian, a bilinear upsample)
cannot leave the range [0,1]: its output at any point is a weighted average of
its inputs. So ANY excursion below 0 or above 1 is a negative-lobe filter --
Lanczos-style reconstruction, a sharpen, or a temporal rectification clamp. That
is the signature, and it needs no reference image to be read.

  undershoot = the deepest point below the dark plateau, in step-heights
  overshoot  = the highest point above the bright plateau

WHAT MAKES AN EDGE ELIGIBLE. Only edges with genuinely FLAT ground on both
sides. A texture seam inside a busy texture has structure either side, and its
"undershoot" would just be the next texel. Both plateaus must be flat to within
a fraction of the step, which throws away most of the frame and keeps the ones
where the number means what it says.

Usage:
    python tools/measure_edge_ringing.py <img.png> [<img.png> ...]
    python tools/measure_edge_ringing.py --controls    # the upscaler ladder
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
SHOTS = PROJ_ROOT / "tools" / "_edgelab"

# Same crop as measure_edge_outlines.py: the window chrome and the HUD have hard
# edges of their own and would dominate every statistic here.
CROP_TOP = 70
CROP_BOTTOM = 1240
GUN_X = (860, 1420)
GUN_Y = (900, 1369)

STEP_MIN = 20.0     # a step has to be worth measuring, in 0..255 luminance
PLATEAU_FLAT = 0.12  # each side must be flat to this fraction of the step
FAR = 8             # offsets +-FAR..+-(FAR-3) define the plateaus
NEAR = 4            # offsets +-1..+-NEAR are searched for the ring


def luminance(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def play_area_mask(shape: tuple[int, int]) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    m[CROP_TOP:min(CROP_BOTTOM, shape[0]), :] = True
    m[GUN_Y[0]:min(GUN_Y[1], shape[0]), GUN_X[0]:min(GUN_X[1], shape[1])] = False
    return m


def profiles(a: np.ndarray) -> np.ndarray | None:
    """Return an (n, 2*FAR+1) array of step-normalised profiles across edges."""
    h, w = a.shape
    area = play_area_mask(a.shape)

    gx = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]

    cand = (np.abs(gx) > STEP_MIN) & area
    # Keep only the LOCAL MAXIMUM of the gradient. Without this a single soft
    # edge contributes three neighbouring "edges" whose profiles are shifted
    # copies of each other, and the mean profile comes out smeared -- which
    # would hide exactly the one-pixel feature being looked for.
    g = np.abs(gx)
    peak = np.zeros_like(cand)
    peak[:, 1:-1] = (g[:, 1:-1] >= g[:, :-2]) & (g[:, 1:-1] > g[:, 2:])
    cand &= peak

    ys, xs = np.nonzero(cand)
    keep = (xs > FAR + 2) & (xs < w - FAR - 2)
    ys, xs = ys[keep], xs[keep]
    if len(xs) < 100:
        return None

    sign = np.sign(gx[ys, xs]).astype(int)
    offs = np.arange(-FAR, FAR + 1)
    prof = np.stack([a[ys, xs + d * sign] for d in offs], axis=1)

    dark = prof[:, 0:4]              # -8 -7 -6 -5
    bright = prof[:, -4:]            # +5 +6 +7 +8
    D = dark.mean(axis=1)
    B = bright.mean(axis=1)
    step = B - D

    ok = step > STEP_MIN
    ok &= dark.std(axis=1) < PLATEAU_FLAT * np.maximum(step, 1e-6)
    ok &= bright.std(axis=1) < PLATEAU_FLAT * np.maximum(step, 1e-6)
    if ok.sum() < 50:
        return None

    return (prof[ok] - D[ok, None]) / step[ok, None]


def measure(path: Path) -> None:
    if not path.exists():
        print(f"{path.name:34s}  MISSING")
        return
    a = luminance(path)
    p = profiles(a)
    if p is None:
        print(f"{path.name:34s}  too few clean step edges")
        return

    mean = p.mean(axis=0)
    offs = np.arange(-FAR, FAR + 1)
    lo = mean[(offs >= -NEAR) & (offs <= -1)].min()
    hi = mean[(offs >= 1) & (offs <= NEAR)].max()

    print(f"{path.name:34s}  n={p.shape[0]:>6d}   "
          f"undershoot {lo:+.3f}   overshoot {hi - 1.0:+.3f}")
    print("      offset " + " ".join(f"{d:+5d}" for d in offs))
    print("      norm   " + " ".join(f"{v:+5.2f}" for v in mean))


CONTROL_LADDER = [
    "arm-ctrl-native.png",
    "arm-ctrl-dlssq.png",
    "arm-ctrl-dlaa.png",
    "arm-ctrl-fsr2.png",
    "arm-vD-ctrl-dlaa-nosharp.png",
]


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--controls":
        print("SMOKE-FREE control frames. Any excursion outside [0,1] is a")
        print("negative-lobe filter, and none of these frames has a medium in it.\n")
        for n in CONTROL_LADDER:
            measure(SHOTS / n)
            print()
        return
    if not args:
        print(__doc__)
        sys.exit(2)
    for f in args:
        measure(Path(f))
        print()


if __name__ == "__main__":
    main()
