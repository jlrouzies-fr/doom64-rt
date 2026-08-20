"""Build Retribution-style key-trim lights for Doom 64: Unseen Evil.

Retribution does not make its locked-door trims illuminate the room through a
texture heuristic.  Its maps place three co-located 9800 PointLight things at
different heights on each lit jamb.  The RT engine already has explicit stack
attenuation for exactly that arrangement.

Unseen Evil converts IWAD maps at runtime, so a conventional MAP02 replacement
would either be Doom-II-version-specific or fight the Terraformer.  This small
late-loaded EventHandler waits until the Terraformer has replaced the wall
textures, finds the resulting STRAKR/B/Y and keytrim_* faces, and spawns the
same three-PointLight stack just in front of each face.

Usage:
    py -3 tools/make_unseenevil_keylights.py --write
"""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-keytrim-lights.pk3"


ZSCRIPT = r'''version "4.12"

// Retribution's locked-door jambs use three 9800 PointLight things at one XY,
// spread vertically.  Keep that exact actor path here: RT_UploadGzDoomDynamicLights
// already recognises and attenuates these stacks, while a texture-only glow cannot
// illuminate the surrounding floor and walls.
class D64UE_RT_KeyTrimLights : EventHandler
{
    Array<Actor> spawned;
    int deferredTics;
    bool active;
    bool posed;

    bool WantLights() const
    {
        CVar cv = CVar.FindCVar("d64ue_rt_keylights");
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
        posed = false;
    }

    override void WorldLoaded(WorldEvent e)
    {
        spawned.Clear();
        active = false;
        // UE's Terraformer also works in WorldLoaded.  Waiting one tic makes
        // this independent of handler registration order and guarantees that
        // DOORRED/BLU/YEL have their final Doom-64 texture names before scanning.
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

    int KeyHue(String name)
    {
        String upper = name.MakeUpper();
        if (upper.Left(6) == "STRAKR" || upper.IndexOf("D64_KEYTRIM_RED") >= 0) return 1;
        if (upper.Left(6) == "STRAKB" || upper.IndexOf("D64_KEYTRIM_BLUE") >= 0) return 2;
        if (upper.Left(6) == "STRAKY" || upper.IndexOf("D64_KEYTRIM_YELLOW") >= 0) return 3;
        return 0;
    }

    void SetHue(Actor light, int hue, bool sharesPillarFlux)
    {
        // A narrow UE pillar exposes the same 16-unit fixture on four faces.
        // Keep one Retribution fixture's aggregate flux while distributing it
        // around the solid: each face carries one quarter of the RGB energy.
        // Wider door jambs are independent fixtures and retain the authored hue.
        int divisor = sharesPillarFlux ? 4 : 1;
        if (hue == 1)      { light.args[0] = 255 / divisor; light.args[1] = 46 / divisor;  light.args[2] = 46 / divisor;  }
        else if (hue == 2) { light.args[0] = 61 / divisor;  light.args[1] = 107 / divisor; light.args[2] = 255 / divisor; }
        else               { light.args[0] = 255 / divisor; light.args[1] = 209 / divisor; light.args[2] = 51 / divisor;  }
        // Match the radius used by Retribution's authored key-door 9800s.
        light.args[3] = 32;
    }

    void SpawnStack(Side side, int hue)
    {
        Vector2 p1 = side.V1().p;
        Vector2 p2 = side.V2().p;
        Vector2 mid = (p1 + p2) * 0.5;
        Vector2 delta = p2 - p1;
        double len = delta.Length();
        if (len < 0.001 || !side.sector) return;

        // Try both face normals and select the one inside the sector this side
        // faces.  This is the runtime equivalent of Retribution's map-authored
        // lights sitting in front of (not buried behind) the jamb texture.
        Vector2 normal = (delta.y / len, -delta.x / len);
        Vector2 pos = mid + normal * 8.0;
        if (Level.PointInSector(pos) != side.sector)
        {
            pos = mid - normal * 8.0;
        }
        if (Level.PointInSector(pos) != side.sector)
        {
            Vector2 toward = side.sector.centerspot - mid;
            if (toward.Length() > 0.001) pos = mid + toward.Unit() * 8.0;
        }

        double floorZ = side.sector.floorplane.ZAtPoint(pos);
        double ceilZ = side.sector.ceilingplane.ZAtPoint(pos);
        double height = ceilZ - floorZ;
        if (height < 16.0) return;

        // Diagnostic capture pose. This is off by default and exists so the
        // key caster can be inspected without a manual walk from MAP02's spawn.
        // Stand farther along the already-validated room-facing normal and look
        // back at the trim. It changes no map or light state.
        CVar poseC = CVar.FindCVar("d64ue_rt_keypose");
        if (!posed && poseC != null && poseC.GetBool() &&
            playeringame[consoleplayer] && players[consoleplayer].mo)
        {
            Vector2 roomward = pos - mid;
            if (roomward.Length() > 0.001)
            {
                Vector2 eye = mid + roomward.Unit() * 112.0;
                Sector eyeSector = Level.PointInSector(eye);
                if (eyeSector)
                {
                    Actor viewer = players[consoleplayer].mo;
                    double eyeFloor = eyeSector.floorplane.ZAtPoint(eye);
                    viewer.SetOrigin((eye.x, eye.y, eyeFloor), true);
                    viewer.Angle = VectorAngle(mid.x - eye.x, mid.y - eye.y);
                    viewer.Pitch = 0;
                    posed = true;
                }
            }
        }

        // One co-located triple per emitting face, exactly the arrangement for
        // which rt_dynlight_stack_atten exists. Every face of a four-sided UE
        // pillar gets a quarter-flux stack, so the pillar totals one fixture;
        // wider jambs get full-flux stacks, like Retribution.
        bool sharesPillarFlux = len <= 20.0;
        for (int zslot = 0; zslot < 3; zslot++)
        {
            double frac = 0.25 + 0.25 * zslot;
            Actor light = Actor.Spawn("PointLight", (pos.x, pos.y, floorZ + height * frac));
            if (!light) continue;
            SetHue(light, hue, sharesPillarFlux);
            spawned.Push(light);
        }
    }

    void SpawnLights()
    {
        RemoveLights();
        int faces = 0;

        for (int i = 0; i < level.Sides.Size(); i++)
        {
            Side side = level.Sides[i];
            int hue = 0;
            for (int part = 0; part < 3 && hue == 0; part++)
            {
                hue = KeyHue(TexMan.GetName(side.GetTexture(part)));
            }
            if (hue == 0) continue;

            SpawnStack(side, hue);
            faces++;
        }

        active = true;
        CVar debugC = CVar.FindCVar("d64ue_rt_keydebug");
        if (debugC != null && debugC.GetBool())
        {
            Console.Printf("D64UE_RT_KeyTrimLights: %s -- %d key face(s), %d Retribution-style 9800 light(s)",
                           level.MapName, faces, spawned.Size());
        }
    }
}
'''

MAPINFO = '''gameinfo
{
    AddEventHandlers = "D64UE_RT_KeyTrimLights"
}
'''

CVARINFO = '''// A/B switch for the map-actor key lights; deliberately not archived.
server noarchive bool d64ue_rt_keylights = true;
user noarchive bool d64ue_rt_keypose = false;
user noarchive bool d64ue_rt_keydebug = false;
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    print("Retribution-style key lights: 3 x PointLight per transformed key-trim face")
    print("  texture families: STRAKR/B/Y and d64_keytrim_red/blue/yellow")
    print("  radius: 32 map units; face offset: 8 map units")
    print("  narrow <=20-unit pillar faces: quarter RGB flux per face")
    if not args.write:
        print(f"census only; pass --write to build {OUT.name}")
        return

    with ZipFile(OUT, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("ZSCRIPT", ZSCRIPT)
        archive.writestr("MAPINFO", MAPINFO)
        archive.writestr("CVARINFO", CVARINFO)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
