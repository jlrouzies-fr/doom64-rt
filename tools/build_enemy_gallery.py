"""
Build a dark no-aggro enemy review gallery (MAP98) — one living monster per booth.

- UDMF friend=true on all monsters (plus launch +notarget)
- Dark hall so eye emissives / sprite lighting are readable with flashlight
- Outputs wad, mapinfo pk3, booths.json, tour ZScript package
"""
from __future__ import annotations

import json
import math
import struct
import zipfile
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
OUT_DIR = ROOT / r"tools\_enemy_gallery"
OUT_WAD = ROOT / r"Doom64-Retribution\d64renemyg.wad"
OUT_MAPINFO_DIR = ROOT / r"tools\d64r-enemygallery-mapinfo"
OUT_MAPINFO_PK3 = ROOT / r"Doom64-Retribution\d64r-enemygallery-mapinfo.pk3"
OUT_TOUR_DIR = ROOT / r"tools\d64r-enemy-gallery-tour"
BOOTHS = OUT_DIR / "booths.json"

GALLERY_MAP = "MAP98"
WAD_STEM = "d64renemyg"
SCENE = f"{WAD_STEM}_{GALLERY_MAP.lower()}"

CELL = 320
HALL_H = 192
CAM_STANDOFF = 140
FLOOR = "FLAT5_4"
CEIL = "CEIL5_2"

# D64-native monsters only (sprites in D64RTR_v15; no Doom2-only CPOS/SKEL/VILE/SPID).
# (doomednum, label, sprite_prefix_hint)
MONSTERS: list[tuple[int, str, str]] = [
    (3004, "Zombieman", "POSS"),
    (9, "ShotgunGuy", "SPOS"),
    (3001, "Imp", "TROO"),
    (3007, "NightmareImp", "TRO2"),
    (3002, "Demon", "SARG"),
    (58, "Spectre", "SAR2"),
    (3005, "Cacodemon", "HEAD"),
    (69, "HellKnight", "BOS2"),
    (3003, "BaronOfHell", "BOSS"),
    (67, "Mancubus", "FATT"),
    (68, "Arachnotron", "BSPI"),
    (71, "PainElemental", "PAIN"),
    (3006, "LostSoul", "SKUL"),
    (16, "Cyberdemon", "CYBR"),
    (3013, "MotherDemon", "RECT"),  # Mother uses RECT* frames in DECORATE
]


def write_wad(items: list[tuple[str, bytes]]) -> bytes:
    # IWAD-style PWAD
    lumps = [(n.encode("ascii")[:8].ljust(8, b"\0"), d) for n, d in items]
    body = b"".join(d for _, d in lumps)
    directory = bytearray()
    off = 12
    for name, data in lumps:
        directory += struct.pack("<II8s", off, len(data), name)
        off += len(data)
    return b"PWAD" + struct.pack("<II", len(lumps), 12 + len(body)) + body + bytes(directory)


def build_textmap(monsters: list[tuple[int, str, str]]) -> tuple[str, list[dict]]:
    cols = max(4, int(math.ceil(math.sqrt(len(monsters)))))
    rows = int(math.ceil(len(monsters) / cols))
    verts: list[tuple[float, float]] = []
    lines: list[dict] = []
    sides: list[dict] = []
    sectors: list[dict] = []
    things: list[dict] = []

    def add_vert(x: float, y: float) -> int:
        verts.append((x, y))
        return len(verts) - 1

    def add_side(sector: int, mid: str = "-") -> int:
        sid = len(sides)
        sides.append(
            {
                "sector": sector,
                "texturemiddle": mid,
                "texturetop": "-",
                "texturebottom": "-",
            }
        )
        return sid

    margin = CELL * 1.5
    width = cols * CELL + margin * 2
    depth = rows * CELL + margin * 2
    v0 = add_vert(-margin, -margin)
    v1 = add_vert(width - margin, -margin)
    v2 = add_vert(width - margin, depth - margin)
    v3 = add_vert(-margin, depth - margin)

    # Dark hall — flashlight + sprite emissives
    sectors.append(
        {
            "heightfloor": 0,
            "heightceiling": HALL_H,
            "texturefloor": FLOOR,
            "textureceiling": CEIL,
            "lightlevel": 16,
        }
    )

    def wall(a: int, b: int, mid: str = "BIGDOOR2") -> None:
        lines.append(
            {
                "v1": a,
                "v2": b,
                "sidefront": add_side(0, mid),
                "blocking": True,
            }
        )

    wall(v0, v1)
    wall(v1, v2)
    wall(v2, v3)
    wall(v3, v0)

    booths: list[dict] = []
    for idx, (ednum, label, prefix) in enumerate(monsters):
        c = idx % cols
        r = idx // cols
        cx = c * CELL + CELL * 0.5
        cy = r * CELL + CELL * 0.5

        # Marker pad (raised, non-blocking) — large monsters must not clip walls
        h = 56 if ednum in (16, 3013) else 32
        sw = add_vert(cx - h, cy - h)
        se = add_vert(cx + h, cy - h)
        ne = add_vert(cx + h, cy + h)
        nw = add_vert(cx - h, cy + h)
        psec = len(sectors)
        sectors.append(
            {
                "heightfloor": 8,
                "heightceiling": HALL_H,
                "texturefloor": "FLAT20",
                "textureceiling": CEIL,
                "lightlevel": 16,
            }
        )

        def edge(va: int, vb: int) -> None:
            lines.append(
                {
                    "v1": va,
                    "v2": vb,
                    "sidefront": add_side(0, "STEP2"),
                    "sideback": add_side(psec, "-"),
                    "blocking": False,
                    "twosided": True,
                }
            )

        edge(sw, se)
        edge(se, ne)
        edge(ne, nw)
        edge(nw, sw)

        # Monster faces south (toward camera). angle 270 = south in Doom.
        things.append(
            {
                "x": cx,
                "y": cy,
                "angle": 270,
                "type": ednum,
                "skill1": True,
                "skill2": True,
                "skill3": True,
                "skill4": True,
                "skill5": True,
                "single": True,
                "coop": True,
                "dm": True,
                "friend": True,
                "countsecret": False,
                "countkill": False,
            }
        )

        cam_x = cx
        cam_y = cy - CAM_STANDOFF
        booths.append(
            {
                "index": idx,
                "doomednum": ednum,
                "label": label,
                "prefix": prefix,
                "x": cam_x,
                "y": cam_y,
                "mx": cx,
                "my": cy,
                "z": 0,
                "angle": 90,
                "pitch": 0,
                "col": c,
                "row": r,
            }
        )

    # Player start south of first booth
    things.append(
        {
            "x": booths[0]["x"] if booths else 0,
            "y": (booths[0]["y"] - 40) if booths else -80,
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
                else:
                    out.append(f"{k} = false;")
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
    parts.append(f"// D64RT enemy gallery: {len(monsters)} booths, dark, friendly")
    return "\n".join(parts), booths


def write_tour_zscript(booths: list[dict], abs_indices: list[int] | None = None) -> None:
    OUT_TOUR_DIR.mkdir(parents=True, exist_ok=True)
    if abs_indices is None:
        abs_indices = [b["index"] for b in booths]
    xs = ", ".join(f"{b['x']:.1f}" for b in booths)
    ys = ", ".join(f"{b['y']:.1f}" for b in booths)
    mxs = ", ".join(f"{b.get('mx', b['x']):.1f}" for b in booths)
    mys = ", ".join(f"{b.get('my', b['y'] + 110):.1f}" for b in booths)
    labels = ",\n\t\t".join(f'"{b["label"]}"' for b in booths)
    ids = ", ".join(str(i) for i in abs_indices)
    n = len(booths)
    zs = f"""version \"4.12\"

// Auto-generated enemy gallery tour (no-aggro review).
class D64RtEnemyGalleryTour : EventHandler
{{
	const COUNT = {n};
	const DWELL = 105;
	const SHOT_AT = 45;
	private int idx;
	private int wait;
	private bool done;
	private bool shot;

	static const double PosX[] = {{ {xs} }};
	static const double PosY[] = {{ {ys} }};
	static const double MonX[] = {{ {mxs} }};
	static const double MonY[] = {{ {mys} }};
	static const int AbsIndex[] = {{ {ids} }};
	static const String Label[] = {{
		{labels}
	}};

	override void WorldLoaded(WorldEvent e)
	{{
		idx = 0;
		wait = 30;
		done = false;
		shot = true;
	}}

	private void PacifyMonsters(int booth)
	{{
		// Pin the booth monster in front of the camera (flying souls drift otherwise).
		Actor best = null;
		double bestDist = 1e9;
		ThinkerIterator it = ThinkerIterator.Create(\"Actor\");
		Actor a;
		while ((a = Actor(it.Next())) != null)
		{{
			if (!a.bIsMonster)
				continue;
			a.bFriendly = true;
			a.target = null;
			a.vel = (0, 0, 0);
			double dx = a.pos.x - MonX[booth];
			double dy = a.pos.y - MonY[booth];
			double d = dx * dx + dy * dy;
			if (d < bestDist)
			{{
				bestDist = d;
				best = a;
			}}
		}}
		if (best != null)
		{{
			// Flyers: absolute Z (floorz-relative was still collapsing to the ground).
			double z = 16.0;
			String lab = Label[booth];
			if (lab == \"LostSoul\" || lab == \"Cacodemon\" || lab == \"PainElemental\")
			{{
				z = 104.0;
				best.bNoGravity = true;
				best.bFloat = true;
				best.bCanPass = true;
			}}
			best.SetXYZ((MonX[booth], MonY[booth], z));
			best.angle = 270;
			best.vel = (0, 0, 0);
			if (level.maptime % 35 == 0)
				Console.Printf(\"D64RtEnemyPin: %s z=%.1f (want %.1f)\", best.GetClassName(), best.pos.z, z);
		}}
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
		PacifyMonsters(booth);
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
			if (idx > 0)
				PacifyMonsters(idx - 1);
			if (!shot && idx > 0 && wait == (DWELL - SHOT_AT))
			{{
				level.MakeScreenShot();
				Console.Printf(\"D64RtEnemyGalleryShot: %d %s\", AbsIndex[idx - 1], Label[idx - 1]);
				shot = true;
			}}
			wait--;
			return;
		}}

		if (idx >= COUNT)
		{{
			Console.Printf(\"D64RtEnemyGalleryTour: done (%d booths)\", COUNT);
			done = true;
			return;
		}}

		HoldView(idx);
		Console.Printf(\"D64RtEnemyGalleryTour: %d %s\", AbsIndex[idx], Label[idx]);
		idx++;
		wait = DWELL;
		shot = false;
	}}
}}
"""
    (OUT_TOUR_DIR / "ZSCRIPT").write_text(zs, encoding="utf-8")
    (OUT_TOUR_DIR / "MAPINFO").write_text(
        'GameInfo\n{\n\tAddEventHandlers = "D64RtEnemyGalleryTour"\n}\n',
        encoding="utf-8",
    )


def write_mapinfo_pk3() -> None:
    OUT_MAPINFO_DIR.mkdir(parents=True, exist_ok=True)
    text = f"""map {GALLERY_MAP} \"D64RT Enemy Gallery\"
{{
	levelnum = 98
	sky1 = \"ISUCK\"
	music = \"\"
	cluster = 1
	sucktime = 0
	par = 0
	nointermission
}}
"""
    (OUT_MAPINFO_DIR / "MAPINFO").write_text(text, encoding="utf-8")
    if OUT_MAPINFO_PK3.exists():
        OUT_MAPINFO_PK3.unlink()
    with zipfile.ZipFile(OUT_MAPINFO_PK3, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(OUT_MAPINFO_DIR / "MAPINFO", arcname="MAPINFO")


def write_scene_stub() -> Path:
    """Ensure RT scene folder exists for this PWAD map (textures.json overlay)."""
    scene_dir = (
        ROOT
        / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes"
        / SCENE
    )
    scene_dir.mkdir(parents=True, exist_ok=True)
    tex = scene_dir / "textures.json"
    if not tex.exists():
        tex.write_text('{"version": 0, "array": []}\n', encoding="utf-8")
    overlay_dir = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes" / SCENE
    overlay_dir.mkdir(parents=True, exist_ok=True)
    otex = overlay_dir / "textures.json"
    if not otex.exists():
        otex.write_text('{"version": 0, "array": []}\n', encoding="utf-8")
    return scene_dir


def pack_tour_pk3() -> Path:
    out = ROOT / r"Doom64-Retribution\d64r-enemy-gallery-tour.pk3"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in OUT_TOUR_DIR.iterdir():
            if p.is_file():
                z.write(p, arcname=p.name)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    textmap, booths = build_textmap(MONSTERS)
    (OUT_DIR / "TEXTMAP.txt").write_text(textmap, encoding="utf-8")
    items = [
        (GALLERY_MAP, b""),
        ("TEXTMAP", textmap.encode("utf-8")),
        ("ENDMAP", b""),
    ]
    OUT_WAD.write_bytes(write_wad(items))
    write_mapinfo_pk3()
    write_tour_zscript(booths)
    tour_pk3 = pack_tour_pk3()
    scene_dir = write_scene_stub()
    payload = {
        "scene": SCENE,
        "map": GALLERY_MAP,
        "wad": str(OUT_WAD),
        "grid": {"cols": int(math.ceil(math.sqrt(len(MONSTERS)))), "cell": CELL},
        "booths": booths,
    }
    BOOTHS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_WAD} ({len(MONSTERS)} booths)")
    print(f"wrote {OUT_MAPINFO_PK3}")
    print(f"wrote tour {OUT_TOUR_DIR} -> {tour_pk3}")
    print(f"wrote scene stub {scene_dir}")
    print(f"wrote {BOOTHS}")


if __name__ == "__main__":
    main()
