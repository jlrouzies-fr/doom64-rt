"""Build d64r-lava-fx.pk3 -- lava sprays: droplets thrown out of the lava.

Why this is a MOD and not more shader. Everything else about the lava is a
surface: the crust, the heat, the light it throws. A spray is an OBJECT -- it
leaves the surface, arcs, falls back and dies -- so it needs the game sim, not
the renderer. GZDoom already has ballistics, and RTGL1 already gives a sprite a
light if its texture meta carries lightIntensity (which is the one place that
meta DOES work -- on flats it does nothing, which is the whole reason
rt_lava_light_* and rt_lava_gi exist).

So: a spawner thinker walks the lava sectors once per level, and throws a
D64LavaSpark straight up out of a random point with a random arc. The spark is a
4-frame sprite that COOLS as it flies -- white-hot, orange, deep red, dark -- and
its light cools with it, because a droplet in the air is the one part of a lava
room that has a reason to be visibly changing.

The sprites are generated here rather than drawn, at 8x8 and 16x16, in the
game's own palette range and with hard pixel edges. Two things they must get
right:

  - grAb. PIL drops the PNG offset chunk, so a sprite written with plain
    im.save() renders anchored at its top-left and sinks into the floor. The
    chunk is written by hand below.
  - They must stay CHUNKY. A soft round particle over Doom 64's art is the same
    mistake as a smooth gradient over the crackle -- see lavaFlowPixel.

Usage:
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_lava_fx.py           # report
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_lava_fx.py --apply
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Doom64-Retribution/d64r-lava-fx.pk3"

# Cooling ramp for the four frames, as sRGB. Same reasoning as the heat ramp in
# gen_lava_looks: pick the colour you want to SEE, not a linear triple.
SPARK_FRAMES = [
    ("A", "#fff0c0", 1.00),  # just left the surface, white-hot
    ("B", "#ff9a2a", 0.85),
    ("C", "#e03c08", 0.65),
    ("D", "#5a1002", 0.40),  # crusting over on the way down
]


def png_with_grab(img: Image.Image, ox: int, oy: int) -> bytes:
    """PNG bytes with a grAb chunk. PIL will not write one, and without it
    GZDoom anchors the sprite at its top-left corner: the droplet renders half
    a sprite low and clips through the floor."""
    import io

    raw = io.BytesIO()
    img.save(raw, format="PNG")
    data = raw.getvalue()

    grab = struct.pack(">ii", ox, oy)
    chunk = struct.pack(">I", len(grab)) + b"grAb" + grab
    import zlib

    chunk += struct.pack(">I", zlib.crc32(b"grAb" + grab) & 0xFFFFFFFF)

    # after IHDR (8 byte signature + 4 len + 4 type + 13 data + 4 crc)
    ihdr_end = 8 + 4 + 4 + 13 + 4
    return data[:ihdr_end] + chunk + data[ihdr_end:]


def make_spark(hex_color: str, scale: float, size: int) -> Image.Image:
    """A blobby, hard-edged droplet. No antialiasing anywhere: every texel is
    either lit or transparent, so it stays pixel art at any distance."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    n = size
    yy, xx = np.mgrid[0:n, 0:n]
    cx = cy = (n - 1) / 2.0
    # taller than wide: a droplet, not a ball
    d = np.sqrt( ( ( xx - cx ) / ( n * 0.34 ) ) ** 2 + ( ( yy - cy ) / ( n * 0.46 ) ) ** 2 )

    rgba = np.zeros((n, n, 4), dtype=np.uint8)
    core = d < 0.55
    edge = (d >= 0.55) & (d < 1.0)

    rgba[..., 0] = r
    rgba[..., 1] = g
    rgba[..., 2] = b
    # two hard steps rather than a gradient -- chunky on purpose
    rgba[..., 3] = np.where(core, 255, np.where(edge, 190, 0))
    # the core reads hotter than the rim, like the real thing
    rgba[core, 0] = min(255, int(r * 1.0))
    rgba[core, 1] = min(255, int(g * 1.15 + 20))
    rgba[core, 2] = min(255, int(b * 1.25 + 20))

    if scale < 1.0:
        rgba[..., 3] = (rgba[..., 3] * scale).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


ZSCRIPT = r'''version "4.12"

// Doom64-RT: lava sprays.
//
// A lava room is otherwise entirely static -- the crust does not move, and the
// heat shader only modulates how bright it is. Droplets are the one element
// with real motion in them, and they are cheap: GZDoom already does the
// ballistics, and RTGL1 gives a sprite a light from its texture meta, which is
// the ONE place that meta works (on a flat it does nothing at all, which is why
// the lava needed rt_lava_gi).
//
// Spawning is per-SECTOR rather than per-tic-per-map: a lake is found once at
// level load, and each one keeps its own emitter with a rate proportional to
// its area, so a puddle spits occasionally and a lake seethes.

class D64LavaSpark : Actor
{
    Default
    {
        Radius 2;
        Height 2;
        Speed 0;
        Gravity 0.55;              // heavier than a bubble, lighter than a rock
        RenderStyle "Add";
        Alpha 1.0;
        +NOBLOCKMAP +NOTELEPORT +MISSILE +NOGRAVITY_NOCLIP
        +CLIENTSIDEONLY +THRUACTORS +FORCEXYBILLBOARD
        -SOLID
    }
    States
    {
    Spawn:
        LSPK A 6 A_FadeOut(0.0);
        LSPK B 8;
        LSPK C 8;
        LSPK D 10 A_FadeOut(0.10);
        Stop;
    }

    override void Tick()
    {
        Super.Tick();
        // Die on contact with anything, including the lava it came from --
        // otherwise droplets pile up on the floor as little glowing dots and
        // the room fills with them.
        if( pos.z <= floorz + 1 || pos.z >= ceilingz - 1 )
        {
            Destroy();
        }
    }
}

class D64LavaEmitter : Thinker
{
    Sector    sec;
    double    minx, miny, maxx, maxy;
    int       period;       // tics between throws
    int       countdown;

    static D64LavaEmitter Create( Sector s, double x0, double y0, double x1, double y1, int per )
    {
        let e = new( "D64LavaEmitter" );
        e.sec = s;
        e.minx = x0; e.miny = y0; e.maxx = x1; e.maxy = y1;
        e.period = per;
        e.countdown = random( 0, per );   // so lakes do not all spit in unison
        return e;
    }

    override void Tick()
    {
        if( sec == null ) { return; }
        if( --countdown > 0 ) { return; }
        countdown = period;

        // Rejection-sample a point actually inside the sector: a lake is rarely
        // convex and its bounding box always overlaps the walkway beside it, so
        // a box sample throws droplets out of solid ground. Same lesson the
        // light grid learned, and cheap here because it runs a few times a
        // second, not per pixel.
        for( int tries = 0; tries < 6; tries++ )
        {
            double px = frandom( minx, maxx );
            double py = frandom( miny, maxy );
            if( level.PointInSector( (px, py) ) != sec ) { continue; }

            double fz = sec.floorplane.ZatPoint( (px, py) );
            let sp = Actor.Spawn( "D64LavaSpark", (px, py, fz + 2) );
            if( sp )
            {
                // Mostly up, a little sideways. 6..11 is roughly a half-second
                // hang, which is long enough to read as an arc.
                sp.vel = ( frandom( -0.9, 0.9 ), frandom( -0.9, 0.9 ), frandom( 5.0, 11.0 ) );
                sp.scale = ( frandom( 0.6, 1.3 ), frandom( 0.6, 1.3 ) );
            }
            return;
        }
    }
}

class D64LavaFx : EventHandler
{
    // Rate is per 1024x1024 map units of lake, so it scales with the water --
    // a fixed per-sector rate makes a puddle as busy as a lake.
    const TICS_PER_THROW_PER_AREA = 26;

    override void WorldLoaded( WorldEvent e )
    {
        if( level.maptime > 0 ) { return; }

        int found = 0;
        for( int i = 0; i < level.sectors.Size(); i++ )
        {
            let s = level.sectors[ i ];
            String fl = TexMan.GetName( s.GetTexture( Sector.floor ) );
            fl = fl.MakeUpper();
            if( fl.IndexOf( "HLAVA" ) != 0 && fl.IndexOf( "D64LAVA" ) != 0 ) { continue; }

            double minx = 1e30, miny = 1e30, maxx = -1e30, maxy = -1e30;
            for( int li = 0; li < s.lines.Size(); li++ )
            {
                let ln = s.lines[ li ];
                for( int v = 0; v < 2; v++ )
                {
                    Vertex vt = ( v == 0 ) ? ln.v1 : ln.v2;
                    minx = min( minx, vt.p.x ); maxx = max( maxx, vt.p.x );
                    miny = min( miny, vt.p.y ); maxy = max( maxy, vt.p.y );
                }
            }
            if( minx > maxx ) { continue; }

            double area = ( maxx - minx ) * ( maxy - miny );
            int per = int( clamp( TICS_PER_THROW_PER_AREA * 1048576.0 / max( area, 1.0 ), 3, 140 ) );
            D64LavaEmitter.Create( s, minx, miny, maxx, maxy, per );
            found++;
        }

        if( found > 0 )
        {
            Console.Printf( "D64LavaFx: %d lava sector(s) spitting", found );
        }
    }
}
'''


def build(dry: bool) -> int:
    frames = []
    for letter, hexc, scale in SPARK_FRAMES:
        size = 16 if letter in ("A", "B") else 8
        img = make_spark(hexc, scale, size)
        # centred horizontally, anchored at the bottom: a droplet hangs from its
        # own position rather than being centred on it
        frames.append((f"LSPK{letter}0", png_with_grab(img, size // 2, size)))

    print(f"{OUT.name}: {len(frames)} spark frame(s), ZSCRIPT {len(ZSCRIPT)} bytes")
    for name, blob in frames:
        print(f"   sprites/{name}.png  {len(blob)} bytes")
    if dry:
        print("\nPass --apply to write the pk3.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("ZSCRIPT", ZSCRIPT)
        for name, blob in frames:
            z.writestr(f"sprites/{name}.png", blob)
    print(f"\nwrote {OUT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    return build(dry=not args.apply)


if __name__ == "__main__":
    sys.exit(main())
