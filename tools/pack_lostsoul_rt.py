"""Pack Lost Soul yellow-fire sprites + offset RT glow light (no actor replace).

The stock 64LostSoul stays unchanged (BRIGHT / SoulTrans). Fire color comes from
sprite replacements + mat/_e. Cast light comes from a separate invisible-ish
LSGL glow actor spawned under each Lost Soul (EventHandler), so fire isn't
bleached by the same texture's lightIntensity bloom.
"""
from __future__ import annotations

import math
import zipfile
from pathlib import Path

from PIL import Image

from gen_enemy_eye_emissives import (
    ENEMY_GALLERY_SCENE,
    MAT,
    MAT_DEV,
    OMAT,
    open_img,
    patch_global,
    save_albedo,
    tone_skul_albedo,
    upsert_json,
    wad_lumps,
)

ROOT = Path(r"G:\AI\Doom64-RT")
OUT_DIR = ROOT / r"tools\d64r-lostsoul-rt"
OUT_PK3 = ROOT / r"Doom64-Retribution\d64r-lostsoul-rt.pk3"
SPR_DIR = OUT_DIR / "sprites"

# Offset glow: faint Add sprite + strong attached light (separate from SKUL fire).
# Floor pool under the soul (actor sits near floorz). Strong cast, moderate emis.
LSGL_LIGHT = 11000.0
LSGL_EMIS = 2.0
LSGL_HEX = "ff9028"


def make_lsgl_sprite() -> Image.Image:
    """Opaque-ish orange disc so RT uploads a real primitive + attached light."""
    size = 48
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = (size - 1) * 0.5
    rmax = size * 0.40
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - cx, y - cy) / rmax
            if d >= 1.0:
                continue
            fall = (1.0 - d) ** 1.5
            a = int(220 * fall)
            img.putpixel((x, y), (255, 130, 36, max(a, 1)))
    return img


def write_lsgl_mat(img: Image.Image) -> None:
    name = "LSGLA0"
    for d in (MAT, MAT_DEV, OMAT):
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / f"{name}.png")
        # Tiny emis so the blob itself doesn't white-out; light is via lightIntensity.
        # Bright _e disc — RT attached lights track emissive coverage like eyes.
        e = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ep = e.load()
        ap = img.load()
        for yy in range(img.size[1]):
            for xx in range(img.size[0]):
                if ap[xx, yy][3] > 8:
                    ep[xx, yy] = (255, 140, 40, 255)
        e.save(d / f"{name}_e.png")

    # Meta lives in rt/data/textures.json (+ scene overlays), not rt/mat/textures.json.
    entry = {
        "textureName": name,
        "emissiveMult": LSGL_EMIS,
        "lightIntensity": LSGL_LIGHT,
        "lightColorHEX": LSGL_HEX,
        "lightEvenOnDynamic": True,
        "noShadow": True,
    }
    # Drop accidental mat/textures.json stubs from earlier experiments.
    for stub in (MAT / "textures.json", MAT_DEV / "textures.json"):
        if stub.is_file() and stub.stat().st_size < 2048:
            stub.unlink()

    patch_global({name: entry})
    overlay_scene = (
        ROOT
        / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes"
        / "d64renemyg_map98"
        / "textures.json"
    )
    for path in (ENEMY_GALLERY_SCENE, overlay_scene):
        path.parent.mkdir(parents=True, exist_ok=True)
        upsert_json(path, {name: entry}, replace=False)


ZSCRIPT = r'''version "4.10.0"

// Soft RT cast-light under Lost Souls. Does not replace or redefine LostSoul.
class D64RtSoulGlow : Actor
{
	Default
	{
		+NOINTERACTION
		+NOBLOCKMAP
		+NOGRAVITY
		+NOCLIP
		+SYNCHRONIZED
		+DONTBLAST
		+NOTONAUTOMAP
		+FORCEXYBILLBOARD
		Radius 6;
		Height 6;
		RenderStyle "Add";
		Alpha 0.45;
		Scale 1.1;
	}
	States
	{
	Spawn:
		LSGL A -1;
		Stop;
	}
}

class D64RtSoulLightHandler : EventHandler
{
	private void AttachGlow(Actor soul)
	{
		if (soul == null || !(soul is "LostSoul") || (soul is "D64RtSoulGlow"))
			return;
		// Avoid duplicates.
		ThinkerIterator it = ThinkerIterator.Create("D64RtSoulGlow");
		Actor g;
		while ((g = Actor(it.Next())) != null)
		{
			if (g.master == soul)
				return;
		}
		g = Actor.Spawn("D64RtSoulGlow", soul.pos);
		if (g != null)
		{
			g.master = soul;
			Console.Printf("D64RtSoulGlow: attached to %s", soul.GetClassName());
		}
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		if (e.Thing != null)
			AttachGlow(e.Thing);
	}

	override void WorldLoaded(WorldEvent e)
	{
		ThinkerIterator it = ThinkerIterator.Create("Actor");
		Actor a;
		while ((a = Actor(it.Next())) != null)
		{
			if (a is "LostSoul")
				AttachGlow(a);
		}
	}

	override void WorldTick()
	{
		ThinkerIterator it = ThinkerIterator.Create("D64RtSoulGlow");
		Actor g;
		while ((g = Actor(it.Next())) != null)
		{
			if (g.master == null || g.master.health <= 0)
			{
				g.Destroy();
				continue;
			}
			// Sit on the floor under the soul — reads as a light pool, not a second fireball.
			Vector3 p = g.master.pos;
			double fz = g.master.floorz + 2.0;
			g.SetOrigin((p.x, p.y, fz), true);
			g.angle = g.master.angle;
		}
	}
}
'''

MAPINFO = """gameinfo
{
	AddEventHandlers = "D64RtSoulLightHandler"
}
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SPR_DIR.mkdir(parents=True, exist_ok=True)
    for stale in ("DECORATE",):
        p = OUT_DIR / stale
        if p.exists():
            p.unlink()

    (OUT_DIR / "ZSCRIPT").write_text(ZSCRIPT, encoding="utf-8")
    (OUT_DIR / "MAPINFO").write_text(MAPINFO, encoding="utf-8")

    lumps = wad_lumps()
    n = 0
    for name, data in lumps.items():
        if not name.startswith("SKUL"):
            continue
        img = open_img(data)
        if img is None:
            continue
        toned = tone_skul_albedo(img)
        toned.save(SPR_DIR / f"{name}.png")
        save_albedo(name, toned)
        n += 1

    glow = make_lsgl_sprite()
    glow.save(SPR_DIR / "LSGLA0.png")
    write_lsgl_mat(glow)

    if OUT_PK3.exists():
        OUT_PK3.unlink()
    with zipfile.ZipFile(OUT_PK3, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(OUT_DIR / "ZSCRIPT", arcname="ZSCRIPT")
        z.write(OUT_DIR / "MAPINFO", arcname="MAPINFO")
        for p in sorted(SPR_DIR.glob("*.png")):
            z.write(p, arcname=f"sprites/{p.name}")
    print(
        f"wrote {OUT_PK3} ({n} SKUL sprites + LSGL offset glow "
        f"light={LSGL_LIGHT} emis={LSGL_EMIS})"
    )


if __name__ == "__main__":
    main()
