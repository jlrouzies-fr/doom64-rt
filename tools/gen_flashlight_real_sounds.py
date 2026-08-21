"""Extract realistic fluorescent flicker sounds from the reference MP3.

Uses onset detection (sudden energy jumps) to find crisp flicker transients,
then extracts 120ms clips centred on each onset, sorts by energy, and keeps
the top 16. The packer (pack_rt_flashlight.py) already picks up any D64FLK*.wav.

Usage:
    python tools/gen_flashlight_real_sounds.py
    python tools/pack_rt_flashlight.py
"""

from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg

# --- paths ----------------------------------------------------------------

PROJ_ROOT = Path(__file__).resolve().parents[1]
SRC_MP3   = PROJ_ROOT / "music" / "fluorescentflicker.mp3"
OUT_DIR   = PROJ_ROOT / "tools" / "d64r-rt-flashlight"
FFMPEG    = Path(imageio_ffmpeg.get_ffmpeg_exe())

RATE = 22050
CLIP_LEN = int(0.120 * RATE)  # 120 ms per clip
NUM_CLIPS = 16


def decode_mono_wav(path: Path, rate: int = RATE) -> tuple[list[int], int]:
    tmp = path.with_suffix(".tmp.wav")
    subprocess.run(
        [str(FFMPEG), "-y", "-i", str(path),
         "-ac", "1", "-ar", str(rate), "-sample_fmt", "s16", str(tmp)],
        capture_output=True, check=True,
    )
    with wave.open(str(tmp), "rb") as w:
        data = w.readframes(w.getnframes())
    tmp.unlink()
    samples = [struct.unpack("<h", data[i:i+2])[0] for i in range(0, len(data), 2)]
    return samples, rate


def rms(samples: list[int]) -> float:
    return math.sqrt(sum(s * s for s in samples) / max(len(samples), 1))


def find_onset_clips(samples: list[int], rate: int) -> list[tuple[int, int, float]]:
    """Return list of (start, end, energy) for each onset-derived clip."""
    win = int(0.004 * rate)  # 4 ms window for onset detection
    n = len(samples)

    # Per-window RMS
    w_rms: list[float] = []
    for i in range(0, n - win, win):
        chunk = samples[i:i+win]
        w_rms.append(rms(chunk))
    mean_rms = rms(samples)

    # Onset: current window RMS > 3x average of previous 4 windows, and > 1.5x global mean
    onsets: list[tuple[int, float]] = []
    for i in range(4, len(w_rms)):
        bg = sum(w_rms[j] for j in range(i-4, i)) / 4.0
        curr = w_rms[i]
        if curr > bg * 3.0 and curr > mean_rms * 1.5:
            pos = i * win
            onsets.append((pos, curr))

    # Group onsets within 20 ms (same event)
    onsets.sort()
    merge = int(0.020 * rate)
    groups: list[tuple[int, int, float]] = []
    for pos, energy in onsets:
        if groups and pos - groups[-1][1] < merge:
            if energy > groups[-1][2]:
                groups[-1] = (groups[-1][0], max(groups[-1][1], pos), energy)
        else:
            groups.append((pos, pos + int(0.010 * rate), energy))

    # Extract 120 ms clip centred on each group
    half = CLIP_LEN // 2
    clips: list[tuple[int, int, float]] = []
    for s, e, _ in groups:
        center = (s + e) // 2
        cs = max(0, center - half)
        ce = min(n, cs + CLIP_LEN)
        if ce - cs < int(0.040 * rate):
            continue  # too short
        crms = rms(samples[cs:ce])
        clips.append((cs, ce, crms))

    # Sort by RMS energy descending, keep top N
    clips.sort(key=lambda x: x[2], reverse=True)
    return clips[:NUM_CLIPS]


def write_wav(path: Path, samples: list[int]) -> None:
    data = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(s)))) for s in samples
    )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    dur = len(samples) / RATE
    peak = max(abs(s) for s in samples) or 1
    print(f"  {path.name:20s}  {len(samples):5d} smp  {dur:.3f}s  peak={peak}")


def main() -> None:
    print(f"Decoding {SRC_MP3.name}...")
    samples, rate = decode_mono_wav(SRC_MP3)
    dur = len(samples) / rate
    print(f"  {len(samples)} samples, {dur:.1f}s, {rate} Hz")

    clips = find_onset_clips(samples, rate)
    print(f"Found {len(clips)} onset clips:")

    # Remove old generated WAVs
    for f in sorted(OUT_DIR.glob("D64FLK_[0-9]*.wav")):
        f.unlink()
        print(f"  removed old {f.name}")

    out_names: list[str] = []
    target = int(0.707 * 32767)
    for idx, (s, e, energy) in enumerate(clips):
        seg = samples[s:e]
        # Normalise to -3 dB peak
        peak = max(abs(x) for x in seg) or 1
        gain = target / peak
        seg = [max(-32768, min(32767, int(x * gain))) for x in seg]

        name = f"DFL{idx:02d}.wav"
        write_wav(OUT_DIR / name, seg)
        out_names.append(name)

    # --- burnout sound (death rattle) ------------------------------------
    # Take the densest 350ms of flicker activity plus a fade-out tail.
    # The region around ~63.44s is the loudest; we grab a cluster of strikes
    # and let them ring out with an exponential decay.
    death_len = int(0.70 * RATE)
    # Loudest onset cluster centre from the sorted clips
    if clips:
        loudest_center = (clips[0][0] + clips[0][1]) // 2
    else:
        loudest_center = int(63.44 * RATE)
    # Stretch it before the centre to capture the build-up
    ds = max(0, loudest_center - int(0.22 * RATE))
    de = min(len(samples), ds + death_len)
    death = list(samples[ds:de])
    # Fade-out in the last 300ms
    fade_len = min(len(death), int(0.30 * RATE))
    for i in range(fade_len):
        t = i / fade_len
        death[-(fade_len - i)] = int(death[-(fade_len - i)] * (1.0 - t * t))
    peak_d = max(abs(x) for x in death) or 1
    gain_d = target / peak_d
    death = [max(-32768, min(32767, int(x * gain_d))) for x in death]
    write_wav(OUT_DIR / "D64FLKO.wav", death)

    # --- recharge sound (power coming back) --------------------------------
    # A 0.35s segment with a gentle fade-in — the tube striking back.
    # Pick a quieter onset clip and fade it in.
    if len(clips) >= 3:
        mid = clips[min(2, len(clips) // 3)]
    else:
        mid = (int(94.4 * RATE), int(94.4 * RATE + CLIP_LEN), 0.0)
    rc = min(mid[0], int(len(samples) - 0.35 * RATE))
    re = min(rc + int(0.35 * RATE), len(samples))
    restrike = list(samples[rc:re])
    fade_in = min(len(restrike), int(0.12 * RATE))
    for i in range(fade_in):
        restrike[i] = int(restrike[i] * (i / fade_in) ** 0.7)
    peak_r = max(abs(x) for x in restrike) or 1
    gain_r = target / peak_r
    restrike = [max(-32768, min(32767, int(x * gain_r))) for x in restrike]
    write_wav(OUT_DIR / "D64FLKN.wav", restrike)

    # --- update SNDINFO ---------------------------------------------------
    sndinfo_path = OUT_DIR / "SNDINFO"
    lines = [
        "// Flashlight battery cues (extracted from fluorescentflicker.mp3).",
        f"// {len(out_names)} random flicker clips via $random group.",
        "",
    ]
    # The three logical sounds the ZSCRIPT uses:
    #   out  = burnout death (original D64FLKO.wav)
    #   on   = recharge (original D64FLKN.wav)
    #   flicker = $random group picking from our real flicker clips
    lines.append("d64rt/flashlight/out\t\tD64FLKO")
    lines.append("d64rt/flashlight/on\t\tD64FLKN")
    lines.append("")
    # Individual flicker variants (lump = short name ≤8 chars, no extension)
    variant_names: list[str] = []
    for name in out_names:
        lump = Path(name).stem  # e.g. DFL00
        logical = f"d64rt/flashlight/f{lump[-2:]}"
        lines.append(f"{logical}\t{lump}")
        variant_names.append(logical)
    lines.append("")
    # $random group — replaces the old single D64FLKR flicker with real clips
    lines.append(f"$random d64rt/flashlight/flicker {{ {' '.join(variant_names)} }}")
    lines.append("")
    lines.append("$limit d64rt/flashlight/out\t1")
    lines.append("$limit d64rt/flashlight/flicker\t1")
    lines.append("$limit d64rt/flashlight/on\t1")
    lines.append("")

    sndinfo_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nUpdated {sndinfo_path}")
    print(f"  $random group 'd64rt/flashlight/flicker' = {len(variant_names)} variants")


if __name__ == "__main__":
    main()