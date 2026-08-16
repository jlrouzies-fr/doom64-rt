"""Measure the outlines a volumetric draws around geometry, in PIXELS.

The point of this script is that "the smoke draws lines around everything" is a
description, and every previous round on this artefact was closed or reopened on
one. `docs/rt-smoke.md` S9 ruled out the sample dither and the spatial filter by
looking; the dither's own cvar help says the opposite. A number settles it.

HOW IT WORKS, and why the control frame is not optional:

  * The CONTROL frame (tools\\edge-lab.cmd off -- same room, same lights, same
    spawn, rt_smoke 0) is what says WHERE the edges are. Finding them in the
    smoked frame instead would be circular: the artefact IS an edge, so an edge
    detector run on it happily reports the artefact as the geometry.
  * The RESIDUAL is the smoked frame minus a wide blur of itself. Smoke is
    low-frequency by construction -- it is resolved on a 160x88 froxel grid --
    so anything sharp in it is not smoke. Subtracting the local mean removes the
    veil and leaves whatever is drawn on top of it.
  * The verdict is the residual sampled at the control's edge pixels against the
    residual everywhere else. Its SIGN says dark or bright; its profile across
    the edge says how WIDE, which is what tells the mechanisms apart:

        ~12-16 render px   one froxel column (renderWidth / 160): the grid
        1-2 px             the checkerboard, or a per-pixel pass
        2-4 px, scaling with the DLSS ratio rather than with any volume cvar:
                           the upscaler

Usage:
    python tools/measure_edge_outlines.py <smoked.png> <control.png>
    python tools/measure_edge_outlines.py --all          # every arm in _edgelab

Prints one line per frame plus a profile, so two arms can be compared without
opening either.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
SHOTS = PROJ_ROOT / "tools" / "_edgelab"

# The capture includes the window frame and the HUD. Both have hard edges of
# their own and would dominate every statistic here, so the measurement is
# confined to the play area. Rows are generous: the title bar is ~46 px and the
# status bar starts around 1250 on a 1369-tall capture.
CROP_TOP = 70
CROP_BOTTOM = 1240
# The weapon sprite is a black blob up the middle bottom -- pure black against
# lit smoke is the strongest edge in the frame and is not geometry.
GUN_X = (860, 1420)
GUN_Y = (900, 1369)

EDGE_THRESHOLD = 18.0   # Sobel magnitude on the control, 0..255 luminance
BLUR_SIGMA = 8.0        # wide enough that no outline survives it


def luminance(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def gaussian_blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian, done by hand so the script needs no scipy."""
    r = int(3 * sigma)
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()

    def conv1(src: np.ndarray, axis: int) -> np.ndarray:
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.pad(src, pad, mode="edge")
        out = np.zeros_like(src)
        for i, w in enumerate(k):
            sl = [slice(None), slice(None)]
            sl[axis] = slice(i, i + src.shape[axis])
            out += w * p[tuple(sl)]
        return out

    return conv1(conv1(a, 0), 1)


def sobel_mag(a: np.ndarray) -> np.ndarray:
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    return np.sqrt(gx * gx + gy * gy)


def play_area_mask(shape: tuple[int, int]) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    m[CROP_TOP:CROP_BOTTOM, :] = True
    m[GUN_Y[0]:GUN_Y[1], GUN_X[0]:GUN_X[1]] = False
    return m


def measure(smoked: Path, control: Path, label: str = "") -> None:
    s = luminance(smoked)
    c = luminance(control)
    if s.shape != c.shape:
        print(f"  SKIP {smoked.name}: {s.shape} vs control {c.shape}")
        return

    area = play_area_mask(s.shape)
    edges = (sobel_mag(c) > EDGE_THRESHOLD) & area

    # WHERE THE SMOKE IS, measured from the pair rather than assumed. The first
    # version of this script averaged over the whole play area and reported no
    # artefact at all -- because the curtain covers maybe a third of the frame
    # and the bare side walls, which are unaffected, outvoted it. An artefact
    # that only exists inside the medium has to be measured inside the medium.
    lowS, lowC = gaussian_blur(s, BLUR_SIGMA), gaussian_blur(c, BLUR_SIGMA)
    smoke = (lowS - lowC > 12.0) & area
    clear = (np.abs(lowS - lowC) < 4.0) & area

    # The residual: what is left of a frame once its own low frequencies are
    # removed. Computed for BOTH frames, because "there is sharp detail at the
    # edges" is true of any rendered image and proves nothing on its own.
    #
    # The comparison that means something: the medium ATTENUATES the surface
    # behind it, so the control's edge detail should arrive in the smoked frame
    # MULTIPLIED BY THE TRANSMITTANCE, i.e. weaker. An edge:flat ratio in the
    # smoked frame that matches or beats the control's is edge energy the smoke
    # ADDED, which is the artefact.
    resid = s - gaussian_blur(s, BLUR_SIGMA)
    residC = c - gaussian_blur(c, BLUR_SIGMA)

    # A pixel ON an edge and a pixel merely NEAR one are different questions.
    # `flat` is everything clear of any edge -- the smoke's own noise floor, and
    # the number the edges have to beat.
    near = gaussian_blur(edges.astype(np.float32), 4.0) > 0.02
    flat = area & ~near

    def rms(r: np.ndarray, m: np.ndarray) -> float:
        return float(np.sqrt(np.mean(r[m] ** 2))) if m.any() else float("nan")

    e_s, f_s = rms(resid, edges & smoke), rms(resid, flat & smoke)
    e_c, f_c = rms(residC, edges & smoke), rms(residC, flat & smoke)

    # How much the veil dims the picture, measured rather than assumed: the ratio
    # of local means over the play area. Edge detail should scale with it.
    veil = float(np.mean(lowS[smoke]) / max(np.mean(lowC[smoke]), 1e-6)) if smoke.any() else float("nan")

    print(f"{label or smoked.name}")
    print(f"    smoke covers {100.0 * smoke.sum() / area.sum():5.1f}% of play area;"
          f" {edges.sum():>7d} edge px, {(edges & smoke).sum():>7d} of them in smoke")
    print(f"    IN SMOKE   smoked edge {e_s:6.2f}  flat {f_s:6.2f}   edge:flat {e_s / max(f_s, 1e-6):5.2f}")
    print(f"               control edge {e_c:6.2f}  flat {f_c:6.2f}   edge:flat {e_c / max(f_c, 1e-6):5.2f}")
    print(f"    veil brightness x{veil:.2f}   EDGE ENERGY KEPT {e_s / max(e_c, 1e-6):5.2f}"
          f"  (transmittance = no outline; above it = added)")

    # WIDTH and SIGN. Vertical edges only (a pillar corner, a sprite's side),
    # each profile FLIPPED so that +offset always points to the brighter side of
    # the control edge. Without that flip left- and right-facing edges cancel and
    # the mean profile is flat zero whatever the artefact is doing -- which is
    # exactly what the first version of this script printed.
    gx = np.zeros_like(c)
    gx[:, 1:-1] = c[:, 2:] - c[:, :-2]
    # ---------------------------------------------------------------------
    # THE TEST THAT ACTUALLY DECIDES IT.
    #
    # If the medium is behaving, then for every pixel
    #
    #     smoked = transmittance * control + inscatter
    #
    # and BOTH coefficients are froxel-resolved, i.e. smooth over the ~16 px a
    # froxel column covers. So fitting a local linear model of the control to
    # the smoked frame over a window of that size must explain the frame
    # EXACTLY, edges included -- a locally-constant a and b cannot draw a line
    # along a silhouette. Whatever the fit cannot explain is the artefact, and
    # it is measured in luminance levels rather than described.
    #
    # This is what the earlier statistics could not do. "Edge energy kept 0.42"
    # says the medium dimmed the picture; it cannot separate a correctly dimmed
    # edge from a dimmed edge with a line drawn beside it, because both raise
    # the same RMS. The residual of this fit is zero for the first and not for
    # the second.
    win = 8.0
    mS, mC = gaussian_blur(s, win), gaussian_blur(c, win)
    vCC = gaussian_blur(c * c, win) - mC * mC
    vSC = gaussian_blur(s * c, win) - mS * mC
    a = vSC / np.maximum(vCC, 1.0)
    b = mS - a * mC
    fit = a * c + b
    r = s - fit

    def rmsr(m: np.ndarray) -> float:
        return float(np.sqrt(np.mean(r[m] ** 2))) if m.any() else float("nan")

    print(f"    LOCAL-FIT RESIDUAL   on edge {rmsr(edges & smoke):5.2f}"
          f"   flat {rmsr(flat & smoke):5.2f}"
          f"   excess {rmsr(edges & smoke) / max(rmsr(flat & smoke), 1e-6):5.2f}"
          f"   [clear-area edge {rmsr(edges & clear):5.2f}]")

    offs = np.arange(-16, 17)

    def fitprofile(mask: np.ndarray, tag: str) -> None:
        vert = (np.abs(gx) > EDGE_THRESHOLD) & mask
        ys, xs = np.nonzero(vert)
        keep = (xs > 40) & (xs < s.shape[1] - 40)
        ys, xs = ys[keep], xs[keep]
        if len(xs) < 200:
            print(f"      {tag}: too few edges ({len(xs)})")
            return
        sign = np.sign(gx[ys, xs]).astype(int)
        prof = np.array([r[ys, xs + d * sign].mean() for d in offs])
        print(f"      {tag}  n={len(xs)}  (+offset = brighter side of the edge)")
        print("        offset " + " ".join(f"{d:+4d}" for d in offs[::2]))
        print("        fitres " + " ".join(f"{prof[i]:+4.1f}" for i in range(0, len(offs), 2)))

    def profile(mask: np.ndarray, tag: str) -> None:
        vert = (np.abs(gx) > EDGE_THRESHOLD) & mask
        ys, xs = np.nonzero(vert)
        keep = (xs > 40) & (xs < s.shape[1] - 40)
        ys, xs = ys[keep], xs[keep]
        if len(xs) < 200:
            print(f"      {tag}: too few edges ({len(xs)})")
            return
        sign = np.sign(gx[ys, xs]).astype(int)
        prof = np.array([resid[ys, xs + d * sign].mean() for d in offs])
        print(f"      {tag}  n={len(xs)}")
        print("        offset " + " ".join(f"{d:+4d}" for d in offs[::2]))
        print("        signed " + " ".join(f"{prof[i]:+4.1f}" for i in range(0, len(offs), 2)))

    # The SAME profile inside the smoke and in the clear parts of the same
    # frame. This is the discriminator that no single-frame look can give: a
    # halo that is equally strong in both is drawn by something that does not
    # know about the medium -- the upscaler, the denoiser, a sharpen -- and is
    # merely more VISIBLE against a flat veil. One that only exists inside the
    # smoke is the medium's own.
    fitprofile(smoke, "fit residual, in smoke")
    fitprofile(clear, "fit residual, in clear")
    print()


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--all":
        control = SHOTS / "repro-control-smokeoff.png"
        for p in sorted(SHOTS.glob("arm-*.png")) + [SHOTS / "repro-smoke.png"]:
            if p.exists():
                measure(p, control, label=p.stem)
        return
    if len(args) != 2:
        print(__doc__)
        sys.exit(2)
    measure(Path(args[0]), Path(args[1]))


if __name__ == "__main__":
    main()
