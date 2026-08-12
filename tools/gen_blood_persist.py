"""Build d64r-blood-persist.pk3 -- blood that stays on the floor.

WHERE THE ONE-SECOND LIFETIME ACTUALLY LIVES. Not in the renderer, not in a
cvar: it is authored in the Retribution WAD's DECORATE lump.

    ACTOR 64Blood : Blood REPLACES Blood     (D64RTR_v15.WAD, DECORATE:1951)
        Spawn:
            BLUD D 0
            BLUD D 0 A_SpawnItemEx("64Blood2",  5,  5, ...)
            BLUD D 0 A_SpawnItemEx("64Blood2", -5, -5, ...)
            BLUD D 8
            BLUD CBA 8
            Stop                              <- 32 tics, ~0.9 s, then gone

The four frames GROW rather than shrink -- BLUDD0 is 16x4, BLUDA0 is 16x12 --
so the sequence already ends on the biggest splat. Persisting it is a matter of
holding that frame (BLUD A -1) instead of reaching Stop.

TWO HALVES, and they are in two different languages on purpose:

  1. the LIFETIME -- DECORATE. It has to be: 64Blood is a DECORATE class, and
     ZScript is parsed BEFORE DECORATE, so no ZScript class can inherit from it.
     A DECORATE actor that `replaces 64Blood` is the only way to touch its
     states. (The replacement chain Blood -> 64Blood -> RTBloodPersist resolves
     fine; GetReplacement recurses.)
  2. the RANDOMIZATION and the CAP -- ZScript. DECORATE cannot read a cvar, and
     it cannot hold a list of every splat in the level. An EventHandler can do
     both, and its WorldThingSpawned sees any Blood subclass regardless of which
     language declared it.

WHY A CAP AT ALL. Every hit leaves 1-3 permanent sprite actors. Offscreen ones
cost only a thinker tick -- hw_sprites never processes a sprite in an unseen
subsector, so RTGL1 never sees them -- but an unbounded queue over a long map
is still a queue nobody bounded. rt_gore_max 1500 recycles the oldest; set it
to 0 for genuinely unlimited.

THE EXPLOSION HALF (rt_gore_burst*). Rockets and barrels left no blood at all,
and that is stock GZDoom, not Retribution: blood actors are spawned only by
ATTACK code, never by damage code. P_RadiusAttack calls P_DamageMobj plus
P_TraceBleed, and P_TraceBleed makes a wall decal -- it spawns no actor. So an
explosive kill went through no code path that could produce a splat.

WorldThingDamaged is the hook, because it carries DamageFlags: DMG_EXPLOSION
(2048) covers rockets AND barrels, since a rocket detonates on contact and the
victim takes the radius hit at distance 0.

The burst does two different things on purpose:

  1. ONE t.SpawnBlood() -- the engine path, and the only thing that emits the
     RT fluid particles (RT_SpawnBlood_Thing, called at p_mobj.cpp:6140). It has no
     ZScript export and cannot be reproduced by hand.
  2. N splats spawned DIRECTLY, so each can be given a Vel. SpawnBlood()
     returns nothing, and setting the velocity from WorldThingSpawned instead
     does not work: that event fires from AActor::CallPostBeginPlay, which the
     thinker list runs on a LATER pass, not synchronously inside Spawn(). Any
     "burst is active" latch would already be stale when the event arrived.

Both kinds land in the existing WorldThingSpawned, so the jitter, the FIFO and
rt_gore_max apply with no change to that method.

Usage:
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_blood_persist.py           # report
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_blood_persist.py --apply
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Doom64-Retribution/d64r-blood-persist.pk3"


MAPINFO = """GameInfo
{
\tAddEventHandlers = "RTBloodPersistHandler"
}
"""


# noarchive on every one of them. An A/B arm that writes a value into the ini is
# the bug that ate a session elsewhere in this project: the next launch inherits
# it silently and both arms end up testing the same thing.
CVARINFO = """// Doom64-RT: persistent blood. All noarchive -- an arm's value must never
// survive into the next launch through the ini.

// How long a splat lives, in tics. 0 = forever (the point of this mod).
// 32 reproduces the stock Retribution behaviour, which is what ab-blood.cmd's
// "off" arm uses -- DECORATE cannot read a cvar, so the OFF switch has to be
// the handler expiring them rather than the states ending early.
server noarchive int rt_gore_life = 0;

// Hard cap on live splats. Oldest is destroyed first. 0 = unlimited.
server noarchive int rt_gore_max = 1500;

// Per-splat size jitter, +/- this fraction. 0 = every splat identical.
server noarchive float rt_gore_scale_var = 0.35;

// Random billboard roll. OFF by default: ROLLSPRITE is applied in
// HWSprite::Process, upstream of the RT upload, so RTGL1 should receive
// already-rotated geometry -- but that has not been eyeballed in game yet.
server noarchive bool rt_gore_roll = false;

// --- the explosion half -------------------------------------------------
// Rockets and barrels leave no blood in stock GZDoom: P_RadiusAttack never
// calls P_SpawnBlood. These throw a splash of the SAME splats outward from the
// victim, which arc down and settle exactly like the hitscan ones.

// Master switch for the explosion splash.
server noarchive bool rt_gore_burst = true;

// Splats at the reference damage (40). Scales 0.5x-2x with actual damage.
server noarchive int rt_gore_burst_count = 5;

// Outward horizontal speed, map units per tic.
server noarchive float rt_gore_burst_speed = 4.0;

// Upward kick. Each splat gets FRandom(lift*0.4, lift).
server noarchive float rt_gore_burst_lift = 3.0;

// One Console.Printf per burst. THE instrument for "is this actually live" --
// nothing printed means the feature is not running, whatever the screen shows.
server noarchive bool rt_gore_burst_debug = false;
"""


# The satellites were at a FIXED (+5,+5) and (-5,-5). Permanent blood made that
# visible: every corpse left the same three-blob stamp at the same angle. Now
# 1-3 satellites at random offsets -- mean 1.9375, so the sprite count per hit
# is essentially what it was.
#
# flags 131 is copied verbatim from the original call: SXF_TRANSFERTRANSLATION |
# SXF_ABSOLUTEPOSITION | SXF_CLIENTSIDE. ABSOLUTEPOSITION here means the x/y are
# world-axis offsets from the caller rather than rotated by its angle -- still
# offsets, not absolute coordinates.
DECORATE = """// Doom64-RT: blood that stays.
//
// Each Spawn ends on `BLUD A -1` -- infinite tics. The actor keeps physics-
// ticking (gravity is in Actor::Tick, not in the state machine), so it still
// falls and settles on the floor; only the animation stops.

ACTOR RTBloodPersist : 64Blood replaces 64Blood
{
\tStates
\t{
\tSpawn:
\t\tBLUD D 0
\t\tBLUD D 0 A_SpawnItemEx("64Blood2", random(-14,14), random(-14,14), 0, 0, 0, 0, 0, 131, 0)
\t\tBLUD D 0 A_Jump(96, "Settle")
\t\tBLUD D 0 A_SpawnItemEx("64Blood2", random(-14,14), random(-14,14), 0, 0, 0, 0, 0, 131, 0)
\t\tBLUD D 0 A_Jump(128, "Settle")
\t\tBLUD D 0 A_SpawnItemEx("64Blood2", random(-16,16), random(-16,16), 0, 0, 0, 0, 0, 131, 0)
\tSettle:
\t\tBLUD D 8
\t\tBLUD C 8
\t\tBLUD B 8
\t\tBLUD A -1
\t\tStop
\t}
}

// The satellite. Its own Spawn is overridden (as it was in the original) so a
// satellite never spawns satellites of its own.
ACTOR RTBloodPersist2 : 64Blood2 replaces 64Blood2
{
\tStates
\t{
\tSpawn:
\t\tBLUD D 8
\t\tBLUD C 8
\t\tBLUD B 8
\t\tBLUD A -1
\t\tStop
\t}
}

// The MAP00 target-range dummy's blood (Add, alpha 0.80). Inherited so the
// render style comes along.
ACTOR RTBloodPersistInvis : 64InvisiBlood replaces 64InvisiBlood
{
\tStates
\t{
\tSpawn:
\t\tBLUD D 8
\t\tBLUD C 8
\t\tBLUD B 8
\t\tBLUD A -1
\t\tStop
\t}
}
"""


ZSCRIPT = r'''version "4.12"

// Doom64-RT: persistent blood -- randomization and the cap.
//
// The lifetime itself is in DECORATE (BLUD A -1); this handler does the two
// things DECORATE cannot: read a cvar, and hold a list of every splat alive in
// the level.
//
// WHY A LIST AND NOT A PER-ACTOR TIMER. "Destroy the oldest when there are too
// many" is a global question -- no actor can answer it about itself. The list
// is a plain FIFO: index 0 is the oldest. ZScript's read barrier returns null
// for a destroyed actor, so entries go null on their own (a corpse-gib splat
// removed by a level reset, say) and the periodic prune compacts them out.

class RTBloodPersistHandler : EventHandler
{
	Array<Actor> splats;
	Array<int>   born;      // level.time when each was spawned, same indexing

	CVar cLife, cMax, cScaleVar, cRoll;
	CVar cBurst, cBurstCount, cBurstSpeed, cBurstLift, cBurstDebug;

	// Same-actor, same-tic dedupe for the explosion burst. A rocket delivers
	// its direct impact damage and its radius damage in ONE tic, and a monster
	// standing between two barrels gets both chain blasts; without this every
	// such victim bursts twice.
	Actor lastBurstThing;
	int   lastBurstTime;

	private void ResolveCVars()
	{
		if (cLife == null)     { cLife     = CVar.FindCVar("rt_gore_life"); }
		if (cMax == null)      { cMax      = CVar.FindCVar("rt_gore_max"); }
		if (cScaleVar == null) { cScaleVar = CVar.FindCVar("rt_gore_scale_var"); }
		if (cRoll == null)     { cRoll     = CVar.FindCVar("rt_gore_roll"); }

		if (cBurst == null)      { cBurst      = CVar.FindCVar("rt_gore_burst"); }
		if (cBurstCount == null) { cBurstCount = CVar.FindCVar("rt_gore_burst_count"); }
		if (cBurstSpeed == null) { cBurstSpeed = CVar.FindCVar("rt_gore_burst_speed"); }
		if (cBurstLift == null)  { cBurstLift  = CVar.FindCVar("rt_gore_burst_lift"); }
		if (cBurstDebug == null) { cBurstDebug = CVar.FindCVar("rt_gore_burst_debug"); }
	}

	private int LifeTics()  { ResolveCVars(); return (cLife != null) ? cLife.GetInt() : 0; }
	private int MaxSplats() { ResolveCVars(); return (cMax  != null) ? cMax.GetInt()  : 0; }

	override void WorldLoaded(WorldEvent e)
	{
		// The actors are gone with the old level; the arrays are not.
		splats.Clear();
		born.Clear();

		lastBurstThing = null;
		lastBurstTime  = -1;
	}

	// EXPLOSIVE KILLS. Blood actors are spawned only by ATTACK code in GZDoom,
	// never by damage code: P_RadiusAttack calls P_DamageMobj and then only
	// P_TraceBleed, which makes a wall decal and spawns no actor. So rockets
	// and barrels produced nothing at all. DMG_EXPLOSION covers both, since a
	// rocket detonates on contact and the victim takes the radius hit at
	// distance 0.
	override void WorldThingDamaged(WorldEvent e)
	{
		Actor t = e.Thing;
		if (t == null) { return; }

		ResolveCVars();
		if (cBurst == null || !cBurst.GetBool()) { return; }
		if ((e.DamageFlags & DMG_EXPLOSION) == 0) { return; }

		// The first three mirror SpawnLineAttackBlood's own test, so an actor
		// that bleeds nothing to a bullet bleeds nothing to a rocket either.
		// In the whole Retribution DECORATE, +NOBLOOD appears exactly once --
		// on 64LostSoul -- and that is what keeps souls bloodless here too.
		if (t.bNoBlood || t.bDormant || t.bInvulnerable) { return; }

		// This is what silently excludes barrels, decorations and everything
		// else that does not bleed. No class list to maintain.
		Class<Actor> bloodcls = t.GetBloodType(0);
		if (bloodcls == null) { return; }

		// Deterministic and netsafe, and it keeps a splash out of the
		// first-person camera.
		if (t.player != null) { return; }

		if (t == lastBurstThing && level.time == lastBurstTime) { return; }
		lastBurstThing = t;
		lastBurstTime  = level.time;

		int baseCount = (cBurstCount != null) ? cBurstCount.GetInt() : 5;
		int n = int(round(baseCount * clamp(double(e.Damage) / 40.0, 0.5, 2.0)));
		if (n < 0) { n = 0; }

		if (cBurstDebug != null && cBurstDebug.GetBool())
		{
			Console.Printf("RTBloodBurst: %s dmg %d -> %d splats", t.GetClassName(), e.Damage, n);
		}

		// The engine path, once. It is the only thing that emits the RT fluid
		// particles (RT_SpawnBlood_Thing), which has no ZScript export.
		t.SpawnBlood(t.pos + (0, 0, t.height * 0.5), e.DamageAngle, e.Damage);

		double spd  = (cBurstSpeed != null) ? cBurstSpeed.GetFloat() : 4.0;
		double lift = (cBurstLift  != null) ? cBurstLift.GetFloat()  : 3.0;

		for (int i = 0; i < n; i++)
		{
			double ang = FRandom[RTBlood](0.0, 360.0);
			double rad = FRandom[RTBlood](0.0, t.radius);
			Vector3 at = (t.pos.X + cos(ang) * rad,
			              t.pos.Y + sin(ang) * rad,
			              t.pos.Z + FRandom[RTBlood](0.25, 0.8) * t.height);

			// NO_REPLACE: GetBloodType already walked the replacement chain
			// Blood -> 64Blood -> RTBloodPersist, exactly as P_SpawnBlood does.
			Actor b = Actor.Spawn(bloodcls, at, NO_REPLACE);
			if (b == null) { continue; }

			if (!b.bDontTranslate) { b.Translation = t.BloodTranslation; }

			// 64Blood has Gravity 0.65, and gravity lives in Actor::Tick rather
			// than in the state machine, so these arc and settle on their own --
			// the same reason the hitscan splats already fall correctly.
			double s = spd * FRandom[RTBlood](0.5, 1.0);
			b.Vel   = (cos(ang) * s, sin(ang) * s, FRandom[RTBlood](lift * 0.4, lift));
			b.Angle = ang;
		}
	}

	override void WorldThingSpawned(WorldEvent e)
	{
		Actor t = e.Thing;
		if (t == null || !(t is "Blood")) { return; }

		// 64NoBlood is a Blood subclass with Alpha 0 that exists purely to make
		// certain monsters bleed nothing. It self-destructs after a tic; keep it
		// out of the queue rather than letting it churn slots.
		if (t.Alpha <= 0) { return; }

		ResolveCVars();

		// SIZE. Permanent blood is the case where identical sprites read as a
		// repeated stamp -- the reason this jitter exists at all.
		// NOT named `var` -- that is a reserved word in ZScript and the whole
		// pk3 fails to parse with "Unexpected token 'var'".
		double jitter = (cScaleVar != null) ? cScaleVar.GetFloat() : 0.0;
		if (jitter > 0)
		{
			double s = 1.0 + FRandom[RTBlood](-1.0, 1.0) * jitter;
			if (s < 0.5) { s = 0.5; }
			t.Scale = (t.Scale.X * s, t.Scale.Y * s);
		}

		// MIRROR. Free asymmetry: RF_XFLIP is a UV flip, no extra geometry.
		t.bXFLIP = (Random[RTBlood](0, 1) == 1);

		// ROLL. Opt-in until it is confirmed to survive the RTGL1 upload.
		if (cRoll != null && cRoll.GetBool())
		{
			t.bROLLSPRITE = true;
			t.Roll = FRandom[RTBlood](0.0, 360.0);
		}

		splats.Push(t);
		born.Push(level.time);

		// Cheap half of the bookkeeping: only trim the front. The full compact
		// runs once a second in WorldTick, so a shotgun blast does not walk a
		// 1500-entry array twenty times in one tic.
		int cap = MaxSplats();
		if (cap > 0)
		{
			while (int(splats.Size()) > cap)
			{
				Actor oldest = splats[0];
				if (oldest != null) { oldest.Destroy(); }
				splats.Delete(0);
				born.Delete(0);
			}
		}
	}

	override void WorldTick()
	{
		if (level.time % 35 != 0) { return; }

		int life = LifeTics();
		int i = 0;
		while (i < int(splats.Size()))
		{
			Actor a = splats[i];
			bool gone = (a == null);
			if (!gone && life > 0 && level.time - born[i] >= life)
			{
				a.Destroy();
				gone = true;
			}
			if (gone)
			{
				splats.Delete(i);
				born.Delete(i);
				continue;
			}
			i++;
		}
	}
}
'''


LUMPS = {
    "MAPINFO": MAPINFO,
    "CVARINFO": CVARINFO,
    "DECORATE": DECORATE,
    "ZSCRIPT": ZSCRIPT,
}


def build(dry: bool) -> int:
    print(f"{OUT.name}: {len(LUMPS)} lump(s), no sprites (BLUD A-D come from D64RTR_v15.WAD)")
    for name, text in LUMPS.items():
        print(f"   {name:<9} {len(text):>5} bytes")
    print("   DECORATE: 3 replacements, each Spawn ending on 'BLUD A -1'")
    print("   ZSCRIPT:  RTBloodPersistHandler -- scale/flip/roll jitter + FIFO cap")
    print("             + WorldThingDamaged explosion burst (DMG_EXPLOSION)")
    print(f"   CVARINFO: {CVARINFO.count('server noarchive')} cvars"
          f" ({CVARINFO.count('rt_gore_burst')} burst mentions)")

    if dry:
        print("\nPass --apply to write the pk3.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in LUMPS.items():
            z.writestr(name, text)
    print(f"\nwrote {OUT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    return build(dry=not args.apply)


if __name__ == "__main__":
    sys.exit(main())
