"""Regenerate only the gallery tour ZScript from booths.json (no wad/PBR rewrite)."""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]
ROOT = PROJ_ROOT
sys.path.insert(0, str(ROOT / "tools"))
from build_texture_gallery import write_tour_zscript  # noqa: E402

BOOTHS = ROOT / r"tools\_gallery\booths.json"
# Matches build_texture_gallery pillar / standoff (booth.y is south of pillar).
PILLAR = 72.0
CAM_STANDOFF = 160.0


def _corner_cam(booth: dict) -> tuple[float, float, float, float]:
    """
    Stand close left of the south face and look ~NE so south + east faces
    both read. Uses a fixed yaw (not aim-lock) so lateral moves are visible.
    """
    cx = float(booth["x"])
    cy = float(booth["y"]) + PILLAR * 0.5 + CAM_STANDOFF
    # South of pillar, slight left; yaw aimed so SE corner sits near frame center
    # (south face dominant, east face visible on the right).
    cam_x = cx - 57.2
    cam_y = cy - (PILLAR * 0.5 + 120.0)
    ang = 65.0
    pitch = -3.0
    return cam_x, cam_y, ang, pitch


def _write_sparse_tour(booths: list[dict], idxs: list[int], view: str = "front") -> None:
    """Tour that teleports through arbitrary booth indices (prints real index)."""
    pkg = ROOT / r"tools\d64r-gallery-tour"
    view = (view or "front").strip().lower()
    if view == "corner":
        cams = [_corner_cam(b) for b in booths]
        xs = ", ".join(f"{c[0]:.1f}" for c in cams)
        ys = ", ".join(f"{c[1]:.1f}" for c in cams)
        angs = ", ".join(f"{c[2]:.1f}" for c in cams)
        pitches = ", ".join(f"{c[3]:.1f}" for c in cams)
    else:
        xs = ", ".join(f"{b['x']:.1f}" for b in booths)
        ys = ", ".join(f"{b['y']:.1f}" for b in booths)
        angs = ", ".join("90.0" for _ in booths)
        pitches = ", ".join("0.0" for _ in booths)

    ids = ", ".join(str(i) for i in idxs)
    names = ",\n\t\t".join(f'"{b["texture"]}"' for b in booths)
    n = len(booths)
    zs = f"""version \"4.12\"

// Auto-generated sparse tour — indices {idxs} view={view}
class D64RtGalleryTour : EventHandler
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
	static const double Ang[] = {{ {angs} }};
	static const double Pitch[] = {{ {pitches} }};
	static const int AbsIndex[] = {{ {ids} }};
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
		mo.angle = Ang[booth];
		mo.pitch = Pitch[booth];
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
				int b = idx > 0 ? idx - 1 : 0;
				mo.angle = Ang[b];
				mo.pitch = Pitch[b];
				mo.vel = (0, 0, 0);
			}}
			if (!shot && idx > 0 && wait == (DWELL - SHOT_AT))
			{{
				level.MakeScreenShot();
				Console.Printf(\"D64RtGalleryShot: %d %s\", AbsIndex[idx - 1], TexName[idx - 1]);
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
		Console.Printf(\"D64RtGalleryTour: %d %s\", AbsIndex[idx], TexName[idx]);
		idx++;
		wait = DWELL;
		shot = false;
	}}
}}
"""
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "ZSCRIPT").write_text(zs, encoding="utf-8")
    (pkg / "MAPINFO").write_text(
        'GameInfo\n{\n\tAddEventHandlers = "D64RtGalleryTour"\n}\n', encoding="utf-8"
    )
    print(f"wrote sparse tour ZScript for {n} booths {idxs} view={view}")


def main() -> None:
    booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
    view = os.environ.get("GALLERY_VIEW", "front").strip().lower() or "front"
    indices_env = os.environ.get("GALLERY_INDICES", "").strip()
    if indices_env:
        idxs = [int(x.strip()) for x in indices_env.split(",") if x.strip()]
        chunk = [booths[i] for i in idxs]
        _write_sparse_tour(chunk, idxs, view=view)
        print(f"tour-only: {len(chunk)} booths indices={idxs} view={view}")
        return

    start = int(os.environ.get("GALLERY_BATCH_START", "0"))
    count = int(os.environ.get("GALLERY_BATCH_COUNT", "48"))
    chunk = booths[start : start + count]
    write_tour_zscript(chunk, start)
    print(f"tour-only: {len(chunk)} booths from {start}")


if __name__ == "__main__":
    main()
