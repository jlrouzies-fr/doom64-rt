"""Synthesize the flashlight battery sound cues for d64r-rt-flashlight.pk3.

Three short mono cues, written next to the pk3 sources so pack_rt_flashlight.py
picks them up:

    D64FLKO.wav  beam guttering out (burnout / battery dead)
    D64FLKR.wav  short mid-cycle flicker blip
    D64FLKN.wav  power coming back after a recharge

Pure stdlib (no numpy): the project's default python has no numpy, and these are
a few thousand samples each. Deterministic -- fixed seed, so regenerating does
not churn the pk3.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
OUT = ROOT / r"tools\d64r-rt-flashlight"
RATE = 22050


def lowpass(sig: list[float], cutoff: float) -> list[float]:
    """One-pole lowpass, cutoff in Hz."""
    a = 1.0 - math.exp(-2.0 * math.pi * cutoff / RATE)
    y = 0.0
    out = []
    for s in sig:
        y += a * (s - y)
        out.append(y)
    return out


def buzz(phase: float) -> float:
    """Filament-ish tone: fundamental + a couple of odd harmonics."""
    return (
        math.sin(phase)
        + 0.45 * math.sin(3.0 * phase)
        + 0.22 * math.sin(5.0 * phase)
    ) / 1.67


def stepped(rng: random.Random, n: int, hold: int, lo: float, hi: float) -> list[float]:
    """Sample-and-hold random gate -- the stutter of a failing contact."""
    out = []
    v = hi
    for i in range(n):
        if i % hold == 0:
            v = lo if rng.random() < 0.45 else hi
        out.append(v)
    return out


def normalize(sig: list[float], peak: float) -> list[float]:
    m = max(abs(s) for s in sig) or 1.0
    return [s * peak / m for s in sig]


def fade_edges(sig: list[float], ms: float = 4.0) -> list[float]:
    n = max(1, int(RATE * ms / 1000.0))
    for i in range(min(n, len(sig))):
        k = i / n
        sig[i] *= k
        sig[-1 - i] *= k
    return sig


def write_wav(path: Path, sig: list[float]) -> None:
    data = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(s * 32767.0)))) for s in sig
    )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    print(f"wrote {path.name} ({len(sig)} samples, {len(data) + 44} bytes)")


def make_flicker_out() -> list[float]:
    """~0.85s: buzz sagging in pitch, stuttering harder, then a soft thunk."""
    rng = random.Random(6401)
    n = int(0.85 * RATE)
    gate = stepped(rng, n, hold=int(RATE / 70), lo=0.12, hi=1.0)
    noise = lowpass([rng.uniform(-1.0, 1.0) for _ in range(n)], 2600.0)

    sig = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f0 = 96.0 * (1.0 - 0.55 * t)  # the coil losing its footing
        phase += 2.0 * math.pi * f0 / RATE
        env = (1.0 - t) ** 1.7
        # Dropouts get more frequent as it dies.
        g = gate[i] if rng.random() > 0.25 * t else gate[i] * 0.4
        sig.append((buzz(phase) * 0.75 + noise[i] * 0.45) * env * g)

    # Reflector/switch thunk once the arc is gone.
    start = int(0.52 * n)
    for i in range(start, n):
        u = (i - start) / RATE
        sig[i] += 0.55 * math.sin(2.0 * math.pi * 72.0 * u) * math.exp(-14.0 * u)

    return fade_edges(normalize(sig, 0.92))


def make_flicker_blip() -> list[float]:
    """~0.24s: a quick contact stutter, no death."""
    rng = random.Random(6402)
    n = int(0.24 * RATE)
    gate = stepped(rng, n, hold=int(RATE / 55), lo=0.1, hi=1.0)
    noise = lowpass([rng.uniform(-1.0, 1.0) for _ in range(n)], 3200.0)

    sig = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f0 = 112.0 * (1.0 - 0.18 * t)
        phase += 2.0 * math.pi * f0 / RATE
        env = math.sin(math.pi * min(1.0, t * 1.15)) ** 0.8
        sig.append((buzz(phase) * 0.7 + noise[i] * 0.35) * env * gate[i])

    return fade_edges(normalize(sig, 0.62))


def make_power_back() -> list[float]:
    """~0.40s: click, then the filament finding its pitch again."""
    rng = random.Random(6403)
    n = int(0.40 * RATE)
    noise = lowpass([rng.uniform(-1.0, 1.0) for _ in range(n)], 4200.0)

    sig = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f0 = 62.0 + 52.0 * min(1.0, t * 2.2)
        phase += 2.0 * math.pi * f0 / RATE
        env = (1.0 - math.exp(-9.0 * t)) * (1.0 - t) ** 0.8
        s = buzz(phase) * 0.8 * env + noise[i] * 0.22 * env
        if i < int(0.012 * RATE):  # switch click
            s += noise[i] * 0.9 * (1.0 - i / (0.012 * RATE))
        sig.append(s)

    return fade_edges(normalize(sig, 0.7))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_wav(OUT / "D64FLKO.wav", make_flicker_out())
    write_wav(OUT / "D64FLKR.wav", make_flicker_blip())
    write_wav(OUT / "D64FLKN.wav", make_power_back())


if __name__ == "__main__":
    main()
