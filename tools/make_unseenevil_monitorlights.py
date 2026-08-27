"""Give Doom 64: Unseen Evil the SMON monitor panels exactly as Retribution has them.

Retribution's wall monitors are three things at once, and every one of the three
is copied here rather than approximated:

  1. THE ART. Retribution's SMON* lumps are PNGs. Unseen Evil ships its OWN
     renditions under the same names (different bytes, twice the size), and every
     RT material for these panels -- rt/mat/SMON*_e/_n/_h/_orm, the emissiveMult
     2.8 rows in textures.json -- was authored against Retribution's pixels. A
     mask lined up on the wrong art glows in the wrong places, dimly. So the
     overlay ships Retribution's PNGs at textures/d64/<NAME>.png, which is where
     UE keeps its own; loading after the mod, they win by path.

  2. THE ANIMATION. Retribution animates SMONA/B/C/D/E/F and the SMONL composites
     at its own tic counts (5, and 2 for the fast SMONB readout). Unseen Evil's
     ANIMDEFS animates only A, D and E, at 7 tics, and leaves B, C and F static.
     Retribution's SMON blocks are copied verbatim into an ANIMDEFS lump here.

  3. THE LIGHT. Retribution places a 9802 PointLightFlicker in front of EVERY
     PANEL, never texture metadata -- an _e mask glows but casts nothing. Measured
     over all 34 maps, by the light thing nearest each SMON sidedef (within 48u):

        SMONA  (0,255,  0)  24/20  h32   x573      green terminals
        SMONB  (255, 0,  0)  24/20  h40   x3        red readout
        SMONC  (0,255,180)  24/20  h32   x34       cyan
        SMOND  (0,120,255)  24/20  h32   x101      BLUE -- not cyan
        SMONE  (0,255,180)  24/20  h32   x29
        SMONL* (0,255,180)  28/24  h32   x231      the 128-wide LB/LC composites

     One per 64-unit tile (MAP01's SMONDA lights are 64 apart), at 32 above the
     floor, angle 90 -- Retribution's numbers, all of them. DOOM II's IWAD carries
     zero 9800/9801/9802 things in any map, so these have to be spawned: this
     late EventHandler waits one tic for the Terraformer, then walks every face
     whose texture starts with SMON. The actor path is what makes it identical --
     RT_UploadGzDoomDynamicLights forwards these with the blink and trim
     (rt_dynlight_blink_floor, rt_dynlight_flicker_scale) the SMON wall was tuned
     with, so there is nothing to re-tune.

     SMONF has no map light in Retribution (it is lit at runtime by
     tools/add_smonf_lights.py, a 9801 pulse); it gets SMONE's 9802 here so no
     screen is left dark, and that is the one value in this file that is a choice.

Same shape as make_unseenevil_keylights.py, for the reason that file gives.

    py -3 tools/make_unseenevil_monitorlights.py            # census, writes nothing
    py -3 tools/make_unseenevil_monitorlights.py --write    # build the overlay pk3
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-monitor-lights.pk3"
WAD = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"

OFF_WALL = 8.0

# family prefix -> (r, g, b, hi, lo, height above floor). Measured, see docstring.
FAMILIES = {
    "SMONA": (0, 255, 0, 24, 20, 32),
    "SMONB": (255, 0, 0, 24, 20, 40),
    "SMONC": (0, 255, 180, 24, 20, 32),
    "SMOND": (0, 120, 255, 24, 20, 32),
    "SMONE": (0, 255, 180, 24, 20, 32),
    "SMONF": (0, 255, 180, 24, 20, 32),  # the one chosen value; see docstring
    "SMONL": (0, 255, 180, 28, 24, 32),
}

ZSCRIPT_HEAD = r'''version "4.12"

// Retribution lights every SMON panel with a 9802 PointLightFlicker a few units
// off the face -- never texture metadata. DOOM II carries no light things at all,
// so Unseen Evil gets them spawned, with Retribution's own per-family arguments.
class D64UE_RT_MonitorLights : EventHandler
{
    Array<Actor> spawned;
    int deferredTics;
    bool active;

    bool WantLights() const
    {
        CVar cv = CVar.FindCVar("d64ue_rt_monitorlights");
        return cv == null || cv.GetBool();
    }

    void RemoveLights()
    {
        for (int i = 0; i < spawned.Size(); i++)
        {
            if (spawned[i]) spawned[i].Destroy();
        }
        spawned.Clear();
        active = false;
    }

    override void WorldLoaded(WorldEvent e)
    {
        spawned.Clear();
        active = false;
        // The Terraformer also runs in WorldLoaded; one tic later its renames
        // (SPACEW3 -> SMONDA) are final.
        deferredTics = 1;
    }

    override void WorldTick()
    {
        if (deferredTics > 0)
        {
            deferredTics--;
            if (deferredTics == 0 && WantLights()) SpawnLights();
            return;
        }
        bool want = WantLights();
        if (want && !active) SpawnLights();
        else if (!want && active) RemoveLights();
    }

    // Family index for a texture name, -1 if it is not a monitor.
    int Family(String name) const
    {
        String u = name.MakeUpper();
        if (u.Left(4) != "SMON" || u.Length() < 5) return -1;
        String f = u.Mid(4, 1);
'''

ZSCRIPT_TAIL = r'''        return -1;
    }

    // ONE LIGHT PER PANEL, NOT PER SIDEDEF. Retribution's monitor walls are one
    // panel per sidedef, so per-face IS per-panel there and its lights sit 64
    // apart. A DOOM II wall is one long sidedef with the texture TILED across
    // it, so per-face spawning lit a twelve-panel bank with one light. Walk the
    // face in texture-width steps from the sidedef's own X offset instead.
    void SpawnFace(Side side, int part, int fam)
    {
        Vector2 p1 = side.V1().p;
        Vector2 p2 = side.V2().p;
        Vector2 delta = p2 - p1;
        double len = delta.Length();
        if (len < 0.001 || !side.sector) return;

        Vector2 tsize = TexMan.GetScaledSize(side.GetTexture(part));
        double tw = tsize.x > 1 ? tsize.x : 64;
        double xoff = side.GetTextureXOffset(part);
        double start = -(xoff % tw);
        if (start > 0) start -= tw;

        for (double t = start + tw * 0.5; t < len; t += tw)
        {
            if (t < 0) continue;
            SpawnAt(side, p1 + delta * (t / len), delta, len, fam);
        }
    }

    void SpawnAt(Side side, Vector2 mid, Vector2 delta, double len, int fam)
    {
        // The face normal that lands INSIDE the sector this side faces. Backwards
        // buries the light in solid geometry, where it looks exactly unspawned.
        Vector2 normal = (delta.y / len, -delta.x / len);
        Vector2 pos = mid + normal * OFF_WALL_D;
        if (Level.PointInSector(pos) != side.sector) pos = mid - normal * OFF_WALL_D;
        if (Level.PointInSector(pos) != side.sector)
        {
            Vector2 toward = side.sector.centerspot - mid;
            if (toward.Length() > 0.001) pos = mid + toward.Unit() * OFF_WALL_D;
        }

        double floorZ = side.sector.floorplane.ZAtPoint(pos);
        double ceilZ = side.sector.ceilingplane.ZAtPoint(pos);
        if (ceilZ - floorZ < 16.0) return;

        // Retribution's height is above the FLOOR (32 for nearly every panel).
        double z = min(floorZ + FAM_H[fam], ceilZ - 8.0);

        // Actor.Spawn: an EventHandler is not an Actor and has no Spawn of its own.
        Actor light = Actor.Spawn("PointLightFlicker", (pos.x, pos.y, z));
        if (!light) return;
        light.args[0] = FAM_R[fam];
        light.args[1] = FAM_G[fam];
        light.args[2] = FAM_B[fam];
        // RADII, not brightnesses; past rt_dynlight_rsoft a bigger one is DIMMER.
        light.args[3] = FAM_HI[fam];
        light.args[4] = FAM_LO[fam];
        // For 9801/9802/9804 the thing's angle is a PERIOD, not a bearing.
        light.Angle = 90;
        spawned.Push(light);
    }

    void SpawnLights()
    {
        RemoveLights();
        int faces = 0;
        for (int i = 0; i < level.Sides.Size(); i++)
        {
            Side side = level.Sides[i];
            int hitPart = -1, fam = -1;
            for (int part = 0; part < 3 && hitPart < 0; part++)
            {
                fam = Family(TexMan.GetName(side.GetTexture(part)));
                if (fam >= 0) hitPart = part;
            }
            if (hitPart < 0) continue;
            SpawnFace(side, hitPart, fam);
            faces++;
        }
        active = true;
        CVar debugC = CVar.FindCVar("d64ue_rt_monitordebug");
        if (debugC != null && debugC.GetBool())
        {
            Console.Printf("D64UE_RT_MonitorLights: %s -- %d SMON face(s), %d panel light(s) (one 9802 per tile)",
                           level.MapName, faces, spawned.Size());
        }
    }
}
'''

MAPINFO = 'gameinfo\n{\n    AddEventHandlers = "D64UE_RT_MonitorLights"\n}\n'
CVARINFO = (
    "// A/B switch for the map-actor monitor lights; deliberately not archived.\n"
    "server noarchive bool d64ue_rt_monitorlights = true;\n"
    "user noarchive bool d64ue_rt_monitordebug = false;\n"
)


def build_zscript() -> str:
    keys = list(FAMILIES)
    fam_if = "".join(
        f'        if (f == "{k[4]}") return {i};\n' for i, k in enumerate(keys)
    )
    def arr(name, idx):
        vals = ", ".join(str(FAMILIES[k][idx]) for k in keys)
        return f"    static const int {name}[] = {{ {vals} }};\n"
    tables = (
        arr("FAM_R", 0) + arr("FAM_G", 1) + arr("FAM_B", 2)
        + arr("FAM_HI", 3) + arr("FAM_LO", 4) + arr("FAM_H", 5)
    )
    src = ZSCRIPT_HEAD + fam_if + ZSCRIPT_TAIL
    src = src.replace("    Array<Actor> spawned;\n", tables + "    Array<Actor> spawned;\n", 1)
    return src.replace("OFF_WALL_D", f"{OFF_WALL}")


def read_wad():
    b = WAD.read_bytes()
    _, n, off = struct.unpack("<4sii", b[:12])
    lumps = {}
    for i in range(n):
        fo, sz, nm = struct.unpack("<ii8s", b[off + i * 16 : off + i * 16 + 16])
        lumps.setdefault(nm.rstrip(b"\0").decode("latin1"), b[fo : fo + sz])
    return lumps


def smon_art(lumps):
    """Every SMON* PNG lump in Retribution's WAD."""
    return {
        n: d for n, d in lumps.items()
        if n.startswith("SMON") and d[:8] == b"\x89PNG\r\n\x1a\n"
    }


def smon_animdefs(lumps) -> str:
    """Retribution's own SMON animation blocks, verbatim."""
    lines = lumps["ANIMDEFS"].decode("latin1").splitlines()
    blocks, cur = [], False
    for ln in lines:
        w = ln.split()
        if not w:
            continue
        if w[0].lower() == "texture" and len(w) >= 2:
            # SMONL* are 128x64 composites defined in Retribution's TEXTURES lump;
            # UE has no such textures and ANIMDEFS naming one is FATAL at startup
            # ("Can't find SMONLB1"). UE's mapping never produces an SMONL name.
            cur = w[1].upper().startswith("SMON") and not w[1].upper().startswith("SMONL")
            if cur:
                blocks.append(f"\ntexture {w[1]}\n")
        elif w[0].lower() == "flat":
            cur = False
        elif cur:
            # pic / allowdecals / oscillate ... keep the block verbatim
            blocks.append("    " + " ".join(w) + "\n")
    return (
        "// Doom64-RT: Retribution's SMON animation blocks, copied verbatim so the\n"
        "// panels animate at the same rate and every family animates (UE's own\n"
        "// ANIMDEFS covers only A, D and E, at 7 tics).\n\n"
        + "".join(blocks)
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    lumps = read_wad()
    art = smon_art(lumps)
    anim = smon_animdefs(lumps)
    zs = build_zscript()
    assert "OFF_WALL_D" not in zs

    print("SMON monitors for Unseen Evil, Retribution's way")
    for k, (r, g, b_, hi, lo, h) in FAMILIES.items():
        print(f"  {k}*  rgb({r},{g},{b_})  radii {hi}/{lo}  h{h}")
    print(f"  art: {len(art)} Retribution PNG lumps -> textures/d64/")
    print(f"  animdefs: {anim.count('texture ')} animated SMON textures")
    if not args.write:
        print(f"\n(census only -- pass --write to build {OUT.name})")
        return

    with ZipFile(OUT, "w", ZIP_DEFLATED) as z:
        z.writestr("ZSCRIPT", zs)
        z.writestr("MAPINFO", MAPINFO)
        z.writestr("CVARINFO", CVARINFO)
        z.writestr("ANIMDEFS.d64rtsmon", anim)
        for n, d in sorted(art.items()):
            z.writestr(f"textures/d64/{n}.png", d)
    with ZipFile(OUT) as z:
        names = z.namelist()
        assert z.read("ZSCRIPT").decode() == zs
        assert sum(1 for x in names if x.startswith("textures/d64/")) == len(art)
    print(f"\nwrote {OUT} ({OUT.stat().st_size} bytes, {len(names)} entries)")


if __name__ == "__main__":
    main()
