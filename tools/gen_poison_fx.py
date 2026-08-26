"""Build d64r-poison-fx.pk3 -- bubbles that swell out of the poison and burst.

The same split as the lava sprays (tools/gen_lava_fx.py): everything else about
a nukage lake is a SURFACE, but a bubble is an OBJECT -- it grows, it leaves the
plane of the floor, it pops and it is gone -- so it belongs to the game sim, not
to the renderer. And it lands on the one place RTGL1 texture meta actually
works: lightIntensity on a SPRITE gives it a light. On a flat it does nothing,
which is the whole reason rt_lava_light_* had to be written in C++.

WHICH FLOORS. D64N1_01 is the poison the user asked about, but it is frame 1 of
64 -- the ANIMDEFS sequence runs D64N1_01..D64N1_64, and GetTexture() returns
whichever frame is showing this tic. An exact-name match therefore succeeds on
1 tic in 64 and the bubbles flicker on and off. The match is a PREFIX, "D64N",
which covers D64N1_*, D64N2_* and the two D64NUKG stills, and nothing else in
the texture set (checked against rt/data/textures.json).

Poison floors in Retribution, from the UDMF: MAP07 (50 sectors -- the map to
test on), MAP16 (1), MAP18 (2), MAP22 (4), MAP24 (4), MAP25 (1), MAP34 (the
texture-sampler map, one of each fluid).

THE SPRITES ARE SLICED, NOT DRAWN. tools/_assets/poisonbubble.png is authored
art: five growth stages and a burst, laid out left to right on one row with
uneven gaps. The slicer finds the occupied column runs and merges the smallest
gaps until exactly six clusters remain -- the burst is a RING of separate
droplets, so it reads as four runs and would otherwise be counted as four
frames. Two things the output must get right:

  - grAb. PIL drops the PNG offset chunk, so a sprite written with plain
    im.save() is anchored at its top-left and renders sunk into the floor. The
    chunk is written by hand below. The growth frames anchor at their own
    bottom, so a bubble meets the fluid where it is spawned; the burst anchors
    on the ring's centre pushed down by half the last bubble's height, so the
    ring appears where the bubble WAS rather than jumping up the moment it pops.
  - HARD ALPHA. RT rasterizes these sprites as an alpha-tested cutout: a soft
    edge becomes a hard edge at the 0.5 threshold anyway, and the actor's own
    Alpha is never applied. So the alpha is binarised here, at the same
    threshold the renderer will use, and nothing about the look is left to a
    RenderStyle that this path ignores.

Usage:
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_poison_fx.py           # report
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_poison_fx.py --apply
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "tools/_assets/poisonbubble.png"
OUT = ROOT / "Doom64-Retribution/d64r-poison-fx.pk3"

# Sprite name. Four characters plus frame letter plus rotation, like any Doom
# sprite: PBUBA0 .. PBUBF0.
SPR = "PBUB"
FRAMES = "ABCDEF"

# How tall the LAST growth frame is, in sprite pixels == map units at scale 1.
# A D64N flat is 64 units square, so 20 puts roughly three bubbles across one
# tile of the texture -- big enough to read as a bubble, small enough that a
# lake does not turn into a bag of marbles. Every other frame is scaled from
# this one by the ratio it has on the sheet, so the growth curve is the art's.
TARGET_H = 20

ALPHA_CUT = 128  # the alpha-test threshold the RT path uses

# THE SATURATION LADDER, AND WHY IT IS A LADDER AND NOT A DIAL.
#
# The obvious way to tint a sprite at runtime is a GZDoom translation, and on
# this renderer it silently breaks the effect. RTHardwareTexture appends a
# per-translation SUFFIX to the RTGL1 material name (rt_buffers.h -- it has to,
# or every translation of a sprite collides on one name and RTGL1 keeps the
# first). So a translated PBUBA0 is uploaded as a DIFFERENT material, which has
# no entry in textures.json, which means it loses lightIntensity and
# emissiveMult: the bubble would change colour and stop glowing. Per-actor
# SetShade has the same problem from the other end -- the RT path never reads it.
#
# So saturation is baked, at build time, into one sprite set per rung, each with
# its own textures.json entries. d64_poison_sat picks the nearest rung. Five is
# enough to find the look; if a value between two rungs is wanted, move a rung
# here and rebuild rather than adding more.
#
# PBUB stays the rung the rest of the code treats as default, so the lab's probe
# row keeps referencing one stable sprite name.
#
# MATCHED TO THE POOL, MEASURED OFF A FRAME -- not to the flat's albedo.
#
# D64NUKG1, the patch D64N1_01 is built from, is nearly black: mean RGB 4,12,1,
# value never above 0.22. Sampling it says "the poison is dark green" and tells
# you nothing useful, because almost all the green you see is the RT water
# shader on top of it. So the reference is the RENDERED pool, taken from a lab
# capture (MAP91, `dense`):
#
#     pool            hue 105 deg   sat 0.40   val 0.25
#     bubble, before  hue  98 deg   sat 0.73   val 0.60
#
# The bubbles were 1.8x the pool's saturation and 7 degrees off its hue, which
# is exactly the "too saturated" that was reported. BASE_SAT brings them onto
# it; HUE_SHIFT is a ROTATION, not an assignment, so the art's own hue variation
# (the highlights run yellower than the body) survives.
#
# They stay brighter than the pool by a wide margin -- val 0.60 against 0.25 --
# which is the "just a bit brighter" half of the brief, and it comes from the
# art plus the emissive rather than from a value push.
POOL_HUE_DEG = 105.0
BUBBLE_HUE_DEG = 98.1
HUE_SHIFT = ( POOL_HUE_DEG - BUBBLE_HUE_DEG ) / 360.0
BASE_SAT = 0.575          # 0.404 / 0.733, measured
VAL_LIFT = 1.06           # a touch, so desaturating does not read as dulling

# The rungs are RELATIVE TO SHIPPING: d64_poison_sat 1 is the matched look, 2 is
# roughly the art as drawn, 0 is grey. That is the scale the cvar should be read
# on -- "how much more saturated than shipping" -- rather than an absolute whose
# value only means something next to a table in this file.
SAT_SETS = [
    ("PBUA", 0.00),   # grey -- the control for "is the green coming from the art"
    ("PBUC", 0.50),
    ("PBUB", 1.00),   # matched to the pool. The default, and what the lab probes use.
    ("PBUD", 1.50),
    ("PBUE", 2.00),   # about the original, over-saturated art
]
SAT_DEFAULT_INDEX = 2


def retint(img: Image.Image, sat_rung: float) -> Image.Image:
    """Rotate hue onto the pool's, scale chroma by BASE_SAT * rung, lift value.

    Per-pixel through colorsys rather than a vectorised transform: the largest
    frame is 23x23, so it costs nothing, and hand-rolling an HSV round trip in
    numpy is how off-by-one hue wraps get shipped."""
    import colorsys

    a = np.asarray(img).astype(np.float32).copy()
    h, w, _ = a.shape
    for y in range(h):
        for x in range(w):
            if a[y, x, 3] <= 0:
                continue
            r, g, b = a[y, x, 0] / 255.0, a[y, x, 1] / 255.0, a[y, x, 2] / 255.0
            hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
            hh = (hh + HUE_SHIFT) % 1.0
            ss = min(1.0, ss * BASE_SAT * sat_rung)
            vv = min(1.0, vv * VAL_LIFT)
            r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
            a[y, x, 0], a[y, x, 1], a[y, x, 2] = r * 255.0, g * 255.0, b * 255.0
    return Image.fromarray(a.round().clip(0, 255).astype(np.uint8), "RGBA")


def png_with_grab(img: Image.Image, ox: int, oy: int) -> bytes:
    """PNG bytes with a grAb chunk. PIL will not write one, and without it
    GZDoom anchors the sprite at its top-left corner: the bubble renders half a
    sprite low and clips through the floor."""
    import io

    raw = io.BytesIO()
    img.save(raw, format="PNG")
    data = raw.getvalue()

    grab = struct.pack(">ii", ox, oy)
    chunk = struct.pack(">I", len(grab)) + b"grAb" + grab
    chunk += struct.pack(">I", zlib.crc32(b"grAb" + grab) & 0xFFFFFFFF)

    # after IHDR (8 byte signature + 4 len + 4 type + 13 data + 4 crc)
    ihdr_end = 8 + 4 + 4 + 13 + 4
    return data[:ihdr_end] + chunk + data[ihdr_end:]


def column_clusters(occ, want):
    """Occupied column runs, merged across the smallest gaps until `want`
    clusters remain. The burst frame is a ring of loose droplets with 2-5 px of
    empty column between them; the growth frames are 29-49 px apart. Merging by
    gap size rather than against a fixed threshold picks that apart without a
    magic number that would have to be retuned for a redrawn sheet."""
    cols = occ.any(0)
    runs, start = [], None
    for i, v in enumerate(cols):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(cols) - 1))

    while len(runs) > want:
        gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
        j = int(np.argmin(gaps))
        runs[j : j + 2] = [(runs[j][0], runs[j + 1][1])]
    return runs


def slice_sheet(sheet: Path):
    """Six (image, ox, oy) triples, already scaled and alpha-cut."""
    src = np.asarray(Image.open(sheet).convert("RGBA"))
    occ = src[..., 3] > 16
    runs = column_clusters(occ, len(FRAMES))
    if len(runs) != len(FRAMES):
        raise SystemExit(f"{sheet.name}: found {len(runs)} frame(s), expected {len(FRAMES)}")

    boxes = []
    for x0, x1 in runs:
        rows = np.where(occ[:, x0 : x1 + 1].any(1))[0]
        boxes.append((x0, x1, int(rows.min()), int(rows.max())))

    # Scale is set by the last GROWTH frame, not by the burst: the burst is a
    # ring wider than the bubble it came from, and letting it drive the scale
    # would shrink every bubble to pay for it.
    last = boxes[len(FRAMES) - 2]
    s = TARGET_H / (last[3] - last[2] + 1)
    half_last = (last[3] - last[2] + 1) * 0.5

    out = []
    for i, (x0, x1, y0, y1) in enumerate(boxes):
        crop = Image.fromarray(src[y0 : y1 + 1, x0 : x1 + 1], "RGBA")
        w = max(1, int(round(crop.width * s)))
        h = max(1, int(round(crop.height * s)))
        small = crop.resize((w, h), Image.LANCZOS)

        a = np.asarray(small).copy()
        a[..., 3] = np.where(a[..., 3] >= ALPHA_CUT, 255, 0)
        img = Image.fromarray(a, "RGBA")

        if i < len(FRAMES) - 1:
            ox, oy = w // 2, h                       # anchored on the fluid
        else:
            # The ring, placed where the bubble was: its own centroid pushed
            # down by half the last bubble's height.
            sub = occ[y0 : y1 + 1, x0 : x1 + 1]
            cy = float(np.where(sub.any(1))[0].mean())
            cx = float(np.where(sub.any(0))[0].mean())
            ox = int(round(cx * s))
            oy = int(round((cy + half_last) * s))
        out.append((img, ox, oy))
    return out


ZSCRIPT = r'''version "4.12"

// Doom64-RT: poison bubbles.
//
// A nukage lake is otherwise completely static -- the flat cycles through its
// 64 ANIMDEFS frames and nothing else about the room changes. A bubble is the
// one element with real motion, and it is cheap: six frames, no collision, and
// RTGL1 gives a SPRITE a light from its texture meta, which is the one place
// that meta works at all.
//
// EVERYTHING LIVES IN THE EVENT HANDLER, for the reason written up in
// gen_lava_fx.py: a custom Thinker's Tick did not run there, and the effect
// reported itself working while spawning nothing. An EventHandler's WorldTick
// is guaranteed to run, so there is no second object whose lifecycle can go
// wrong.

class D64PoisonBubble : Actor
{
    Default
    {
        Radius 1;
        Height 1;
        Speed 0;
        RenderStyle "Normal";
        // Opaque on purpose. RT rasterizes the sprite as an alpha-tested
        // cutout and never applies the actor's Alpha, so a translucent bubble
        // is a thing you can write and not a thing you can see -- and a bubble
        // of sludge is not translucent anyway.
        +NOBLOCKMAP +NOGRAVITY +NOCLIP +NOTELEPORT +THRUACTORS
        +CLIENTSIDEONLY +FORCEXYBILLBOARD +NOTRIGGER +DONTSPLASH
        -SOLID
    }
    States
    {
__STATES__
    }

    // WHICH RUNG. Read once, at spawn, and jumped to as a STATE -- the sprite
    // name is what carries the material identity, so this is the only place the
    // choice can be made without losing the textures.json entry (see the note
    // above SAT_SETS in gen_poison_fx.py).
    override void PostBeginPlay()
    {
        Super.PostBeginPlay();

        let cv = CVar.FindCVar( "d64_poison_sat" );
        double s = cv ? cv.GetFloat() : 1.0;

        State st;
__SATPICK__
        if( st ) { SetState( st ); }

        AttachPoisonLight();
    }

    // A REAL DYNAMIC LIGHT, and this time it does not blow the sprite out.
    //
    // The first version put a GLDEFS pointlight on every frame and every bubble
    // rendered as a white pill: a light sitting inside a 20-unit billboard is at
    // zero distance from it, so the sprite lit ITSELF into clipping and the art
    // was gone. That is why GLDEFS was dropped, and the effect then leaned
    // entirely on textures.json emissive -- which looked fine in a LIT lab and
    // turned out to cast nothing at all in a dark corridor. Both halves of that
    // were wrong.
    //
    // LF_DONTLIGHTSELF is what makes the light possible: the bubble lights the
    // room and not its own billboard, so there is no pill and there is real
    // green on the walls.
    //
    // Attached from ZScript rather than declared in GLDEFS because a GLDEFS
    // light is fixed at parse time, and this one has to be tunable --
    // d64_poison_light scales it, 0 turns it off.
    //
    // SIZE IS NOT BRIGHTNESS. Above rt_dynlight_rsoft (pinned at 20) a LARGER
    // radius is DIMMER, so d64_poison_lsize is clamped under it: brightness
    // comes from the colour, which is what the scale multiplies.
    void AttachPoisonLight()
    {
        let cvOn = CVar.FindCVar( "d64_poison_light" );
        double li = cvOn ? cvOn.GetFloat() : 1.0;
        if( li <= 0.01 ) { return; }

        let cvSz = CVar.FindCVar( "d64_poison_lsize" );
        int lsz = int( clamp( cvSz ? cvSz.GetFloat() : 16.0, 1, 20 ) );

        // A green a little cooler than the sprite, so the light reads as the
        // poison's rather than as a lamp someone left in the sludge.
        int r = int( clamp(  40 * li, 0, 255 ) );
        int g = int( clamp( 170 * li, 0, 255 ) );
        int b = int( clamp(  35 * li, 0, 255 ) );

        A_AttachLight( 'pbub', DynamicLight.PointLight, Color( 255, r, g, b ),
                       lsz, 0, DynamicLight.LF_DONTLIGHTSELF );
    }

    override void Tick()
    {
        Super.Tick();
        if( isFrozen() ) { return; }
        // The rise slows as the bubble swells, so it settles at the surface
        // instead of drifting off it over the 43 tics it is alive.
        vel.z *= 0.94;
    }
}

class D64PoisonFx : EventHandler
{
    // One entry per poison sector, with its bounding box. See WorldLoaded.
    Array<int>    secIdx;
    Array<double> minx, miny, maxx, maxy;

    int poisonSectors;
    int spawned;
    int tick;

    // THE INSTRUMENT. "Nothing is happening" and "one in forty samples lands on
    // poison" look identical from inside the game, and the first three spawn
    // lines cannot tell them apart -- they print and then the effect goes quiet.
    // What matters is the HIT RATE: how many sampled points fell on a poison
    // floor. On a lake it is near 1; on a corridor it is what makes the effect
    // disappear.
    //
    // NOT called `tries`: the sampling loop below already declares
    // `for( int tries = 0; ... )`, and a field of that name is shadowed by it --
    // the counter reads 0 forever while the loop quietly runs half its attempts.
    int samples;
    int hits;
    int report;

    // Sampled points that DID land on poison and were then thrown away because
    // a solid 3D floor stands over them (RoofedByRover). Counted apart from
    // `hits` on purpose: the sampler found the fluid, so a low hit rate and a
    // roofed lake are different faults and must not average into one number.
    int roofed;

    // Rate is what the PLAYER sees, not what the lake covers. MAP07 has 50
    // poison sectors; spawning uniformly over their area puts nearly every
    // bubble out of frame while the log cheerfully reports them thrown. The
    // sample disc follows the camera and the rate is per second, not per acre
    // -- the same correction the lava sprays needed.
    //
    // d64_poison_dist is the effect's DRAW DISTANCE. Raising it quadruples the
    // area the same burst has to cover, so the rate goes up with it or the near
    // field visibly thins out; the two are not independent knobs.
    const PERIOD    = 9;     // tics between bursts
    const PER_BURST = 3;     // bubbles per burst
    const NEAR_MIN  = 40;    // no closer than this, or they swell in your face

    static int DiagLevel()
    {
        let cv = CVar.FindCVar( "rt_verbose" );
        return ( cv && cv.GetBool() ) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY;
    }

    static bool IsPoison( String fl )
    {
        // PREFIX, not an exact name. D64N1_01 is frame 1 of a 64-frame ANIMDEFS
        // sequence and GetTexture returns the frame showing right now, so an
        // exact match hits on 1 tic in 64 and the bubbles strobe.
        return fl.MakeUpper().IndexOf( "D64N" ) == 0;
    }

    // A SOLID ROVER OVER THE POISON IS A LID.
    //
    // MAP07's nukage rooms have their authored bridge decks back (the 3D-floor
    // strip wad was retired 2026-08-23). The deck hides the fluid, so it has to
    // hide the bubbles -- and it did not: they drew ON the metal,
    // screen/poison3Dfloor.png.
    //
    // THIS IS NOT A SPAWN-HEIGHT BUG, and it is worth writing down because the
    // obvious reading is that the bubble got clamped up onto the deck. It does
    // not. Measured out of the UDMF: sec164 and sec202 are the only two nukage
    // sectors in the game with a rover over them; the fluid is at z -174 and
    // the slabs run -30..42 and -30..102, so there is 144 UNITS of clearance.
    // Actor.Spawn calls P_FindFloorCeiling with FFCF_ONLYSPAWNPOS, which sets
    // FFCF_3DRESTRICT and disables the step-up branch of NextLowestFloorAt, so
    // floorz stays on the poison; and the rise (0.06-0.20 damped x0.94) totals
    // about 3 units. The bubble is where it belongs and is drawn through solid
    // geometry -- the same 3D-floor blindness docs/rt-impact-fx.md records for
    // every RT particle system. Suppressing the bubble is the game sim's half,
    // it is correct whether or not the renderer's half is ever closed, and it
    // takes the tick and the dynamic light with it.
    //
    // FF_SOLID *and* FF_RENDERPLANES on purpose. An invisible collision-only
    // rover is not a lid, and neither is a see-through decorative slab
    // (ABS05's floating blood, type 7) -- you can see the fluid through it, so
    // a bubble there is right. FF_SOLID is also the predicate the engine's own
    // NextLowestFloorAt uses for "is this a floor".
    static bool RoofedByRover( Sector sec, Vector2 p, double fz )
    {
        int n = sec.Get3DFloorCount();      // 0 for almost every sector in the game
        for( int i = 0; i < n; i++ )
        {
            let ff = sec.Get3DFloor( i );
            if( !ff ) { continue; }

            int need = F3DFloor.FF_EXISTS | F3DFloor.FF_SOLID | F3DFloor.FF_RENDERPLANES;
            if( ( ff.flags & need ) != need ) { continue; }

            // Above the fluid, not merely present: a rover flush with the plane
            // or below it covers nothing. The 1-unit slack matches the epsilon
            // the fluid's own plane comparisons use elsewhere.
            if( ff.top.ZatPoint( p ) > fz + 1 ) { return true; }
        }
        return false;
    }

    override void WorldLoaded( WorldEvent e )
    {
        poisonSectors = 0;
        spawned = 0;
        tick = 0;
        samples = 0;
        hits = 0;
        roofed = 0;
        report = 0;

        secIdx.Clear(); minx.Clear(); miny.Clear(); maxx.Clear(); maxy.Clear();

        for( int i = 0; i < level.sectors.Size(); i++ )
        {
            let s = level.sectors[ i ];
            if( !IsPoison( TexMan.GetName( s.GetTexture( Sector.floor ) ) ) ) { continue; }

            // Bounding box from the sector's own linedefs. Sector indices rather
            // than Sector refs: ZScript will not hold a dynamic array of struct
            // pointers, so these are parallel arrays -- same shape as the lava
            // sprays' lake list.
            double x0 = 1e30, y0 = 1e30, x1 = -1e30, y1 = -1e30;
            for( int li = 0; li < s.lines.Size(); li++ )
            {
                let ln = s.lines[ li ];
                for( int v = 0; v < 2; v++ )
                {
                    Vertex vx = ( v == 0 ) ? ln.v1 : ln.v2;
                    if( !vx ) { continue; }
                    x0 = min( x0, vx.p.x ); x1 = max( x1, vx.p.x );
                    y0 = min( y0, vx.p.y ); y1 = max( y1, vx.p.y );
                }
            }
            if( x0 > x1 ) { continue; }

            secIdx.Push( i );
            minx.Push( x0 ); miny.Push( y0 ); maxx.Push( x1 ); maxy.Push( y1 );
            poisonSectors++;
        }

        // BEHIND d64_poison_debug, like every other line this handler prints.
        // It used to be unconditional -- useful while the effect was being
        // built, noise on every level load once it works. rt_verbose is not the
        // gate: that is the engine's switch and it is on in the dev launchers,
        // so the line came back the moment anyone used one.
        let cvDbg = CVar.FindCVar( "d64_poison_debug" );
        if( poisonSectors > 0 && cvDbg && cvDbg.GetBool() )
        {
            Console.PrintfEx( DiagLevel(), "D64PoisonFx: %d poison sector(s), %d bubble(s) every %d tics near the player",
                            poisonSectors, PER_BURST, PERIOD );
        }
    }

    override void WorldTick()
    {
        if( poisonSectors == 0 ) { return; }

        // TWO switches, on purpose -- see the note above CVARINFO. The player's
        // choice (Options > Effects) is archived; the A/B master is not. Either
        // one off means no bubbles.
        let cvOn = CVar.FindCVar( "d64_poison_fx" );
        if( cvOn && !cvOn.GetBool() ) { return; }

        let cvUser = CVar.FindCVar( "d64_poison_bubbles" );
        if( cvUser && !cvUser.GetBool() ) { return; }

        let pmo = players[ consoleplayer ].mo;
        if( !pmo ) { return; }

        if( --tick > 0 ) { return; }
        tick = PERIOD;

        let cvRate = CVar.FindCVar( "d64_poison_rate" );
        let cvDist = CVar.FindCVar( "d64_poison_dist" );
        let cvSize = CVar.FindCVar( "d64_poison_size" );
        let cvZ    = CVar.FindCVar( "d64_poison_z" );
        double rate = cvRate ? cvRate.GetFloat() : 1.0;
        double far  = cvDist ? cvDist.GetFloat() : 1100.0;
        // Clamped low rather than allowed to reach 0: a zero scale is an
        // invisible bubble that still ticks, lights the room and costs the
        // same, which reads as "the effect broke". d64_poison_fx is the off
        // switch and it is the only one.
        double szMul = cvSize ? max( 0.05, cvSize.GetFloat() ) : 1.0;
        double zOff  = cvZ ? cvZ.GetFloat() : 1.0;

        // The gate is a cvar so the before and the after are one arm rather
        // than two builds. Without it "no bubbles on the deck" and "the code
        // never ran" produce the same screenshot.
        let cvRoof  = CVar.FindCVar( "d64_poison_roofgate" );
        bool roofGate = cvRoof ? cvRoof.GetBool() : true;
        if( far <= NEAR_MIN ) { return; }

        // Fractional rates still work: the remainder is the probability of one
        // more bubble, so 0.5 is genuinely half as many rather than the same
        // count rounded back up.
        let cvDbg2 = CVar.FindCVar( "d64_poison_debug" );
        if( cvDbg2 && cvDbg2.GetBool() && ++report >= 4 )
        {
            report = 0;
            Console.PrintfEx( DiagLevel(), "D64PoisonFx: %d spawned, %d/%d samples hit poison (%d%%), %d roofed by a 3D floor",
                            spawned, hits, samples, samples > 0 ? ( 100 * hits ) / samples : 0, roofed );
        }

        // The sectors in range, rebuilt each burst because the player moves.
        // Bbox-to-point distance: clamp the player into the box and measure to
        // that, so a long channel counts as near along its whole length rather
        // than by its centre.
        Array<int> cand;
        for( int i = 0; i < secIdx.Size(); i++ )
        {
            double cx = clamp( pmo.pos.x, minx[ i ], maxx[ i ] );
            double cy = clamp( pmo.pos.y, miny[ i ], maxy[ i ] );
            if( ( ( cx, cy ) - ( pmo.pos.x, pmo.pos.y ) ).Length() <= far )
            {
                cand.Push( i );
            }
        }
        if( cand.Size() == 0 ) { return; }

        double want = PER_BURST * rate;
        int n = int( want );
        if( frandom( 0, 1 ) < want - n ) { n++; }

        for( int i = 0; i < n; i++ )
        {
            for( int tries = 0; tries < 10; tries++ )
            {
                // SAMPLE THE POISON, NOT THE WORLD.
                //
                // This used to throw a dart at a disc around the player and keep
                // it if it happened to land on a poison floor. On the lab's lake
                // that hits 17% of the time; in MAP07, where the nukage runs
                // down corridors a couple of hundred units wide, it hits 5% --
                // so most bubbles were never placed at all, and the few that
                // were landed wherever the disc happened to clip some other
                // pool. That is the "bubble 1000 from player" in the report,
                // with the poison underfoot staying still.
                //
                // Now a poison SECTOR is picked first, from those whose bbox is
                // in range, and the point is drawn inside that sector. The
                // PointInSector check stays -- a bbox is not the sector, and an
                // L-shaped pool has corners that are not in it -- but it is now
                // rejecting the odd corner rather than the entire map.
                if( cand.Size() == 0 ) { break; }
                int ci  = cand[ random( 0, cand.Size() - 1 ) ];
                double px = frandom( minx[ ci ], maxx[ ci ] );
                double py = frandom( miny[ ci ], maxy[ ci ] );

                samples++;
                Sector sec = level.PointInSector( (px, py) );
                if( !sec ) { continue; }
                if( sec.Index() != secIdx[ ci ] ) { continue; }

                // Distance still matters: a lake can be far wider than the draw
                // distance, and a bubble behind you at 2000 units is cost with
                // nothing to show for it.
                double rad = ( ( px, py ) - ( pmo.pos.x, pmo.pos.y ) ).Length();
                if( rad < NEAR_MIN || rad > far ) { continue; }
                hits++;

                // SPAWNED ON THE PLANE, OFFSET WHEN DRAWN. d64_poison_z used
                // to be added to the spawn z, and negative values did nothing:
                // P_ZMovement clamps an actor to floorz on its first tic, so
                // every bubble asked to sit below the surface was pushed back
                // up onto it. SpriteOffset.Y is added straight to the sprite
                // quad's world z (hw_sprites.cpp: `z1 += offy; z2 += offy`)
                // with no clamp anywhere, so it goes both ways.
                //
                // The cvar is still the WHOLE offset, not a delta on a hidden
                // constant: what it says is where the bubble's foot is drawn,
                // and the sprite is bottom-anchored by grAb. Negative sinks it
                // into the poison, which is the useful direction -- a bubble
                // that breaks the plane reads better than one resting on it.
                double fz = sec.floorplane.ZatPoint( (px, py) );

                // Rejected as a SAMPLE, not as a spawn: `continue` sends the
                // 10-try loop looking for another point, so the open half of a
                // partly-decked pool keeps its full density instead of losing
                // one bubble per covered draw. hits++ above already fired, and
                // that is right -- the sampler did find poison here.
                if( roofGate && RoofedByRover( sec, (px, py), fz ) ) { roofed++; continue; }

                let b = D64PoisonBubble( Actor.Spawn( "D64PoisonBubble", (px, py, fz) ) );
                if( b )
                {
                    spawned++;
                    // A bubble is round in plan, so the two scales stay equal
                    // -- the lava spark stretches its filaments on purpose,
                    // this one would just look like an egg.
                    // The per-bubble variation stays, and d64_poison_size
                    // scales the whole spread -- so raising it makes a bigger
                    // lake, not a uniform one.
                    //
                    // THIS SPREAD IS THE AUTHORED ART AND DOES NOT MOVE.
                    // 0.7-1.25 draws the 20 px sprite at 20 px; the shipping
                    // size lives entirely in d64_poison_size's DEFAULT, below
                    // in CVARINFO.
                    //
                    // It is written down because two rounds of retuning were
                    // lost to the other arrangement: the multiplier was baked
                    // in here AND the cvar kept defaulting to 1, so "make it
                    // 0.7" meant a different absolute size each time and the
                    // lab's `small` arm drifted with it. One number, one place,
                    // and `size 1` always means the art at its drawn size.
                    double sc = frandom( 0.7, 1.25 ) * szMul;
                    b.scale = ( sc, sc );
                    b.SpriteOffset = ( 0, zOff );
                    b.vel   = ( 0, 0, frandom( 0.06, 0.20 ) );

                    let cvDbg = CVar.FindCVar( "d64_poison_debug" );
                    if( cvDbg && cvDbg.GetBool() && ( spawned <= 3 || ( spawned % 200 ) == 0 ) )
                    {
                        Console.PrintfEx( DiagLevel(), "D64PoisonFx: bubble %d at (%.0f %.0f %.0f), %.0f from player",
                                        spawned, px, py, fz, rad );
                    }
                }
                break;
            }
        }
    }
}
'''


# NOSAVE, and that is not incidental. An A/B knob that persists means the next
# run silently inherits whichever arm was tried last, and a null result gets
# blamed on the change instead of on the leftover value.
#
# d64_poison_bubbles IS THE ONE EXCEPTION, and it is a different kind of thing.
# It is the player's setting, driven by Options > Effects, and a setting that
# forgets itself on quit is broken. So the switch is split in two:
#
#   d64_poison_bubbles  archived   what the PLAYER chose. The menu writes it.
#   d64_poison_fx       nosave     the A/B master. Arms and labs write it.
#
# The handler needs both. Merging them would archive the A/B master, and then
# one `ab-poison.cmd off` would turn the effect off for good on a machine that
# never asked -- the exact fault the rest of this file is nosave to avoid.
# Because it is archived, every arm and every lab launch must pin
# d64_poison_bubbles explicitly, or a player who turned the effect off in the
# menu silently kills every future A/B run.
CVARINFO = """server nosave bool  d64_poison_fx    = true;
server nosave float d64_poison_rate  = 2.0;
server nosave float d64_poison_dist  = 1100.0;
server nosave float d64_poison_size  = 0.35;
server nosave float d64_poison_z     = 1.0;
server nosave float d64_poison_sat   = 1.0;
server nosave float d64_poison_light = 1.0;
server nosave float d64_poison_lsize = 16.0;
server nosave bool  d64_poison_debug = false;
server nosave bool  d64_poison_roofgate = true;
server        bool  d64_poison_bubbles = true;
"""


# NO GLDEFS LIGHT, AND WHY -- measured in the poison lab (MAP91), not reasoned.
#
# The first version gave every frame a GLDEFS pointlight, copying the lava
# sprays. In the lab that rendered a lake of WHITE PILLS: a point light sitting
# inside a 20-unit billboard is at zero distance from it, so the sprite lights
# itself into clipping and the art -- the shading, the highlight, the whole
# reason the bubble looks like a bubble -- is gone. The lava spark gets away
# with it because it is 6 px and already meant to read as a white-hot dot.
#
# Turning dynamic lights off proved the second half: the bubbles still threw
# green pools onto the nukage under them. That is RTGL1's SPRITE light, from
# lightIntensity in textures.json below, and it was doing the job on its own.
# So the GLDEFS half was not the light -- it was only the blowout.
#
# If a future change needs a light that is NOT co-located with the billboard
# (a flare above the pop, say), it has to be a separate actor at a real
# distance, not a light attached to this frame.


# An EventHandler in a ZSCRIPT lump is NOT registered on its own -- it has to be
# named in MAPINFO. Without this the class compiles, loads and never runs, which
# is exactly what happened to the lava sprays for a whole round. AddEventHandlers
# appends rather than replaces, so this coexists with d64r-lava-fx.pk3's line.
# OPTIONS > EFFECTS. The first MENUDEF in the project, so it is also the shape
# the next effect toggle should copy.
#
# AddOptionMenu rather than a replacement: OptionsMenu is declared `protected`
# in the engine's menudef.txt, which blocks REPLACING it but not extending it
# (menudef.cpp:703 guards the replace path; ParseAddOptionMenu does not check
# mProtected at all). AFTER matches on an item's ACTION, so "HUDOptions" is the
# HUD submenu, and the new page lands with the other option pages instead of
# below the console/config commands at the bottom.
#
# It lives in this pk3 rather than in the engine's menudef.txt because the cvar
# it drives is declared in this pk3's CVARINFO. An engine menu item bound to a
# cvar that does not exist when the pk3 is not loaded is a menu that cannot draw
# itself; this way the page appears exactly when the effect is present.
MENUDEF = """AddOptionMenu "OptionsMenu" AFTER "HUDOptions"
{
	Submenu "Effects", "D64EffectsOptions"
}

OptionMenu "D64EffectsOptions"
{
	Title "EFFECTS"
	StaticText "Doom 64 RT", 1
	StaticText " "
	Option "Poison bubbles", "d64_poison_bubbles", "OnOff"
	StaticText " "
	StaticText "Bubbles that swell out of a nukage"
	StaticText "lake and burst. Poison floors only."
}
"""


MAPINFO = """GameInfo
{
\tAddEventHandlers = "D64PoisonFx"
}
"""


# The sprite half of the lighting, and it has to be written by the tool: this
# lives in rt/data/textures.json under build/, which is gitignored and rewritten
# wholesale by the PBR tooling, so a hand edit is neither recorded nor durable.
# Deliberately an order of magnitude under the lava sparks (760 lm at the hot
# end): "a slight green light" is the brief, and a bubble is cold.
# The sprite half of the lighting, and it has to be written by the tool: this
# lives in rt/data/textures.json under build/, which is gitignored and rewritten
# wholesale by the PBR tooling, so a hand edit is neither recorded nor durable.
#
# Deliberately an order of magnitude under the lava sparks (760 lm at the hot
# end): "a slight green light" is the brief, and a bubble is cold.
#
# lightColor is retinted with the ART, per rung. A grey bubble throwing a
# saturated green light would be the one combination that cannot happen in the
# world, and the grey rung exists precisely to answer "where is the green coming
# from" -- it has to be honest about it.
# MEASURED IN THE DARK, not reasoned about in a lit room.
#
# The first numbers (55-150 lm, emissiveMult 0.30-0.55) were signed off in
# MAP91, which has a ceiling grid -- so what looked like the bubbles glowing was
# the room lighting their albedo, and they were carrying almost no light of
# their own. MAP93, the same corridor at lightlevel 0 with nothing else in it,
# showed the truth: dull olive dots on black nukage, casting nothing. That is
# the "no light on MAP07" report exactly.
#
# Two things made it worse than the first pass. The bubbles are now drawn at
# d64_poison_size 0.35 rather than ~1.0, so there is roughly a fifth of the
# sprite area to emit from; and the retint pulled chroma to 0.575 to match the
# pool. Both are wanted -- neither is free.
#
# THEN CORRECTED, 2026-08-26, once the entries were live for the first time.
#
# The 4.5x raise above was tuned against "the bubbles cast nothing in the dark"
# -- and it was never actually seen in play, because patch_texjson wrote only
# the gitignored build tree and every build wiped it (see TEXJSON_PATHS). The
# first run with both halves alive read as far too bright, and the numbers say
# why: at emissiveMult 0.60-1.05 and 250-650 lm the bubbles were calibrated like
# a LAVA SPARK (LSPK*: 0.30-0.70, 100-760 lm) -- a white-hot molten droplet --
# and sat in the top ~15% of all 956 emissive sprites in the game, whose median
# is 0.35-0.40. A cold nukage bubble is not a lava spark.
#
# TWO SEPARATE THINGS, and conflating them is what made the knob feel dead:
#
#   emissiveMult    how bright the BILLBOARD LOOKS. Screen glow; casts nothing.
#                   Material meta, so NOT tunable at runtime -- rebuild with
#                   --emis to move it (see below).
#   lightIntensity  light the sprite THROWS on the world. Also material meta,
#                   also untunable, AND co-located with the billboard with no
#                   LF_DONTLIGHTSELF -- the white-pill mechanism.
#
# lightIntensity is now 0 on every frame and the cast light is entirely
# AttachPoisonLight()'s, which is tunable (d64_poison_light) and cannot light
# its own sprite. That is not a new idea here: it is exactly what the game's 84
# flame sprites do -- lightIntensity 0 in the meta, lit by RT_UploadFlameLights
# in C++ instead, and for the same reason (meta cannot express a tunable light).
#
# So d64_poison_light now governs ALL the light a bubble throws, and its default
# goes back to 1.0 -- the value that was actually in play while the meta was
# missing. Every arm pins it, so the arms moved with it.
#
# emissiveMult lands at 0.22-0.42: below the set's median, an order of magnitude
# under a torch, and the brief -- "a thing you notice on the surface, not a
# lamp" -- unchanged. It is the ONE number for how bright a bubble looks.
BUBBLE_BASE_META = [
    (0, [110, 235, 60], 0.22),
    (0, [110, 235, 60], 0.25),
    (0, [112, 238, 62], 0.28),
    (0, [114, 240, 64], 0.31),
    (0, [116, 242, 66], 0.35),
    (0, [130, 250, 80], 0.42),
]

# Scales the emissiveMult ramp above; --emis on the command line sets it. It is
# a REBUILD knob and not a cvar, because material meta cannot be scaled at
# runtime: a tinted sprite is a different RTGL1 material with no textures.json
# entry, which is the same wall d64_poison_sat's baked rungs exist to get round.
# Having it on the command line means a level can be tried in one command
# instead of an edit:
#
#     tools/.venv-ai/Scripts/python.exe tools/gen_poison_fx.py --apply --emis 0.6
#
# lightColor is kept written even though lightIntensity is 0, so that raising
# the intensity again is one number and not a re-derivation.
EMIS_SCALE = 1.0


def rung_meta(prefix: str, sat_rung: float) -> dict:
    import colorsys

    out = {}
    for letter, (lm, col, em) in zip(FRAMES, BUBBLE_BASE_META):
        hh, ss, vv = colorsys.rgb_to_hsv(*[c / 255.0 for c in col])
        hh = (hh + HUE_SHIFT) % 1.0
        ss = min(1.0, ss * BASE_SAT * sat_rung)
        vv = min(1.0, vv * VAL_LIFT)
        rgb = [int(round(min(255.0, c * 255.0))) for c in colorsys.hsv_to_rgb(hh, ss, vv)]
        out[f"{prefix}{letter}0"] = (lm, rgb, round(em * EMIS_SCALE, 3))
    return out


# Built on demand rather than at import, so --emis can be applied before it is
# read. The module-level name stays for anything that imports this file.
def bubble_meta() -> dict:
    out = {}
    for pfx, rung in SAT_SETS:
        out.update(rung_meta(pfx, rung))
    return out


BUBBLE_META = bubble_meta()

# BOTH COPIES, and the second one is not optional.
#
# This wrote only the build tree until 2026-08-26, and that is why the PBU*
# entries were missing from every machine: build/ is GITIGNORED and every build
# re-stages the TRACKED copy over it, so a build-dir-only meta edit is reverted
# by the next build and a fresh clone never had it at all. Nothing errors -- the
# meta simply has fewer entries and the bubbles silently stop glowing, which is
# the "emissive only, looked fine in the lit lab" failure written up in
# docs/poison-bubbles.md read a second time.
#
# Same rule as the rest of the RT materials: after any generator run,
# `git status Doom64-Retribution/Retribution-RT-Materials/` must not be empty.
TEXJSON_PATHS = [
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json",
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/data/textures.json",
]


def patch_texjson() -> int:
    import json

    meta = bubble_meta()
    total = 0
    for path in TEXJSON_PATHS:
        if not path.exists():
            print(f"  (skipped {path}: not found -- build gzdoom first)")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        seen, n = set(), 0
        for e in data["array"]:
            nm = e.get("textureName")
            if nm in meta and nm not in seen:
                seen.add(nm)
                i, c, em = meta[nm]
                e["lightIntensity"], e["lightColor"], e["emissiveMult"] = i, c, em
                n += 1
        for nm, (i, c, em) in meta.items():
            if nm not in seen:
                data["array"].append(
                    {"textureName": nm, "lightIntensity": i, "lightColor": c,
                     "emissiveMult": em, "metallicDefault": 0}
                )
                n += 1
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  {path.relative_to(ROOT).as_posix()}  {n} PBU* entries")
        total += n
    return total


# The six-frame sequence, once, with the sprite name left open so it can be
# stamped per rung. The durations and the burst growth are the SAME on every
# rung -- saturation is the only thing the ladder changes, or an A/B between two
# rungs would be comparing two effects.
STATE_SEQ = """    {label}:
        {spr} A 8;
        {spr} B 6;
        {spr} C 6;
        {spr} D 6;
        {spr} E 10;
        // The ring flies apart rather than sitting still for seven tics. Frame
        // F is already a ring of loose droplets; growing it is what turns it
        // from a stamp into a pop.
        {spr} F 2 {{ scale *= 1.14; }}
        {spr} F 2 {{ scale *= 1.14; }}
        {spr} F 3 {{ scale *= 1.14; }}
        Stop;"""


def build_states() -> str:
    """One sequence per rung. Spawn is a second label on the default rung, so an
    actor spawned before PostBeginPlay runs -- or with the cvar missing
    entirely -- still has the shipping look rather than no sprite at all."""
    out = []
    for i, (prefix, _rung) in enumerate(SAT_SETS):
        label = f"Sat{i}"
        if i == SAT_DEFAULT_INDEX:
            out.append("    Spawn:")
        out.append(STATE_SEQ.format(label=label, spr=prefix))
    return "\n".join(out)


def build_satpick() -> str:
    """A ladder of midpoint thresholds, generated from SAT_SETS so the code and
    the table cannot drift apart."""
    lines, first = [], True
    for i in range(len(SAT_SETS) - 1):
        mid = (SAT_SETS[i][1] + SAT_SETS[i + 1][1]) / 2.0
        kw = "if" if first else "else if"
        lines.append(f"        {kw}( s < {mid:.3f} ) {{ st = ResolveState( \"Sat{i}\" ); }}")
        first = False
    lines.append(f'        else {{ st = ResolveState( "Sat{len(SAT_SETS) - 1}" ); }}')
    return "\n".join(lines)


def build(dry: bool) -> int:
    if not SHEET.exists():
        raise SystemExit(f"missing source art: {SHEET}")

    sliced = slice_sheet(SHEET)

    # One sprite set per rung. The geometry -- crop, scale, grAb -- is shared,
    # so the rungs cannot drift apart in anything except colour.
    sets = []
    for prefix, rung in SAT_SETS:
        frames = []
        for letter, (img, ox, oy) in zip(FRAMES, sliced):
            tinted = retint(img, rung)
            frames.append((f"{prefix}{letter}0", tinted, ox, oy,
                           png_with_grab(tinted, ox, oy)))
        sets.append((prefix, rung, frames))

    zscript = ZSCRIPT.replace("__STATES__", build_states())
    zscript = zscript.replace("__SATPICK__", build_satpick())

    total = sum(len(f) for _, _, f in sets)
    print(f"{OUT.name}: {total} sprite(s) -- {len(FRAMES)} frames x {len(SAT_SETS)} "
          f"saturation rung(s) -- sliced from {SHEET.name}")
    print(f"   hue {BUBBLE_HUE_DEG:.1f} -> {POOL_HUE_DEG:.1f} deg, chroma x{BASE_SAT:.3f} "
          f"at rung 1.0, value x{VAL_LIFT:.2f}  (matched to the rendered pool)")
    for prefix, rung, frames in sets:
        star = "  <- default (d64_poison_sat 1)" if rung == SAT_SETS[SAT_DEFAULT_INDEX][1] else ""
        print(f"   {prefix}  sat x{rung:.2f}  {len(frames)} frame(s){star}")
    # Counted, not written down. The hardcoded "7 nosave knobs" this replaced had
    # been wrong for three cvars.
    cv = [l for l in CVARINFO.splitlines() if l.strip()]
    n_nosave = sum(1 for l in cv if "nosave" in l)
    print(f"   ZSCRIPT {len(zscript)} bytes, MAPINFO registers D64PoisonFx, "
          f"CVARINFO adds {n_nosave} nosave knob(s) + {len(cv) - n_nosave} archived "
          f"setting(s), MENUDEF adds Options > Effects; "
          f"NO GLDEFS -- see the note above BUBBLE_BASE_META")
    for name, img, ox, oy, blob in sets[SAT_DEFAULT_INDEX][2]:
        print(f"   sprites/{name}.png  {img.width}x{img.height}  offset ({ox},{oy})  {len(blob)} bytes")
    if dry:
        print("\nPass --apply to write the pk3.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MAPINFO", MAPINFO)
        z.writestr("CVARINFO", CVARINFO)
        z.writestr("MENUDEF", MENUDEF)
        z.writestr("ZSCRIPT", zscript)
        for _prefix, _rung, frames in sets:
            for name, img, ox, oy, blob in frames:
                z.writestr(f"sprites/{name}.png", blob)
    print(f"\nwrote {OUT}")
    print(f"{patch_texjson()} bubble entr(ies) written to textures.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--emis", type=float, default=1.0,
                    help="scale the sprite glow ramp (emissiveMult); 1.0 ships")
    args = ap.parse_args()
    global EMIS_SCALE
    EMIS_SCALE = args.emis
    return build(dry=not args.apply)


if __name__ == "__main__":
    sys.exit(main())
