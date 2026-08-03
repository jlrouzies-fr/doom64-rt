"""Hold a wallturned-like pose (east wall on the right) and screenshot.

Pose: near east end, facing north — STONE2 end-wall fills the right side,
dark hall to the left. Matches screen/wallturned.png composition.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
PKG = ROOT / r"tools\d64r-gallery-wall-ab"
OUT_PK3 = ROOT / r"Doom64-Retribution\d64r-gallery-wall-ab.pk3"

# East wall on the RIGHT when facing north (yaw 90)
POS_X = 8250.0
POS_Y = 3600.0
YAW = 90.0

WARMUP = 45
# Small fwd/back so RR stays awake, then shoot mid-move
WALK = 40
SHOT_AT = 20
STEP = 18.0


def main() -> None:
    PKG.mkdir(parents=True, exist_ok=True)
    zs = f'''version "4.12"

class D64RtGalleryWallAb : EventHandler
{{
	const WARMUP = {WARMUP};
	const WALK = {WALK};
	const SHOT_AT = {SHOT_AT};
	const STEP = {STEP};
	const POS_X = {POS_X};
	const POS_Y = {POS_Y};
	const YAW = {YAW};
	private int phase;
	private int t;
	private bool done;
	private bool shot;
	private bool goingFwd;
	private double curY;

	override void WorldLoaded(WorldEvent e)
	{{
		phase = 0; t = 0; done = false; shot = false; goingFwd = true; curY = POS_Y;
	}}

	private void Place(double px, double py)
	{{
		Actor mo = players[consoleplayer].mo;
		if (mo == null) return;
		players[consoleplayer].camera = mo;
		mo.SetOrigin((px, py, 0), false);
		mo.SetOrigin((px, py, mo.floorz), false);
		mo.angle = YAW;
		mo.pitch = 0;
		mo.vel = (0, 0, 0);
	}}

	override void WorldTick()
	{{
		if (done || level.maptime < 8) return;
		if (players[consoleplayer].mo == null) return;

		if (phase == 0)
		{{
			Place(POS_X, POS_Y);
			t++;
			if (t >= WARMUP)
			{{
				phase = 1; t = 0; shot = false; goingFwd = true; curY = POS_Y;
				Console.Printf("D64RtWallAb: wallturned walk yaw=90");
			}}
			return;
		}}

		if (phase == 1)
		{{
			t++;
			if ((t % 12) == 0) goingFwd = !goingFwd;
			double dir = goingFwd ? 1.0 : -1.0;
			// Facing north: forward = +Y
			curY = curY + STEP * dir;
			if (curY > 4200.0) {{ curY = 4200.0; goingFwd = false; }}
			if (curY < 3000.0) {{ curY = 3000.0; goingFwd = true; }}
			Place(POS_X, curY);

			if (!shot && t == SHOT_AT)
			{{
				level.MakeScreenShot();
				Console.Printf("D64RtWallAbShot: wallturned t=%d", t);
				shot = true;
			}}
			if (t >= WALK)
			{{
				Console.Printf("D64RtWallAb: done");
				done = true;
			}}
		}}
	}}
}}
'''
    (PKG / "ZSCRIPT").write_text(zs, encoding="utf-8")
    (PKG / "MAPINFO").write_text(
        'GameInfo\n{\n\tAddEventHandlers = "D64RtGalleryWallAb"\n}\n',
        encoding="utf-8",
    )
    for _ in range(8):
        try:
            if OUT_PK3.exists():
                OUT_PK3.unlink()
            break
        except PermissionError:
            import time

            time.sleep(0.4)
    with zipfile.ZipFile(OUT_PK3, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in PKG.iterdir():
            if p.is_file():
                zf.write(p, arcname=p.name)
    print(f"wrote {OUT_PK3} wallturned pose x={POS_X} y={POS_Y} yaw={YAW}")


if __name__ == "__main__":
    main()
