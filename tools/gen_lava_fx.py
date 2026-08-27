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

NO HAZE LAYER, AND WHY. A slab of soft, very low-alpha additive puffs above the
lake is the standard way to fake heat volume, and it cannot work on this
renderer: RT rasterizes these sprites as an ALPHA-TESTED cutout, so a radial
gradient becomes a hard-edged disc at the 0.5 threshold and the actor's alpha
(0.03) is never applied -- every puff draws at full texel strength. In game that
was a row of flat orange balls hanging over the lava. A volume above the surface
has to come from the volumetric medium (rt_fog_*), not from billboards.

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
# Not white at the hot end. A near-white droplet plus RenderStyle Add plus an
# emissive multiplier renders as a flat white pill -- which is exactly what the
# first version looked like in game. Molten rock leaving a lake is ORANGE; the
# white-hot reading comes from it being bright against a dark room, not from the
# texel being white.
SPARK_FRAMES = [
    ("A", "#ff8c1a", 1.00),  # just left the surface
    ("B", "#f05c0c", 0.90),
    ("C", "#a82408", 0.70),
    ("D", "#4a0c02", 0.45),  # crusting over on the way down
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
    d = np.sqrt( ( ( xx - cx ) / ( n * 0.26 ) ) ** 2 + ( ( yy - cy ) / ( n * 0.38 ) ) ** 2 )

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
// A lava room is otherwise completely static -- the crust does not move and the
// heat shader only modulates how bright it is. Droplets are the one element with
// real motion. They are also cheap: GZDoom does the ballistics, and RTGL1 gives
// a SPRITE a light from its texture meta, which is the one place that meta works
// at all (on a flat it does nothing, which is why the lava needed rt_lava_gi).
//
// EVERYTHING LIVES IN THE EVENT HANDLER. The first version put the per-lake
// emitters in a custom Thinker created with new("D64LavaEmitter"), and its Tick
// never ran -- the handler reported "2 lava sector(s) spitting" and not one
// spark was ever thrown. An EventHandler's WorldTick is guaranteed to run, so
// the lakes are just parallel arrays here and there is no second object whose
// lifecycle can go wrong.

class D64LavaSpark : Actor
{
    // Set false on the fragments, so a break does not cascade: without it every
    // child breaks again on its own way down and one throw turns into a swarm.
    bool canBreak;

    Default
    {
        Radius 2;
        Height 2;
        Speed 0;
        Gravity 0.55;              // heavier than a bubble, lighter than a rock
        RenderStyle "Add";
        Alpha 0.85;
        +NOBLOCKMAP +NOTELEPORT +MISSILE +THRUACTORS
        +CLIENTSIDEONLY +FORCEXYBILLBOARD +NOTRIGGER
        -SOLID
    }
    States
    {
    Spawn:
        LSPK A 8;
        LSPK B 10;
        LSPK C 10;
        LSPK D 12 A_FadeOut(0.08);
        Stop;
    }

    override void BeginPlay()
    {
        Super.BeginPlay();
        canBreak = true;
    }

    // One fragment. Kept tiny and short-lived -- these are the filament, not
    // more droplets, and at full size they read as a firework.
    void ShedBit( Vector3 v, double sc )
    {
        // Cast, or the field is invisible: Actor.Spawn returns Actor, and
        // b.canBreak on an Actor is "Unknown identifier".
        let b = D64LavaSpark( Actor.Spawn( "D64LavaSpark", pos ) );
        if( !b ) { return; }
        b.canBreak = false;
        b.vel      = v;
        b.scale    = ( sc * 0.55, sc * 0.85 );  // taller than wide: a filament, not a dot
        b.alpha    = 0.7;
        b.tics     = 4;                  // starts part-cooled, dies sooner
    }

    override void Tick()
    {
        Super.Tick();
        if( isFrozen() ) { return; }

        if( canBreak )
        {
            // A thread of small stuff torn off while it is still climbing. This
            // is what makes it read as molten rock rather than a solid pellet:
            // the surface tension loses and bits come off the back.
            if( vel.z > 1.5 && random( 0, 255 ) < 70 )
            {
                ShedBit( ( vel.x * 0.35 + frandom( -0.25, 0.25 ),
                           vel.y * 0.35 + frandom( -0.25, 0.25 ),
                           vel.z * 0.30 + frandom( -0.4, 0.4 ) ),
                         frandom( 0.5, 0.9 ) );
            }

            // And it BREAKS at the top of the arc, where a real droplet is
            // slowest and least able to hold itself together.
            if( vel.z <= 0.6 && pos.z > floorz + 12 )
            {
                canBreak = false;
                int pieces = random( 2, 4 );
                for( int i = 0; i < pieces; i++ )
                {
                    ShedBit( ( frandom( -1.6, 1.6 ), frandom( -1.6, 1.6 ), frandom( -0.4, 1.4 ) ),
                             frandom( 0.6, 1.0 ) );
                }
            }
        }

        // Die on landing. The +2.5 margin is because it is SPAWNED at floorz + 2
        // and would otherwise kill itself on its first tic.
        if( pos.z <= floorz + 2.5 && vel.z <= 0 )
        {
            Destroy();
        }
    }
}

class D64LavaFx : EventHandler
{
    // Parallel arrays, one entry per lava sector. Sector indices rather than
    // Sector refs: ZScript will not hold a dynamic array of struct pointers.
    Array<int>    secIdx;
    Array<double> minx, miny, maxx, maxy;

    int spawned;
    int tick;

    // Print level for this pk3's diagnostics. Under `rt_verbose 0` (the engine's
    // release default) they stay out of the on-screen notify area but still
    // reach the console buffer and the logfile. Set `rt_verbose 1` to see the
    // sector count and the spark trace on screen again.
    static int DiagLevel()
    {
        let cv = CVar.FindCVar( "rt_verbose" );
        return ( cv && cv.GetBool() ) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY;
    }

    // Rate is what the PLAYER sees, not what the lake covers.
    //
    // NEAR_MAX is effectively the effect's DRAW DISTANCE: nothing is spawned
    // beyond it, so the lake goes still in the distance. Doubling it quadruples
    // the area the same burst has to cover, so PER_BURST goes up with it or the
    // near field visibly thins out -- the two are not independent knobs.
    const PERIOD    = 7;     // tics between bursts
    const PER_BURST = 5;     // droplets per burst
    const NEAR_MIN  = 64;    // no closer than this, or they spawn in your face
    const NEAR_MAX  = 1400;

    override void WorldLoaded( WorldEvent e )
    {
        secIdx.Clear(); minx.Clear(); miny.Clear(); maxx.Clear(); maxy.Clear();
        spawned = 0;

        for( int i = 0; i < level.sectors.Size(); i++ )
        {
            let s = level.sectors[ i ];
            String fl = TexMan.GetName( s.GetTexture( Sector.floor ) );
            fl = fl.MakeUpper();
            if( fl.IndexOf( "HLAVA" ) != 0 && fl.IndexOf( "D64LAVA" ) != 0 ) { continue; }

            double x0 = 1e30, y0 = 1e30, x1 = -1e30, y1 = -1e30;
            for( int li = 0; li < s.lines.Size(); li++ )
            {
                let ln = s.lines[ li ];
                Vertex va = ln.v1;
                Vertex vb = ln.v2;
                if( va )
                {
                    x0 = min( x0, va.p.x ); x1 = max( x1, va.p.x );
                    y0 = min( y0, va.p.y ); y1 = max( y1, va.p.y );
                }
                if( vb )
                {
                    x0 = min( x0, vb.p.x ); x1 = max( x1, vb.p.x );
                    y0 = min( y0, vb.p.y ); y1 = max( y1, vb.p.y );
                }
            }
            if( x0 > x1 ) { continue; }

            secIdx.Push( i );
            minx.Push( x0 ); miny.Push( y0 ); maxx.Push( x1 ); maxy.Push( y1 );
        }

        if( secIdx.Size() > 0 )
        {
            Console.PrintfEx( DiagLevel(), "D64LavaFx: %d lava sector(s), %d droplet(s) every %d tics near the player",
                            secIdx.Size(), PER_BURST, PERIOD );
        }
    }

    // A SOLID ROVER OVER THE LAVA IS A LID -- the poison bubbles' gate, ported
    // so the two liquid FX cannot drift apart. See the long note in
    // gen_poison_fx.py: a sprite spawned on a sector's own floor under an
    // opaque 3D floor is drawn THROUGH it (screen/poison3Dfloor.png), and the
    // spawn height is not the fault -- FFCF_3DRESTRICT keeps floorz on the
    // fluid, correctly.
    //
    // It changes nothing in Retribution TODAY, and that is the point of
    // porting it now rather than after the next report. The one rover over
    // lava in the game is MAP20's, over sec284 (HLAVA1), and it is type 7 --
    // FF_SHOOTTHROUGH|FF_SEETHROUGH, NOT FF_SOLID. You can see the lava
    // through it, so sparks there are right and the predicate below leaves
    // them alone. The next opaque deck over a lava pit is already handled.
    static bool RoofedByRover( Sector sec, Vector2 p, double fz )
    {
        int n = sec.Get3DFloorCount();      // 0 for almost every sector in the game
        for( int i = 0; i < n; i++ )
        {
            let ff = sec.Get3DFloor( i );
            if( !ff ) { continue; }

            int need = F3DFloor.FF_EXISTS | F3DFloor.FF_SOLID | F3DFloor.FF_RENDERPLANES;
            if( ( ff.flags & need ) != need ) { continue; }

            if( ff.top.ZatPoint( p ) > fz + 1 ) { return true; }
        }
        return false;
    }

    override void WorldTick()
    {
        if( secIdx.Size() == 0 ) { return; }

        // SPAWN NEAR THE PLAYER, not uniformly across the lake.
        //
        // Uniform-over-area was the obvious reading of "a lake seethes" and it
        // is wrong in practice: MAP21's lava sector has a 2043x1392 bounding
        // box, so at four droplets a second essentially all of them land out of
        // frame and the effect is invisible while the log happily reports them
        // being thrown. What matters is the density the player SEES, so the
        // sample disc follows the camera and the rate is per-second, not
        // per-acre. Same instinct as the light grid's distance cull.
        let pmo = players[ consoleplayer ].mo;
        if( !pmo ) { return; }

        if( --tick > 0 ) { return; }
        tick = PERIOD;

        for( int n = 0; n < PER_BURST; n++ )
        {
            for( int tries = 0; tries < 10; tries++ )
            {
                double ang = frandom( 0, 360 );
                double rad = frandom( NEAR_MIN, NEAR_MAX );
                double px  = pmo.pos.x + cos( ang ) * rad;
                double py  = pmo.pos.y + sin( ang ) * rad;

                Sector sec = level.PointInSector( (px, py) );
                if( !sec ) { continue; }
                String fl = TexMan.GetName( sec.GetTexture( Sector.floor ) ).MakeUpper();
                if( fl.IndexOf( "HLAVA" ) != 0 && fl.IndexOf( "D64LAVA" ) != 0 ) { continue; }

                double fz = sec.floorplane.ZatPoint( (px, py) );
                if( RoofedByRover( sec, (px, py), fz ) ) { continue; }

                let sp = Actor.Spawn( "D64LavaSpark", (px, py, fz + 2) );
                if( sp )
                {
                    spawned++;
                    if( spawned <= 3 || ( spawned % 200 ) == 0 )
                    {
                        Console.PrintfEx( DiagLevel(), "D64LavaFx: spark %d at (%.0f %.0f %.0f), %.0f from player",
                                        spawned, px, py, fz, rad );
                    }
                    sp.vel = ( frandom( -0.55, 0.55 ), frandom( -0.55, 0.55 ), frandom( 1.8, 3.9 ) );
                    sp.scale = ( frandom( 0.5, 0.9 ), frandom( 0.5, 0.9 ) );
                }
                break;
            }
        }
    }
}
'''



# A dynamic light per frame, cooling with the droplet.
#
# Two separate light mechanisms are in play and it is worth being clear which is
# which. The sprite's textures.json entry gives RTGL1 an emissive/light for the
# BILLBOARD -- that is the one place that meta works. GLDEFS gives GZDoom a
# real dynamic light, which rt_main forwards to RTGL1 via
# RT_UploadGzDoomDynamicLights. The second is what actually throws light on the
# walls as a droplet flies past, so it is the one being asked for here.
#
# Radii stay in the teens deliberately: above rt_dynlight_rsoft a LARGER radius
# is DIMMER, so a droplet with size 64 would light less than one with size 16.
GLDEFS = """// Doom64-RT lava sprays. Radius is not brightness -- see the note in
// tools/gen_lava_fx.py before raising any of these.
pointlight D64LAVASPARK_A
{
	color 1.0 0.55 0.10
	size 18
}
pointlight D64LAVASPARK_B
{
	color 1.0 0.36 0.05
	size 16
}
pointlight D64LAVASPARK_C
{
	color 0.85 0.18 0.03
	size 13
}
pointlight D64LAVASPARK_D
{
	color 0.45 0.07 0.01
	size 9
}

object D64LavaSpark
{
	frame LSPKA { light D64LAVASPARK_A }
	frame LSPKB { light D64LAVASPARK_B }
	frame LSPKC { light D64LAVASPARK_C }
	frame LSPKD { light D64LAVASPARK_D }
}
"""


# An EventHandler in a ZSCRIPT lump is NOT registered on its own -- it has to be
# named in MAPINFO. Without this the class compiles, loads, and never runs, which
# is exactly what happened: the pk3 reported "5 lumps", the level loaded, and
# there was no D64LavaFx line and no droplets. Same one line d64r-rt-sky.pk3 uses.
MAPINFO = """GameInfo
{
	AddEventHandlers = "D64LavaFx"
}
"""


# The sprite half of the lighting, and it has to be written by the tool: this
# lives in rt/data/textures.json under build/, which is gitignored and rewritten
# wholesale by the PBR tooling, so a hand edit is neither recorded nor durable.
# Same reason tools/set_water_meta.py exists.
SPARK_META = {
    "LSPKA0": (760, [255, 140, 26], 0.7),
    "LSPKB0": (520, [240, 92, 12], 0.6),
    "LSPKC0": (280, [168, 36, 8], 0.45),
    "LSPKD0": (100, [74, 12, 2], 0.3),
}
TEXJSON = ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json"


def patch_texjson() -> int:
    import json

    if not TEXJSON.exists():
        print(f"  (skipped {TEXJSON.name}: not found -- build gzdoom first)")
        return 0
    data = json.loads(TEXJSON.read_text(encoding="utf-8"))
    seen, n = set(), 0
    for e in data["array"]:
        nm = e.get("textureName")
        if nm in SPARK_META and nm not in seen:
            seen.add(nm)
            i, c, em = SPARK_META[nm]
            e["lightIntensity"], e["lightColor"], e["emissiveMult"] = i, c, em
            n += 1
    for nm, (i, c, em) in SPARK_META.items():
        if nm not in seen:
            data["array"].append(
                {"textureName": nm, "lightIntensity": i, "lightColor": c,
                 "emissiveMult": em, "metallicDefault": 0}
            )
            n += 1
    TEXJSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return n


def build(dry: bool) -> int:
    frames = []
    for letter, hexc, scale in SPARK_FRAMES:
        size = 8 if letter in ("A", "B") else 6
        img = make_spark(hexc, scale, size)
        # centred horizontally, anchored at the bottom: a droplet hangs from its
        # own position rather than being centred on it
        frames.append((f"LSPK{letter}0", png_with_grab(img, size // 2, size)))

    print(f"{OUT.name}: {len(frames)} spark frame(s), ZSCRIPT {len(ZSCRIPT)} bytes, MAPINFO registers D64LavaFx, GLDEFS lights the droplets")
    for name, blob in frames:
        print(f"   sprites/{name}.png  {len(blob)} bytes")
    if dry:
        print("\nPass --apply to write the pk3.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MAPINFO", MAPINFO)
        z.writestr("GLDEFS", GLDEFS)
        z.writestr("ZSCRIPT", ZSCRIPT)
        for name, blob in frames:
            z.writestr(f"sprites/{name}.png", blob)
    print(f"\nwrote {OUT}")
    print(f"{patch_texjson()} spark entr(ies) written to textures.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    return build(dry=not args.apply)


if __name__ == "__main__":
    sys.exit(main())
