"""Build stripped MAP01 PWADs from Retribution TEXTMAP for hang isolation."""
import argparse
import re
import struct
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

SRC = PROJ_ROOT / r"tools\_map_cmp\MAP01_TEXTMAP.txt"
OUT_DIR = PROJ_ROOT / r"tools\_map_isol"


def wad(items):
    body = b""
    directory = b""
    offset = 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    header = struct.pack("<4sII", b"PWAD", len(items), 12 + len(body))
    return header + body + directory


def blocks(text, kind):
    return list(re.finditer(rf"(?ms)^({kind}\s*\{{.*?\n\}})", text))


def transform(text, mode: str) -> str:
    # Always keep namespace + geometry scaffolding
    if mode == "full":
        return text

    if mode == "no_things":
        # Keep only player starts (types 1-4)
        def keep_thing(m):
            body = m.group(1)
            t = re.search(r"type\s*=\s*(\d+)", body)
            if t and int(t.group(1)) in (1, 2, 3, 4):
                return m.group(0)
            return ""

        return re.sub(r"(?ms)^thing\s*\{.*?\}", keep_thing, text)

    if mode == "no_specials":
        # Strip linedef specials/args; keep geometry + things
        def scrub_line(m):
            body = m.group(1)
            body = re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body)
            body = re.sub(r"(?m)^\s*arg\d+\s*=\s*-?\d+;\s*\n", "", body)
            return "linedef\n{" + body + "}"

        text = re.sub(r"(?ms)^linedef\s*\{(.*?)\}", scrub_line, text)

        def scrub_sec(m):
            body = m.group(1)
            body = re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body)
            return "sector\n{" + body + "}"

        return re.sub(r"(?ms)^sector\s*\{(.*?)\}", scrub_sec, text)

    if mode == "no_things_no_specials":
        return transform(transform(text, "no_things"), "no_specials")

    if mode == "flat_box_textures":
        # Keep geometry/things/specials but replace all textures with stock Doom II
        text = re.sub(r'texturemiddle\s*=\s*"[^"]*";', 'texturemiddle = "STARTAN2";', text)
        text = re.sub(r'texturetop\s*=\s*"[^"]*";', 'texturetop = "-";', text)
        text = re.sub(r'texturebottom\s*=\s*"[^"]*";', 'texturebottom = "-";', text)
        text = re.sub(r'texturefloor\s*=\s*"[^"]*";', 'texturefloor = "FLOOR0_1";', text)
        text = re.sub(r'textureceiling\s*=\s*"[^"]*";', 'textureceiling = "CEIL1_1";', text)
        return text

    if mode == "no_3dfloor":
        def scrub_line(m):
            body = m.group(1)
            if re.search(r"special\s*=\s*160\s*;", body):
                body = re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body)
                body = re.sub(r"(?m)^\s*arg\d+\s*=\s*-?\d+;\s*\n", "", body)
            return "linedef\n{" + body + "}"

        return re.sub(r"(?ms)^linedef\s*\{(.*?)\}", scrub_line, text)

    if mode == "player_only_nospec":
        return transform(transform(text, "no_things"), "no_specials")

    raise SystemExit(f"unknown mode {mode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = SRC.read_text(encoding="utf-8", errors="replace")
    out_text = transform(text, args.mode)
    out = Path(args.out) if args.out else OUT_DIR / f"map01_{args.mode}.wad"
    data = wad(
        [
            ("MAP01", b""),
            ("TEXTMAP", out_text.encode("utf-8")),
            ("ENDMAP", b""),
        ]
    )
    out.write_bytes(data)
    print(f"wrote {out} bytes={len(data)} text={len(out_text)}")


if __name__ == "__main__":
    main()
