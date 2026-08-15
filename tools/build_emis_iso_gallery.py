"""Build MAP97 walled batch rooms to isolate which emissive *groups* wash GI.

Each category gets its own sealed room (solid walls) so booths cannot light
neighbors. A short camera tour shots one view per room at stock mapboost 200.

Modes (--mode):
  categories  — CONTROL / MIRROR / SMON / LAVA / CRT_LOGO / GLOW_EXIT / OUTTEX_SWX
  smon        — CONTROL + SMONA..SMONL sub-batches

Outputs:
  Doom64-Retribution/d64remisiso.wad
  Doom64-Retribution/d64r-emis-iso-mapinfo.pk3
  Doom64-Retribution/d64r-emis-iso-tour.pk3
  tools/_emis_iso/rooms.json
  rt scene stubs under d64remisiso_map97
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import zipfile
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD_OUT = ROOT / r"Doom64-Retribution\d64remisiso.wad"
MAPINFO_PK3 = ROOT / r"Doom64-Retribution\d64r-emis-iso-mapinfo.pk3"
TOUR_PK3 = ROOT / r"Doom64-Retribution\d64r-emis-iso-tour.pk3"
OUT_DIR = ROOT / r"tools\_emis_iso"
WORLD_EMIS = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
)
GALLERY_SCENE = (
    ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtexg_map99\textures.json"
)
RT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials"

STEM = "d64remisiso"
MAP = "MAP97"
SCENE = f"{STEM}_{MAP.lower()}"

ROOM_W = 640.0
ROOM_D = 720.0
HALL_H = 128
WALL = "BIGDOOR2"
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"
PILLAR = 64.0
CAM_STANDOFF = 180.0
GAP = 128.0


def categorize(name: str) -> str:
    u = name.upper()
    if u.startswith("SMON"):
        return "SMON"
    if re.match(r"^(HLAVA|D64LAVA|LAVA)", u):
        return "LAVA"
    if re.match(r"^(CRT|CRTR|D64LOGO|CFACE|C22|C23)", u):
        return "CRT_LOGO"
    if "GLOW" in u or u.startswith("SEXIT"):
        return "GLOW_EXIT"
    if u.startswith("OUTTEX") or u.startswith("SWX"):
        return "OUTTEX_SWX"
    return "OTHER_EMIS"


def load_batches(mode: str) -> list[dict]:
    emis = json.loads(WORLD_EMIS.read_text(encoding="utf-8"))["array"]
    emis_names = {e["textureName"] for e in emis}
    by: dict[str, list[str]] = {}
    for e in emis:
        n = e["textureName"]
        by.setdefault(categorize(n), []).append(n)

    mirrors: list[str] = []
    gallery_names: set[str] = set()
    if GALLERY_SCENE.exists():
        arr = json.loads(GALLERY_SCENE.read_text(encoding="utf-8"))["array"]
        gallery_names = {e["textureName"] for e in arr}
        for e in arr:
            if e.get("isMirrorIfSmooth") and e["textureName"] not in emis_names:
                mirrors.append(e["textureName"])
                if len(mirrors) >= 12:
                    break

    control = ["CEIL1_1", "FLOOR0_1", "STONE2", "STONE3", "SUPPORT2", "SUPPORT3"]
    if gallery_names:
        rough = [
            n
            for n in sorted(gallery_names)
            if n.upper().startswith(("SFLAT", "FLAT", "BRICK", "STONE", "SUPPORT"))
            and n not in emis_names
            and "LAVA" not in n.upper()
        ]
        if rough:
            control = rough[:8]

    if mode == "smon":
        smon_groups: dict[str, list[str]] = {}
        for n in sorted(by.get("SMON", [])):
            smon_groups.setdefault(n.upper()[:5], []).append(n)
        batches = [{"id": "CONTROL", "textures": control, "note": "non-emissive baseline"}]
        for key in sorted(smon_groups.keys()):
            batches.append(
                {
                    "id": key,
                    "textures": sorted(smon_groups[key]),
                    "note": f"SMON sub-batch {key}",
                }
            )
        return [b for b in batches if b["textures"]]

    batches = [
        {"id": "CONTROL", "textures": control, "note": "non-emissive baseline"},
        {
            "id": "MIRROR",
            "textures": mirrors or ["SPACEBE", "SPACEAA"],
            "note": "mirrors only",
        },
        {"id": "SMON", "textures": sorted(by.get("SMON", [])), "note": "blink monitors"},
        {"id": "LAVA", "textures": sorted(by.get("LAVA", [])), "note": "lava + lights"},
        {
            "id": "CRT_LOGO",
            "textures": sorted(by.get("CRT_LOGO", [])),
            "note": "CRT / logo / faces",
        },
        {
            "id": "GLOW_EXIT",
            "textures": sorted(by.get("GLOW_EXIT", [])),
            "note": "glow + exit",
        },
        {
            "id": "OUTTEX_SWX",
            "textures": sorted(by.get("OUTTEX_SWX", [])),
            "note": "OUTTEX/SWX brightmaps",
        },
    ]
    for b in batches:
        if b["id"] == "SMON" and len(b["textures"]) > 16:
            keep = []
            seen: set[str] = set()
            for t in b["textures"]:
                key = t[:5]
                if key not in seen or len(keep) < 12:
                    keep.append(t)
                    seen.add(key)
                if len(keep) >= 16:
                    break
            b["textures"] = keep
            b["note"] += f" (sample {len(keep)})"
    return [b for b in batches if b["textures"]]


def build_textmap(batches: list[dict]) -> tuple[str, list[dict]]:
    verts: list[tuple[float, float]] = []
    lines: list[dict] = []
    sides: list[dict] = []
    sectors: list[dict] = []
    things: list[dict] = []
    rooms_meta: list[dict] = []

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

    def add_onesided(va: int, vb: int, mid: str, sector: int) -> None:
        lines.append(
            {
                "v1": va,
                "v2": vb,
                "sidefront": add_side(sector, mid),
                "blocking": True,
            }
        )

    def add_twosided(va: int, vb: int, mid: str, front_sec: int, back_sec: int) -> None:
        lines.append(
            {
                "v1": va,
                "v2": vb,
                "sidefront": add_side(front_sec, mid, top=mid, bottom=mid),
                "sideback": add_side(back_sec, "-", top="-", bottom="-"),
                "blocking": True,
                "twosided": True,
                "dontpegtop": True,
            }
        )

    n = len(batches)
    total_w = n * ROOM_W + (n + 1) * GAP
    total_d = ROOM_D + 2 * GAP
    solid = len(sectors)
    sectors.append(
        {
            "heightfloor": HALL_H,
            "heightceiling": HALL_H,
            "texturefloor": FLOOR,
            "textureceiling": CEIL,
            "lightlevel": 0,
        }
    )
    o0 = add_vert(-GAP, -GAP)
    o1 = add_vert(total_w - GAP, -GAP)
    o2 = add_vert(total_w - GAP, total_d - GAP)
    o3 = add_vert(-GAP, total_d - GAP)
    add_onesided(o1, o0, WALL, solid)
    add_onesided(o2, o1, WALL, solid)
    add_onesided(o3, o2, WALL, solid)
    add_onesided(o0, o3, WALL, solid)

    for i, batch in enumerate(batches):
        ox = i * (ROOM_W + GAP)
        alcove_d = 200.0
        x0, x1 = ox, ox + ROOM_W
        y0, y1 = 0.0, ROOM_D
        ya = alcove_d

        hall = len(sectors)
        sectors.append(
            {
                "heightfloor": 0,
                "heightceiling": HALL_H,
                "texturefloor": FLOOR,
                "textureceiling": CEIL,
                "lightlevel": 32,
            }
        )

        sw = add_vert(x0, y0)
        se = add_vert(x1, y0)
        ne = add_vert(x1, y1)
        nw = add_vert(x0, y1)
        add_twosided(se, sw, WALL, hall, solid)
        add_twosided(ne, se, WALL, hall, solid)
        add_twosided(nw, ne, WALL, hall, solid)
        add_twosided(sw, nw, WALL, hall, solid)

        texs = batch["textures"]
        cols = max(1, int(math.ceil(math.sqrt(len(texs)))))
        rows = int(math.ceil(len(texs) / cols))
        cell_x = (ROOM_W - 80) / cols
        cell_y = (ROOM_D - alcove_d - 80) / max(rows, 1)
        for ti, tex in enumerate(texs):
            c = ti % cols
            r = ti // cols
            cx = x0 + 40 + cell_x * (c + 0.5)
            cy = ya + 40 + cell_y * (r + 0.5)
            h = PILLAR * 0.5
            psw = add_vert(cx - h, cy - h)
            pse = add_vert(cx + h, cy - h)
            pne = add_vert(cx + h, cy + h)
            pnw = add_vert(cx - h, cy + h)
            psec = len(sectors)
            sectors.append(
                {
                    "heightfloor": HALL_H,
                    "heightceiling": HALL_H,
                    "texturefloor": FLOOR,
                    "textureceiling": CEIL,
                    "lightlevel": 0,
                }
            )

            def edge(va: int, vb: int, t: str = tex) -> None:
                add_twosided(va, vb, t, hall, psec)

            edge(psw, pse)
            edge(pse, pne)
            edge(pne, pnw)
            edge(pnw, psw)

        cam_x = ox + ROOM_W * 0.5
        cam_y = CAM_STANDOFF
        rooms_meta.append(
            {
                "index": i,
                "id": batch["id"],
                "note": batch["note"],
                "textures": texs,
                "count": len(texs),
                "x": cam_x,
                "y": cam_y,
                "angle": 90,
                "room_origin_x": ox,
            }
        )

        if i == 0:
            things.append(
                {
                    "x": cam_x,
                    "y": cam_y,
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
        out = [kind, "{"]
        for k, v in fields.items():
            if isinstance(v, bool):
                if v:
                    out.append(f"{k} = true;")
            elif isinstance(v, str):
                out.append(f'{k} = "{v}";')
            elif isinstance(v, float):
                out.append(f"{k} = {v:.3f};")
            else:
                out.append(f"{k} = {v};")
        out.append("}")
        return "\n".join(out)

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
    parts.append(f"// D64RT emis iso: {len(batches)} sealed rooms")
    return "\n".join(parts), rooms_meta


def write_wad(textmap: str) -> None:
    tm = textmap.encode("utf-8")
    lumps = [
        (MAP.encode("ascii"), b""),
        (b"TEXTMAP", tm),
        (b"ENDMAP", b""),
    ]
    data = bytearray(b"PWAD")
    data += struct.pack("<II", len(lumps), 12)
    offsets = []
    for name, payload in lumps:
        offsets.append(len(data))
        data += payload
    dir_off = len(data)
    struct.pack_into("<I", data, 8, dir_off)
    for (name, payload), off in zip(lumps, offsets):
        nm = name[:8].ljust(8, b"\0")
        data += struct.pack("<II8s", off, len(payload), nm)
    WAD_OUT.write_bytes(data)
    print(f"wrote {WAD_OUT} ({len(data)} bytes)")


def write_mapinfo() -> None:
    pkg = OUT_DIR / "mapinfo_pk3"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "MAPINFO").write_text(
        f'map {MAP} "{MAP} - Emis Iso Batches"\n{{\n'
        f"\tlevelnum = 97\n"
        f'\tsky1 = "RSKY1"\n'
        f"}}\n",
        encoding="utf-8",
    )
    if MAPINFO_PK3.exists():
        MAPINFO_PK3.unlink()
    with zipfile.ZipFile(MAPINFO_PK3, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(pkg / "MAPINFO", arcname="MAPINFO")
    print(f"wrote {MAPINFO_PK3}")


def write_tour(rooms: list[dict]) -> None:
    pkg = OUT_DIR / "tour_pk3"
    pkg.mkdir(parents=True, exist_ok=True)
    n = len(rooms)
    xs = ", ".join(f"{r['x']:.1f}" for r in rooms)
    ys = ", ".join(f"{r['y']:.1f}" for r in rooms)
    angs = ", ".join(str(int(r["angle"])) for r in rooms)
    ids = ", ".join(f'"{r["id"]}"' for r in rooms)
    dwell = 100
    shot_at = 55
    zs = f'''version "4.12"

// Auto-generated by build_emis_iso_gallery.py
class D64RtEmisIsoTour : EventHandler
{{
	const COUNT = {n};
	const DWELL = {dwell};
	const SHOT_AT = {shot_at};
	private int idx;
	private int wait;
	private bool done;
	private bool shot;

	static const double PosX[] = {{ {xs} }};
	static const double PosY[] = {{ {ys} }};
	static const double Yaw[] = {{ {angs} }};
	static const string RoomId[] = {{ {ids} }};

	override void WorldLoaded(WorldEvent e)
	{{
		idx = 0;
		wait = 40;
		done = false;
		shot = true;
	}}

	private void HoldView(int i)
	{{
		Actor mo = players[consoleplayer].mo;
		if (mo == null)
			return;
		players[consoleplayer].camera = mo;
		mo.SetOrigin((PosX[i], PosY[i], 0), false);
		mo.SetOrigin((PosX[i], PosY[i], mo.floorz), false);
		mo.angle = Yaw[i];
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
			if (mo != null && idx > 0)
			{{
				mo.angle = Yaw[idx - 1];
				mo.pitch = 0;
				mo.vel = (0, 0, 0);
			}}
			if (!shot && idx > 0 && wait == (DWELL - SHOT_AT))
			{{
				level.MakeScreenShot();
				Console.Printf("D64RtEmisIsoShot: %d room=%s", idx - 1, RoomId[idx - 1]);
				shot = true;
			}}
			wait--;
			return;
		}}

		if (idx >= COUNT)
		{{
			Console.Printf("D64RtEmisIsoTour: done (%d rooms)", COUNT);
			done = true;
			return;
		}}

		HoldView(idx);
		Console.Printf("D64RtEmisIsoTour: %d room=%s", idx, RoomId[idx]);
		idx++;
		wait = DWELL;
		shot = false;
	}}
}}
'''
    (pkg / "ZSCRIPT").write_text(zs, encoding="utf-8")
    (pkg / "MAPINFO").write_text(
        'GameInfo\n{\n\tAddEventHandlers = "D64RtEmisIsoTour"\n}\n',
        encoding="utf-8",
    )
    if TOUR_PK3.exists():
        TOUR_PK3.unlink()
    with zipfile.ZipFile(TOUR_PK3, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in pkg.iterdir():
            if p.is_file():
                zf.write(p, arcname=p.name)
    print(f"wrote {TOUR_PK3}")


def write_scene_stub(batches: list[dict]) -> None:
    used: set[str] = set()
    for b in batches:
        used.update(b["textures"])
    meta_by: dict[str, dict] = {}
    if GALLERY_SCENE.exists():
        for e in json.loads(GALLERY_SCENE.read_text(encoding="utf-8"))["array"]:
            if e["textureName"] in used:
                meta_by[e["textureName"]] = e
    if WORLD_EMIS.exists():
        for e in json.loads(WORLD_EMIS.read_text(encoding="utf-8"))["array"]:
            if e["textureName"] in used:
                base = meta_by.get(e["textureName"], {"textureName": e["textureName"]})
                base.update(e)
                meta_by[e["textureName"]] = base
    arr = [meta_by.get(n, {"textureName": n}) for n in sorted(used)]
    doc = {"version": 0, "array": arr}
    for root in (
        RT / "data" / "scenes" / SCENE,
        OVERLAY / "rt" / "data" / "scenes" / SCENE,
    ):
        root.mkdir(parents=True, exist_ok=True)
        (root / "textures.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )
    print(f"scene stub {SCENE} ({len(arr)} textures)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--mode",
        choices=("categories", "smon"),
        default="categories",
        help="batch layout (default: categories)",
    )
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    batches = load_batches(args.mode)
    textmap, rooms = build_textmap(batches)
    write_wad(textmap)
    write_mapinfo()
    write_tour(rooms)
    write_scene_stub(batches)
    payload = {
        "mode": args.mode,
        "rooms": rooms,
        "batches": batches,
        "map": MAP,
        "scene": SCENE,
    }
    (OUT_DIR / "rooms.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(f"mode={args.mode}")
    for r in rooms:
        print(f"  [{r['index']}] {r['id']:12} n={r['count']:2}  {r['note']}")


if __name__ == "__main__":
    main()
