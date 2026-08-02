"""
Build an empty UDMF debug gallery map with every unique wall/flat texture
used across Doom 64: Retribution maps, plus auto-PBR stubs and a status MD.

Outputs:
  Doom64-Retribution/d64r-texture-gallery.wad   (MAP01 override / or MAP99)
  tools/_gallery/texture_inventory.json
  texture-status.md                             (tracker)
  rt/data/scenes/<scene>/textures.json + rt/mat/*_orm.png
"""
from __future__ import annotations

import json
import math
import re
import struct
import zlib
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM_PK3 = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
OUT_WAD = ROOT / r"Doom64-Retribution\d64r-texture-gallery.wad"
OUT_INV = ROOT / r"tools\_gallery\texture_inventory.json"
OUT_MD = ROOT / r"texture-status.md"
RT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials"
# Scene name must match RT_MapName = <wadstem>_<map>
# Gallery wad is loaded as PWAD that provides MAP01 for testing OR we use MAP99
# Prefer dedicated map lump MAP99 so it doesn't fight MAP01 fix wad.
GALLERY_MAP = "MAP99"
SCENE = "d64r_texture_gallery_map99"  # if wad stem is d64r-texture-gallery -> awkward
# Actually RT_MapName uses wad filename stem of the map's source. For multi-file
# loads, map usually comes from last PWAD that defines it. We'll name the wad
# so stem is predictable: d64rtexgal.wad -> d64rtexgal_map99
# Simpler: put gallery as MAP01 inside d64r-texgallery.wad and launch with only
# that + mod for textures... textures come from D64RTR. Launch:
#   -file D64RTR ... d64r-texgallery.wad  +map map99
# RT_MapName = last wad providing the map. We'll use stem `d64rtexg`.

GALLERY_WAD_STEM = "d64rtexg"
OUT_WAD = ROOT / r"Doom64-Retribution" / f"{GALLERY_WAD_STEM}.wad"
SCENE = f"{GALLERY_WAD_STEM}_{GALLERY_MAP.lower()}"

# Pillar hall: CELL must be > pillar + cam_standoff so row cameras clear prior pillars.
CELL = 280
HALL_H = 128
PILLAR = 72
CAM_STANDOFF = 160
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"


def write_wad(items: list[tuple[str, bytes]]) -> bytes:
    body = b""
    directory = b""
    offset = 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def write_png_rgba(path: Path, w: int, h: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + rgba[y * w * 4 : (y + 1) * w * 4] for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def solid_orm(roughness: float, metallic: float, size: int = 64) -> bytes:
    g = max(0, min(255, int(roughness * 255)))
    b = max(0, min(255, int(metallic * 255)))
    return bytes([255, g, b, 255]) * (size * size)


def solid_emissive(rgb: tuple[int, int, int], size: int = 64) -> bytes:
    r, g, b = rgb
    return bytes([r, g, b, 255]) * (size * size)


def classify(name: str) -> dict:
    u = name.upper()
    meta: dict = {"textureName": name, "roughnessDefault": 0.85, "metallicDefault": 0.0}

    if any(x in u for x in ("WATER", "NUKE", "SLIME", "BLOOD", "LAVA")):
        if "LAVA" in u or "NUKE" in u or "FIRE" in u:
            meta["emissiveMult"] = 1.5
            meta["roughnessDefault"] = 0.35
            meta["isAcid"] = "NUKE" in u or "SLIME" in u
        else:
            meta["isMirror"] = True
            meta["isWater"] = "WATER" in u
            meta["metallicDefault"] = 1.0
            meta["roughnessDefault"] = 0.05
        return meta

    if u.startswith("SPACE") or u.startswith("METAL") or u.startswith("STEEL"):
        meta["metallicDefault"] = 0.75
        meta["roughnessDefault"] = 0.35
        meta["isMirrorIfSmooth"] = True
        return meta

    if any(x in u for x in ("COMP", "MONIT", "TECH", "PANEL", "LIGHT", "LITE", "GLOW", "SWITCH")):
        meta["metallicDefault"] = 0.55
        meta["roughnessDefault"] = 0.4
        meta["emissiveMult"] = 0.6
        meta["lightIntensity"] = 20.0
        meta["lightColor"] = [180, 220, 255]
        return meta

    if u.startswith("SFLAT") or u.startswith("FLAT") or u.startswith("FLOOR"):
        meta["roughnessDefault"] = 0.9
        meta["metallicDefault"] = 0.05
        return meta

    if u.startswith("CEIL") or u.startswith("SDFLT"):
        meta["roughnessDefault"] = 0.8
        meta["metallicDefault"] = 0.15
        return meta

    if "DOOR" in u or "GATE" in u:
        meta["metallicDefault"] = 0.65
        meta["roughnessDefault"] = 0.45
        if "GATE" in u:
            meta["emissiveMult"] = 0.15
        return meta

    meta["metallicDefault"] = 0.25
    meta["roughnessDefault"] = 0.7
    return meta


def heuristic_category(name: str) -> str:
    u = name.upper()
    if any(x in u for x in ("LAVA", "FIRE", "NUKE", "SLIME", "WATER", "BLOOD")):
        return "liquid"
    if u.startswith("SPACE") or u.startswith("METAL") or u.startswith("STEEL"):
        return "metal"
    if any(x in u for x in ("COMP", "MONIT", "TECH", "LIGHT", "LITE", "GLOW", "SWITCH")):
        return "tech"
    if u.startswith("SFLAT") or u.startswith("FLAT") or u.startswith("FLOOR"):
        return "floor"
    if u.startswith("CEIL") or u.startswith("SDFLT"):
        return "ceiling"
    if "DOOR" in u or "GATE" in u:
        return "door"
    return "industrial"


def load_brightmap_names() -> set[str]:
    if not BM_PK3.exists():
        return set()
    names: set[str] = set()
    data = BM_PK3.read_bytes()
    i = 0
    while True:
        p = data.find(b"PK\x03\x04", i)
        if p < 0 or p + 30 > len(data):
            break
        (fnlen,) = struct.unpack_from("<H", data, p + 26)
        name = data[p + 30 : p + 30 + fnlen].decode("latin1", "replace")
        base = Path(name).stem.upper()
        if base:
            names.add(base)
        i = p + 4
    return names


def inventory_textures() -> tuple[list[str], dict[str, list[str]], Counter]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    lumps = []
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        lumps.append((nm, off, sz))

    maps: list[tuple[str, list]] = []
    i = 0
    while i < len(lumps):
        nm, off, sz = lumps[i]
        if re.fullmatch(r"MAP\d+", nm):
            block = [lumps[i]]
            j = i + 1
            while j < len(lumps):
                n2 = lumps[j][0]
                if re.fullmatch(r"MAP\d+", n2):
                    break
                block.append(lumps[j])
                j += 1
            maps.append((nm, block))
            i = j
        else:
            i += 1

    tex_count: Counter = Counter()
    by_map: dict[str, set[str]] = defaultdict(set)
    for mname, block in maps:
        for nm, off, sz in block:
            if nm != "TEXTMAP":
                continue
            t = d[off : off + sz].decode("utf-8", "replace")
            for m in re.finditer(
                r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"', t
            ):
                name = m.group(1)
                if name in ("-", "F_SKY1", "P_SKY1"):
                    continue
                tex_count[name] += 1
                by_map[mname].add(name)

    names = sorted(tex_count.keys(), key=lambda x: (-tex_count[x], x))
    by_map_lists = {k: sorted(v) for k, v in sorted(by_map.items())}
    return names, by_map_lists, tex_count


def build_gallery_textmap(textures: list[str]) -> str:
    """
    Grid of solid pillars in a lit hall. Each pillar's faces show one texture.
    Camera stands south of the pillar and looks north (flashlight + sun).
    """
    cols = max(8, int(math.ceil(math.sqrt(len(textures)))))
    rows = int(math.ceil(len(textures) / cols))
    pillar = PILLAR

    verts: list[tuple[float, float]] = []
    lines: list[dict] = []
    sides: list[dict] = []
    sectors: list[dict] = []
    things: list[dict] = []

    def add_vert(x: float, y: float) -> int:
        verts.append((x, y))
        return len(verts) - 1

    def add_side(sector: int, mid: str, top: str = "-", bottom: str = "-") -> int:
        sid = len(sides)
        sides.append(
            {
                "sector": sector,
                "texturemiddle": mid,
                "texturetop": top,
                "texturebottom": bottom,
            }
        )
        return sid

    margin = CELL * 2
    width = cols * CELL + margin * 2
    height = rows * CELL + margin * 2
    v0 = add_vert(-margin, -margin)
    v1 = add_vert(width - margin, -margin)
    v2 = add_vert(width - margin, height - margin)
    v3 = add_vert(-margin, height - margin)

    sectors.append(
        {
            "heightfloor": 0,
            "heightceiling": HALL_H,
            "texturefloor": FLOOR,
            "textureceiling": CEIL,
            "lightlevel": 255,
        }
    )

    def add_onesided(v_a: int, v_b: int, mid: str, sector: int = 0) -> None:
        lines.append(
            {
                "v1": v_a,
                "v2": v_b,
                "sidefront": add_side(sector, mid),
                "blocking": True,
            }
        )

    add_onesided(v0, v1, "BIGDOOR2")
    add_onesided(v1, v2, "BIGDOOR2")
    add_onesided(v2, v3, "BIGDOOR2")
    add_onesided(v3, v0, "BIGDOOR2")

    for idx, tex in enumerate(textures):
        c = idx % cols
        r = idx // cols
        cx = c * CELL + CELL * 0.5
        cy = r * CELL + CELL * 0.5
        h = pillar * 0.5
        sw = add_vert(cx - h, cy - h)
        se = add_vert(cx + h, cy - h)
        ne = add_vert(cx + h, cy + h)
        nw = add_vert(cx - h, cy + h)

        psec = len(sectors)
        sectors.append(
            {
                "heightfloor": HALL_H,
                "heightceiling": HALL_H,
                "texturefloor": FLOOR,
                "textureceiling": CEIL,
                "lightlevel": 255,
            }
        )

        def add_pillar_edge(va: int, vb: int) -> None:
            sf = add_side(0, tex, top=tex, bottom=tex)
            sb = add_side(psec, "-", top="-", bottom="-")
            lines.append(
                {
                    "v1": va,
                    "v2": vb,
                    "sidefront": sf,
                    "sideback": sb,
                    "blocking": True,
                    "twosided": True,
                    "dontpegtop": True,
                }
            )

        add_pillar_edge(sw, se)
        add_pillar_edge(se, ne)
        add_pillar_edge(ne, nw)
        add_pillar_edge(nw, sw)

    things.append(
        {
            "x": cols * CELL * 0.5,
            "y": -margin * 0.4,
            "angle": 90,
            "type": 1,
            "skill1": True,
            "skill2": True,
            "skill3": True,
            "skill4": True,
            "skill5": True,
            "single": True,
            "coop": True,
            "dm": True,
        }
    )

    def emit_block(kind: str, fields: dict) -> str:
        lines_out = [f"{kind}", "{"]
        for k, v in fields.items():
            if isinstance(v, bool):
                if v:
                    lines_out.append(f"{k} = true;")
            elif isinstance(v, str):
                lines_out.append(f'{k} = "{v}";')
            elif isinstance(v, float):
                lines_out.append(f"{k} = {v:.3f};")
            else:
                lines_out.append(f"{k} = {v};")
        lines_out.append("}")
        return "\n".join(lines_out)

    parts = ['namespace = "zdoom";', ""]
    for x, y in verts:
        parts.append(emit_block("vertex", {"x": x, "y": y}))
        parts.append("")
    for sec in sectors:
        parts.append(emit_block("sector", sec))
        parts.append("")
    for sd in sides:
        parts.append(emit_block("sidedef", sd))
        parts.append("")
    for ld in lines:
        parts.append(emit_block("linedef", ld))
        parts.append("")
    for th in things:
        parts.append(emit_block("thing", th))
        parts.append("")

    parts.append(f"// D64RT texture gallery: {len(textures)} pillars, {cols}x{rows}")

    booths = []
    for idx, tex in enumerate(textures):
        c = idx % cols
        r = idx // cols
        cx = c * CELL + CELL * 0.5
        cy = r * CELL + CELL * 0.5
        booths.append(
            {
                "index": idx,
                "texture": tex,
                "x": cx,
                "y": cy - (pillar * 0.5 + CAM_STANDOFF),
                "z": 0,
                "angle": 90,
                "pitch": 0,
                "col": c,
                "row": r,
            }
        )
    build_gallery_textmap.last_booths = booths  # type: ignore[attr-defined]
    build_gallery_textmap.last_grid = {
        "layout": "pillars",
        "cols": cols,
        "rows": rows,
        "cell": CELL,
        "pillar": pillar,
        "cam_standoff": CAM_STANDOFF,
    }  # type: ignore

    return "\n".join(parts)


def write_status_md(
    textures: list[str],
    by_map: dict[str, list[str]],
    tex_count: Counter,
    bright: set[str],
    meta_by: dict[str, dict],
) -> None:
    today = date.today().isoformat()
    # Load previous statuses if any
    prev_status: dict[str, str] = {}
    prev_notes: dict[str, str] = {}
    if OUT_MD.exists():
        for m in re.finditer(
            r"^\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|",
            OUT_MD.read_text(encoding="utf-8"),
            re.M,
        ):
            name = m.group(1).strip()
            st = m.group(3).strip()
            note = m.group(4).strip()
            if name and name != "texture":
                prev_status[name] = st
                prev_notes[name] = note

    lines = [
        "# Retribution RT texture status",
        "",
        f"Last regenerated: **{today}**",
        "",
        "Gallery map: load `Doom64-Retribution/d64rtexg.wad` then `map map99` "
        "(or use `tools/launch-texture-gallery-rt.cmd`).",
        "",
        "Scene materials: `rt/data/scenes/"
        + SCENE
        + "/textures.json` + `rt/mat/<TEX>_orm.png`.",
        "",
        "Regenerate inventory / gallery / auto-PBR:",
        "",
        "```bat",
        r"python tools\build_texture_gallery.py",
        "```",
        "",
        "## Status legend",
        "",
        "| status | meaning |",
        "|---|---|",
        "| `unreviewed` | auto stub only; not visually checked |",
        "| `auto` | heuristic PBR applied; looks plausible |",
        "| `tuned` | hand-adjusted meta / ORM / emissive |",
        "| `done` | approved for shipping |",
        "| `blocked` | needs engine/art fix before tuning |",
        "| `skip` | intentionally ignored (sky dummy, etc.) |",
        "",
        "## Summary",
        "",
        f"- Unique textures in maps: **{len(textures)}**",
        f"- Maps scanned: **{len(by_map)}** ({', '.join(by_map.keys())})",
        f"- Brightmap-ish names available: **{len(bright)}**",
        "",
    ]

    # counts by status
    status_count: Counter = Counter()
    rows = []
    for name in textures:
        cat = heuristic_category(name)
        st = prev_status.get(name, "unreviewed")
        note = prev_notes.get(name, "")
        # Known dummies / non-materials
        if name.upper() in ("ISUCK",) and st == "unreviewed":
            st = "skip"
            note = note or "sky dummy / not a real material"
        if not note:
            meta = meta_by.get(name, {})
            bits = [
                f"r={meta.get('roughnessDefault', '?')}",
                f"m={meta.get('metallicDefault', '?')}",
            ]
            if meta.get("emissiveMult"):
                bits.append(f"e={meta['emissiveMult']}")
            if name.upper() in bright:
                bits.append("bm")
            note = ", ".join(str(b) for b in bits)
        status_count[st] += 1
        maps_hit = [m for m, ts in by_map.items() if name in ts]
        maps_s = ",".join(maps_hit[:6]) + ("…" if len(maps_hit) > 6 else "")
        rows.append((name, cat, st, note, tex_count[name], maps_s))

    lines.append("| status | count |")
    lines.append("|---|---|")
    for st, n in status_count.most_common():
        lines.append(f"| `{st}` | {n} |")
    lines.append("")
    lines.append("## Tracker")
    lines.append("")
    lines.append("| texture | category | status | notes | uses | maps |")
    lines.append("|---|---|---|---|---|---|")
    for name, cat, st, note, uses, maps_s in rows:
        lines.append(f"| `{name}` | {cat} | {st} | {note} | {uses} | {maps_s} |")
    lines.append("")
    lines.append("## Workflow")
    lines.append("")
    lines.append("1. Launch gallery (`tools/launch-texture-gallery-rt.cmd`).")
    lines.append("2. Walk the grid; mark rows in this file `auto` → `tuned` → `done`.")
    lines.append("3. For tuned textures: edit scene `textures.json` and/or `rt/mat/<TEX>_*.png`.")
    lines.append("4. Re-run `build_texture_gallery.py` to refresh inventory; **statuses/notes are preserved**.")
    lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def emit_pbr(textures: list[str], bright: set[str]) -> dict[str, dict]:
    array = []
    meta_by = {}
    for name in textures:
        meta = classify(name)
        if name.upper() in bright:
            meta["emissiveMult"] = max(float(meta.get("emissiveMult", 0) or 0), 0.8)
        array.append(meta)
        meta_by[name] = meta

    doc = {"version": 0, "array": array}
    for scene_root in (
        RT / "data" / "scenes" / SCENE,
        OVERLAY / "rt" / "data" / "scenes" / SCENE,
    ):
        scene_root.mkdir(parents=True, exist_ok=True)
        (scene_root / "textures.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )

    mat_dirs = (RT / "mat", OVERLAY / "rt" / "mat")
    for mat_dir in mat_dirs:
        mat_dir.mkdir(parents=True, exist_ok=True)

    orm_n = emis_n = 0
    for meta in array:
        name = meta["textureName"]
        rough = float(meta.get("roughnessDefault", 0.85))
        metal = float(meta.get("metallicDefault", 0.0))
        emis = float(meta.get("emissiveMult", 0) or 0)
        orm = solid_orm(rough, metal)
        for mat_dir in mat_dirs:
            write_png_rgba(mat_dir / f"{name}_orm.png", 64, 64, orm)
        orm_n += 1
        if emis > 0.05:
            u = name.upper()
            if "LAVA" in u or "FIRE" in u:
                rgb = (255, 90, 20)
            elif "NUKE" in u or "SLIME" in u:
                rgb = (40, 255, 40)
            else:
                rgb = (120, 180, 255)
            scale = min(1.0, emis)
            rgb_s = tuple(max(0, min(255, int(c * scale))) for c in rgb)
            e = solid_emissive(rgb_s)  # type: ignore
            for mat_dir in mat_dirs:
                write_png_rgba(mat_dir / f"{name}_e.png", 64, 64, e)
            emis_n += 1

    cfg = RT / "RTGL1.json"
    cfg.write_text(
        json.dumps(
            {
                "version": 0,
                "developerMode": True,
                "vulkanValidation": False,
                "dx12Validation": False,
                "dlssValidation": False,
                "fpsMonitor": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"PBR stubs: orm={orm_n} emis={emis_n} scene={SCENE}")
    return meta_by


def write_tour_zscript(booths: list[dict], batch_start: int) -> None:
    """Bake a small auto-tour EventHandler for screenshot review."""
    pkg = ROOT / r"tools\d64r-gallery-tour"
    pkg.mkdir(parents=True, exist_ok=True)
    if not booths:
        return
    # ZScript array literals
    xs = ", ".join(f"{b['x']:.1f}" for b in booths)
    ys = ", ".join(f"{b['y']:.1f}" for b in booths)
    names = ",\n\t\t".join(f'"{b["texture"]}"' for b in booths)
    n = len(booths)
    zs = f"""version \"4.12\"

// Auto-generated by build_texture_gallery.py — do not hand-edit.
// Tours booths [{batch_start} .. {batch_start + n - 1}] for screenshot review.
class D64RtGalleryTour : EventHandler
{{
	const COUNT = {n};
	const DWELL = 105; // ~3.0s per booth
	const SHOT_AT = 45; // native screenshot this many tics after arrive
	private int idx;
	private int wait;
	private bool done;
	private bool shot;

	static const double PosX[] = {{ {xs} }};
	static const double PosY[] = {{ {ys} }};
	static const String TexName[] = {{
		{names}
	}};

	override void WorldLoaded(WorldEvent e)
	{{
		idx = 0;
		wait = 25;
		done = false;
		shot = true;
	}}

	private void HoldView(int booth)
	{{
		Actor mo = players[consoleplayer].mo;
		if (mo == null)
			return;
		players[consoleplayer].camera = mo;
		mo.SetOrigin((PosX[booth], PosY[booth], 0), false);
		mo.SetOrigin((PosX[booth], PosY[booth], mo.floorz), false);
		mo.angle = 90;
		mo.pitch = 0;
		mo.vel = (0, 0, 0);
	}}

	override void WorldTick()
	{{
		if (done || level.maptime < 8)
			return;
		if (players[consoleplayer].mo == null)
			return;

		if (wait > 0)
		{{
			Actor mo = players[consoleplayer].mo;
			if (mo != null)
			{{
				mo.angle = 90;
				mo.pitch = 0;
				mo.vel = (0, 0, 0);
			}}
			if (!shot && idx > 0 && wait == (DWELL - SHOT_AT))
			{{
				level.MakeScreenShot();
				Console.Printf(\"D64RtGalleryShot: %d %s\", {batch_start} + idx - 1, TexName[idx - 1]);
				shot = true;
			}}
			wait--;
			return;
		}}

		if (idx >= COUNT)
		{{
			Console.Printf(\"D64RtGalleryTour: done (%d booths)\", COUNT);
			done = true;
			return;
		}}

		HoldView(idx);
		Console.Printf(\"D64RtGalleryTour: %d %s\", {batch_start} + idx, TexName[idx]);
		idx++;
		wait = DWELL;
		shot = false;
	}}
}}
"""
    (pkg / "ZSCRIPT").write_text(zs, encoding="utf-8")
    (pkg / "MAPINFO").write_text(
        'GameInfo\n{\n\tAddEventHandlers = "D64RtGalleryTour"\n}\n', encoding="utf-8"
    )
    print(f"wrote tour ZScript for {n} booths (start={batch_start})")


def main() -> None:
    textures, by_map, tex_count = inventory_textures()
    bright = load_brightmap_names()
    print(f"unique textures: {len(textures)} across {len(by_map)} maps")

    OUT_INV.parent.mkdir(parents=True, exist_ok=True)
    OUT_INV.write_text(
        json.dumps(
            {
                "generated": date.today().isoformat(),
                "count": len(textures),
                "textures": textures,
                "counts": dict(tex_count),
                "by_map": by_map,
                "scene": SCENE,
                "gallery_map": GALLERY_MAP,
                "gallery_wad": str(OUT_WAD),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    textmap = build_gallery_textmap(textures)
    (OUT_INV.parent / "TEXTMAP.txt").write_text(textmap, encoding="utf-8")
    booths = getattr(build_gallery_textmap, "last_booths", [])
    grid = getattr(build_gallery_textmap, "last_grid", {})
    (OUT_INV.parent / "booths.json").write_text(
        json.dumps({"grid": grid, "booths": booths}, indent=2) + "\n", encoding="utf-8"
    )

    # UDMF map in PWAD: MAP99 + TEXTMAP + ENDMAP
    items = [
        (GALLERY_MAP, b""),
        ("TEXTMAP", textmap.encode("utf-8")),
        ("ENDMAP", b""),
    ]
    OUT_WAD.write_bytes(write_wad(items))
    print("wrote", OUT_WAD, f"({GALLERY_MAP}, {len(textures)} panels)")

    import os

    # GALLERY_SKIP_PBR=1 → rebuild map/booths/tour only (keeps materials + MD untouched)
    if os.environ.get("GALLERY_SKIP_PBR", "").strip() not in ("1", "true", "yes"):
        meta_by = emit_pbr(textures, bright)
        write_status_md(textures, by_map, tex_count, bright, meta_by)
        print("wrote", OUT_MD)
    else:
        print("skipped PBR + texture-status.md rewrite")

    start = int(os.environ.get("GALLERY_BATCH_START", "0"))
    count = int(os.environ.get("GALLERY_BATCH_COUNT", "30"))
    write_tour_zscript(booths[start : start + count], start)


if __name__ == "__main__":
    main()
