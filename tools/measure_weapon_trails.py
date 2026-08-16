"""Compare weapon-trail arms FRAME FOR FRAME AT THE SAME MAP TIC.

WHY ALIGNMENT IS THE WHOLE PROBLEM. rt_autoshot fires on the first FRAME at or
after a given map tic, and the arms do not run at the same frame rate -- a
freeze that changes the medium changes the cost of drawing it. So the same
burst settings gave maptimes 121/129/138/147 in one arm and 119/127/136/144 in
another. Those are DIFFERENT PHASES of the super shotgun's reload: comparing
ordinal frame 7 against ordinal frame 7 compares a sprite half way up against a
sprite half way down, and any difference measured is the animation, not the arm.

The engine prints `RT-AUTOSHOT: SCREENSHOT AT MAPTIME <n>` for every capture, in
order, so the log gives frame ordinal -> map tic. This pairs arms on the tic and
refuses to compare anything else.

THE METRIC. The medium is resolved on a 160x88 froxel grid and is low-frequency
by construction, so SHARP STRUCTURE INSIDE IT IS NOT THE MEDIUM. The number is
the RMS of a high-pass in a box that deliberately excludes:

    the HUD          (bottom ~18%)      big hard glyph edges
    the message feed (top ~15%)         the RT-AUTOSHOT lines print into frame
    the weapon       (bottom centre)    the sprite itself is a legitimate edge

What is left is the upper-middle of the screen: smoke in front of a flat,
featureless wall, where nothing sharp has any business existing. A sprite-shaped
stamp floating there is the artefact, and it is the only thing in the box that
can raise this number.

Usage:
    py tools/measure_weapon_trails.py tools/_traillab/trail-legacy tools/_traillab/trail-fix
    py tools/measure_weapon_trails.py --all
    py tools/measure_weapon_trails.py --crops <tic> <dir>...   # write matched crops to look at
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
LAB = PROJ_ROOT / "tools" / "_traillab"

# The judging box, as fractions of the frame. Upper middle: above the weapon,
# below the message feed, inside the smoke, against a flat wall.
BOX = (0.22, 0.16, 0.78, 0.62)   # x0, y0, x1, y1

ARMS = ["trail-legacy", "trail-fix", "trail-fixnoss", "trail-ssonly", "trail-nogun"]


def luminance(path: Path) -> np.ndarray:
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
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


def frames_by_tic(folder: Path) -> dict[int, Path]:
    """frame ordinal -> map tic, from the engine's own log."""
    pngs = sorted(folder.glob("*.png"), key=lambda p: (p.stat().st_mtime, p.name))
    log = folder / "trail-lab.log"
    if not log.exists():
        print(f"  {folder.name}: no trail-lab.log -- cannot align, skipping")
        return {}
    # IGNORECASE: the engine writes this lowercase into the logfile and
    # uppercase onto the screen, and matching only the on-screen form silently
    # returned zero tics for every arm.
    tics = [int(m) for m in re.findall(r"screenshot at maptime\s+(\d+)",
                                       log.read_text(errors="ignore"),
                                       re.IGNORECASE)]
    if len(tics) != len(pngs):
        # Not fatal, but say so: a mismatch means the pairing below is a guess.
        print(f"  {folder.name}: WARNING {len(pngs)} png vs {len(tics)} log lines")
    return {t: p for t, p in zip(tics, pngs)}


def box_of(shape: tuple[int, int]) -> tuple[slice, slice]:
    h, w = shape
    return (slice(int(BOX[1] * h), int(BOX[3] * h)),
            slice(int(BOX[0] * w), int(BOX[2] * w)))


def sharpness(path: Path) -> tuple[float, float]:
    """BAND-PASS, not high-pass, and the difference decides the whole reading.

    A plain high-pass counts per-pixel noise as "structure", and the noisiest
    arm then wins the artefact contest for the wrong reason: rt_volume_history 1
    integrates ONE sample per pixel per frame, so it is the grainiest arm by
    construction and scored worse than the control while visibly having fewer
    ghosts. That is the instrument grading the medium's noise, not its ghosts.

    The artefact is a SPRITE-SIZED patch -- tens of pixels across, with hard
    edges. So band-pass between sigma 2 and sigma 12: the fine end drops the
    per-pixel grain the accumulator leaves, the coarse end drops the smoke's own
    legitimate low-frequency shape. What survives is structure at the scale of a
    weapon silhouette.
    """
    a = luminance(path)
    b = box_of(a.shape)
    roi = a[b]
    band = blur(roi, 2.0) - blur(roi, 12.0)
    return float(np.sqrt(np.mean(band ** 2))), float(np.mean(roi))


def compare_window(dirs: list[Path]) -> None:
    """Compare DISTRIBUTIONS over a shared tic window, not paired tics.

    Pairing on the exact tic is the right instrument only if both arms can be
    sampled at the same tic. They cannot: under capture this runs at roughly
    four frames per second, so rt_autoshot -- which fires on the first FRAME at
    or after its tic -- lands wherever a frame happens to fall, and two arms
    share one tic out of thirteen. Pairing threw away 90% of the data and then
    reported a 5% difference from the single survivor.

    What is comparable is the WINDOW. The super shotgun's fire-and-reload cycle
    is ~50 tics and each arm covers ~100, so every arm samples the same two
    cycles at scattered phases. The mean over a dozen such samples is a fair
    estimate of "how much sprite-shaped structure this arm puts in the medium",
    and the spread across frames is the noise scale that says whether a
    difference in those means means anything.
    """
    tables = {d.name: frames_by_tic(d) for d in dirs}
    tables = {k: v for k, v in tables.items() if v}
    if len(tables) < 2:
        print("need at least two arms with logs")
        return

    lo = max(min(t) for t in tables.values())
    hi = min(max(t) for t in tables.values())
    print(f"\nShared tic window: {lo}..{hi}")
    print("\nSPRITE-SCALE STRUCTURE IN THE MEDIUM (band-pass RMS, judging box)")
    print("lower is better; +-sd is the frame-to-frame spread, i.e. the noise scale\n")

    stats = {}
    for n, tbl in tables.items():
        vals = [sharpness(p)[0] for t, p in sorted(tbl.items()) if lo <= t <= hi]
        stats[n] = (float(np.mean(vals)), float(np.std(vals)), len(vals))
        print(f"  {n:<24s} n={stats[n][2]:>3d}   {stats[n][0]:6.3f} +- {stats[n][1]:5.3f}")

    base = list(stats)[0]
    bm, bs, bn = stats[base]
    print()
    for n in list(stats)[1:]:
        m, s, k = stats[n]
        # Standard error of the difference of two means.
        se = (bs * bs / max(bn, 1) + s * s / max(k, 1)) ** 0.5
        d = m - bm
        pct = 100.0 * d / max(bm, 1e-6)
        sig = abs(d) > 2 * se
        verdict = ("BETTER" if d < 0 else "WORSE") if sig else "inside noise -- no verdict"
        print(f"  {n} vs {base}: {pct:+.1f}%  (diff {d:+.3f}, 2*se {2 * se:.3f})  {verdict}")


def compare(dirs: list[Path]) -> None:
    tables = {d.name: frames_by_tic(d) for d in dirs}
    common = sorted(set.intersection(*[set(t) for t in tables.values() if t]) if
                    all(tables.values()) else set())
    if not common:
        print("NO SHARED MAP TICS between these arms -- nothing comparable.")
        print("Re-run the burst; if it persists, widen -Burst so the windows overlap.")
        for n, t in tables.items():
            print(f"  {n}: {sorted(t)}")
        return

    names = list(tables)
    print(f"\nShared map tics: {common}")
    print("\nSHARP STRUCTURE IN THE MEDIUM (high-pass RMS in the judging box)")
    print("lower is better -- the medium is low-frequency, so this is the artefact\n")
    print("  tic  " + "".join(f"{n:>22s}" for n in names))
    totals = {n: [] for n in names}
    for t in common:
        row = f"  {t:>3d}  "
        for n in names:
            s, m = sharpness(tables[n][t])
            totals[n].append(s)
            row += f"{s:>13.3f} (L{m:5.1f})"
        print(row)
    print("\n  MEAN " + "".join(f"{np.mean(totals[n]):>22.3f}" for n in names))

    base = names[0]
    print()
    for n in names[1:]:
        d = 100.0 * (np.mean(totals[n]) - np.mean(totals[base])) / max(np.mean(totals[base]), 1e-6)
        verdict = "BETTER" if d < -3 else ("WORSE" if d > 3 else "same, inside noise")
        print(f"  {n} vs {base}: {d:+.1f}%   {verdict}")


def crops(tic: int, dirs: list[Path]) -> None:
    """Write the judging box of each arm at one tic, for looking at."""
    out = LAB / "_compare"
    out.mkdir(parents=True, exist_ok=True)
    for d in dirs:
        tbl = frames_by_tic(d)
        if tic not in tbl:
            print(f"  {d.name}: no frame at tic {tic} (has {sorted(tbl)})")
            continue
        im = Image.open(tbl[tic]).convert("RGB")
        w, h = im.size
        c = im.crop((int(BOX[0] * w), int(BOX[1] * h), int(BOX[2] * w), int(BOX[3] * h)))
        p = out / f"tic{tic}-{d.name}.png"
        c.save(p)
        print(f"  wrote {p}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--all":
        compare_window([LAB / a for a in sorted(x.name for x in LAB.iterdir() if x.is_dir() and x.name != "_compare")])
        return
    if len(args) >= 3 and args[0] == "--crops":
        crops(int(args[1]), [Path(a) for a in args[2:]])
        return
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    compare_window([Path(a) for a in args])


if __name__ == "__main__":
    main()
