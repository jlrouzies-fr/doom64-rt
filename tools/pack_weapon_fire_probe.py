"""Pack d64r-weapon-fire-probe.pk3 — a no-input repro for "the gun goes transparent
while shooting".

The real Fire animation flips frames every 1-3 tics, far too fast to correlate a
screenshot with a frame. So the probe defines a subclass of the mod's own weapon whose
Fire state holds each interesting frame for HOLD tics, and screenshots the middle of
each hold. Frames are paired BRIGHT / not-BRIGHT so the fullbright flag itself is
isolated: the mod marks every plasma fire frame BRIGHT and no idle frame, which is the
prime suspect for the fire-only transparency.

  python tools/pack_weapon_fire_probe.py [plasma|bfg]

Launch with tools/probe-weapon-fire.ps1.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(r"G:\ai\Doom64-RT")
OUT = ROOT / "Doom64-Retribution" / "d64r-weapon-fire-probe.pk3"

HOLD = 25  # tics per frame

# (label, sprite, frame letter, bright[, action]) — action runs on entering the frame.
# The "live" set holds each frame long enough to screenshot WHILE a real plasma ball is
# in flight and the real muzzle-flash extralight is up, which the dry frame-hold set
# cannot show: the dry set proved the frames themselves render, so anything that only
# breaks during a real shot has to come from the projectile or the flash light.
PLASMA_LIVE_STEPS = [
    ("live-idle-before", "PLSG", "A", False, None),
    ("live-shoot-flash", "PLSF", "B", True,
     'A_FireCustomMissile("64PlasmaBall", 0, 1, 0, -5, 0, 0)'),
    ("live-shoot-gunflash", "PLSF", "B", True, "A_GunFlash"),
    ("live-ball-inflight", "PLSF", "A", True, None),
    ("live-ball-gone", "PLSG", "D", False, None),
    ("live-idle-after", "PLSG", "A", False, None),
]

# (label, sprite, frame letter, bright)
PLASMA_STEPS = [
    ("PLSGA-idle", "PLSG", "A", False),
    ("PLSGR-bright", "PLSG", "R", True),
    ("PLSGR-plain", "PLSG", "R", False),
    ("PLSFB-bright", "PLSF", "B", True),
    ("PLSFB-plain", "PLSF", "B", False),
    ("PLSFA-bright", "PLSF", "A", True),
    ("PLSFA-plain", "PLSF", "A", False),
    ("PLSGD-plain", "PLSG", "D", False),
    ("PLSGD-bright", "PLSG", "D", True),
    ("PLSGE-plain", "PLSG", "E", False),
]

BFG_STEPS = [
    ("BFGGA-idle", "BFGG", "A", False),
    ("BFGGA-bright", "BFGG", "A", True),
    ("BFGGD-plain", "BFGG", "D", False),
    ("BFGGD-bright", "BFGG", "D", True),
    ("BFGFA-bright", "BFGF", "A", True),
    ("BFGFA-plain", "BFGF", "A", False),
]

# Same as PLASMA_LIVE_STEPS but the shot is the mod's own invisible, lightless dummy
# projectile. Everything else — frames, BRIGHT flags, A_GunFlash/extralight — is
# identical, so a solid gun here pins the ghosting on the plasma ball itself.
PLASMA_DUMMY_STEPS = [
    (lbl, spr, frm, br, ('A_FireCustomMissile("DummyProjectile3", 0, 1, 0, -5, 0, 0)'
                         if act and "64PlasmaBall" in act else act))
    for lbl, spr, frm, br, act in PLASMA_LIVE_STEPS
]

WEAPONS = {
    # steps=None -> autofire mode: the mod's real weapon, real timings, re-entering Fire
    # on the weapon's own cadence, one screenshot per tic. Held frames cannot show
    # anything that only emerges from the frames CHANGING every 1-3 tics.
    "plasma-auto": ("64PlasmaRifle", "Cell", 600, None),
    "plasma": ("64PlasmaRifle", "Cell", 600, PLASMA_STEPS),
    "plasma-live": ("64PlasmaRifle", "Cell", 600, PLASMA_LIVE_STEPS),
    "plasma-dummy": ("64PlasmaRifle", "Cell", 600, PLASMA_DUMMY_STEPS),
    "bfg": ("64BFG9000", "Cell", 600, BFG_STEPS),
}

MAPINFO = """GameInfo
{
\tAddEventHandlers = "D64RtWeaponFireProbe"
}
"""

DECORATE_TMPL = """ACTOR D64RtProbeWeapon : %(base)s
{
\tWeapon.SlotNumber 0
\t+WEAPON.NOAUTOFIRE
\tStates
\t{
\t\tReady:
\t\t\t%(readyspr)s %(readyfrm)s 1 A_WeaponReady
\t\t\tLoop
\t\tSelect:
\t\t\t%(readyspr)s %(readyfrm)s 0 A_Raise
\t\t\t%(readyspr)s %(readyfrm)s 1 A_Raise
\t\t\tLoop
\t\tDeselect:
\t\t\t%(readyspr)s %(readyfrm)s 0 A_Lower
\t\t\t%(readyspr)s %(readyfrm)s 1 A_Lower
\t\t\tLoop
\t\tFire:
%(firestates)s
\t\t\tGoto Ready
\t\tFlash:
\t\t\tTNT1 A 2 BRIGHT A_Light1
\t\t\tTNT1 A 1 BRIGHT A_Light0
\t\t\tGoto LightDone
\t}
}
"""

ZSCRIPT = """version "4.12"

// Holds one weapon frame at a time and screenshots each hold, so an image can be
// matched to a frame with certainty. No player input, no teleport.
class D64RtWeaponFireProbe : EventHandler
{
\tconst WEAPON_CLS = "D64RtProbeWeapon";
\tconst AMMO_CLS = "%(ammo)s";
\tconst AMMO_AMT = %(ammoamt)d;
\tconst HOLD = %(hold)d;
\tconst SETTLE = 70;

\tprivate int phase;
\tprivate int timer;
\tprivate int step;

\tstatic const String Labels[] = { %(labels)s };

\toverride void WorldLoaded(WorldEvent e)
\t{
\t\tphase = 0;
\t\ttimer = SETTLE;
\t\tstep = 0;
\t}

\tprivate void Report(PlayerInfo p, String tag)
\t{
\t\tPSprite psp = p.FindPSprite(PSprite.WEAPON);
\t\tif (psp == null)
\t\t{
\t\t\tConsole.Printf("PROBE t=%%d %%s WEAPON-LAYER=NONE", level.maptime, tag);
\t\t\treturn;
\t\t}
\t\tConsole.Printf("PROBE t=%%d %%s spr=%%d frame=%%d alpha=%%.3f",
\t\t\tlevel.maptime, tag, int(psp.Sprite), psp.Frame, psp.alpha);
\t}

\toverride void WorldTick()
\t{
\t\tif (level.maptime < 8)
\t\t\treturn;
\t\tPlayerInfo p = players[consoleplayer];
\t\tif (p == null || p.mo == null)
\t\t\treturn;
\t\tp.mo.vel = (0, 0, 0);

\t\tif (phase == 0)
\t\t{
\t\t\tp.mo.A_GiveInventory(AMMO_CLS, AMMO_AMT);
\t\t\tp.mo.A_GiveInventory(WEAPON_CLS, 1);
\t\t\tlet w = Weapon(p.mo.FindInventory(WEAPON_CLS));
\t\t\tif (w == null)
\t\t\t{
\t\t\t\tConsole.Printf("PROBE: could not give %%s", WEAPON_CLS);
\t\t\t\tphase = 3;
\t\t\t\treturn;
\t\t\t}
\t\t\tp.PendingWeapon = w;
\t\t\tphase = 1;
\t\t\ttimer = SETTLE;
\t\t\treturn;
\t\t}

\t\tif (phase == 1)
\t\t{
\t\t\tif (timer > 0)
\t\t\t{
\t\t\t\ttimer--;
\t\t\t\treturn;
\t\t\t}
\t\t\tif (p.ReadyWeapon == null || p.ReadyWeapon.GetClassName() != WEAPON_CLS)
\t\t\t{
\t\t\t\ttimer = 10;
\t\t\t\treturn;
\t\t\t}
\t\t\tState fire = p.ReadyWeapon.FindState('Fire');
\t\t\tif (fire == null)
\t\t\t{
\t\t\t\tConsole.Printf("PROBE: no Fire state");
\t\t\t\tphase = 3;
\t\t\t\treturn;
\t\t\t}
\t\t\tp.SetPsprite(PSprite.WEAPON, fire);
\t\t\tstep = 0;
\t\t\ttimer = HOLD / 2;
\t\t\tphase = 2;
\t\t\treturn;
\t\t}

\t\tif (phase == 2)
\t\t{
\t\t\tif (timer > 0)
\t\t\t{
\t\t\t\ttimer--;
\t\t\t\treturn;
\t\t\t}
\t\t\tif (step >= Labels.Size())
\t\t\t{
\t\t\t\tConsole.Printf("PROBE: done");
\t\t\t\tphase = 3;
\t\t\t\treturn;
\t\t\t}
\t\t\tReport(p, Labels[step]);
\t\t\tlevel.MakeScreenShot();
\t\t\tstep++;
\t\t\ttimer = HOLD - 1;
\t\t}
\t}
}
"""

ZSCRIPT_AUTO = """version "4.12"

// Autofire mode: the mod's own weapon, its own state timings, trigger held down.
// Re-enters Fire whenever the weapon layer falls back to Ready — the same thing
// P_CheckWeaponFire does for a held attack button — and screenshots every tic, so a
// defect that only appears while the frames are actually flipping shows up.
class D64RtWeaponFireProbe : EventHandler
{
\tconst WEAPON_CLS = "%(weapon)s";
\tconst AMMO_CLS = "%(ammo)s";
\tconst AMMO_AMT = %(ammoamt)d;
\tconst SETTLE = 70;
\tconst SHOTS = 40;

\tprivate int phase;
\tprivate int timer;
\tprivate int shotsLeft;

\toverride void WorldLoaded(WorldEvent e)
\t{
\t\tphase = 0;
\t\ttimer = SETTLE;
\t\tshotsLeft = SHOTS;
\t}

\toverride void WorldTick()
\t{
\t\tif (level.maptime < 8)
\t\t\treturn;
\t\tPlayerInfo p = players[consoleplayer];
\t\tif (p == null || p.mo == null)
\t\t\treturn;
\t\tp.mo.vel = (0, 0, 0);

\t\tif (phase == 0)
\t\t{
\t\t\tp.mo.A_GiveInventory(AMMO_CLS, AMMO_AMT);
\t\t\tp.mo.A_GiveInventory(WEAPON_CLS, 1);
\t\t\tlet w = Weapon(p.mo.FindInventory(WEAPON_CLS));
\t\t\tif (w == null)
\t\t\t{
\t\t\t\tConsole.Printf("PROBE: could not give %%s", WEAPON_CLS);
\t\t\t\tphase = 3;
\t\t\t\treturn;
\t\t\t}
\t\t\tp.PendingWeapon = w;
\t\t\tphase = 1;
\t\t\ttimer = SETTLE;
\t\t\treturn;
\t\t}

\t\tif (phase == 1)
\t\t{
\t\t\tif (timer > 0)
\t\t\t{
\t\t\t\ttimer--;
\t\t\t\treturn;
\t\t\t}
\t\t\tif (p.ReadyWeapon == null || p.ReadyWeapon.GetClassName() != WEAPON_CLS)
\t\t\t{
\t\t\t\ttimer = 10;
\t\t\t\treturn;
\t\t\t}
\t\t\tphase = 2;
\t\t\treturn;
\t\t}

\t\tif (phase == 2)
\t\t{
\t\t\tif (shotsLeft <= 0)
\t\t\t{
\t\t\t\tConsole.Printf("PROBE: done");
\t\t\t\tphase = 3;
\t\t\t\treturn;
\t\t\t}
\t\t\t// Trigger held. Comparing CurState against the Ready label does not work —
\t\t\t// the mod's Ready jumps straight into a separate ReadyLoop label, so that
\t\t\t// test never matched and the probe just idled. Re-enter Fire on the weapon's
\t\t\t// own cycle length instead (plasma: R1 + B3 + A1 + D1 = %(cycle)d tics).
\t\t\tif (p.ReadyWeapon != null && (shotsLeft %% %(cycle)d) == 0
\t\t\t\t&& p.ReadyWeapon.CheckAmmo(Weapon.PrimaryFire, false))
\t\t\t{
\t\t\t\tp.SetPsprite(PSprite.WEAPON, p.ReadyWeapon.FindState('Fire'));
\t\t\t}
\t\t\tPSprite w = p.FindPSprite(PSprite.WEAPON);
\t\t\tPSprite fl = p.FindPSprite(PSprite.FLASH);
\t\t\tif (w == null)
\t\t\t\tConsole.Printf("PROBE t=%%d AUTO WEAPON-LAYER=NONE", level.maptime);
\t\t\telse
\t\t\t\tConsole.Printf("PROBE t=%%d AUTO spr=%%d frame=%%d alpha=%%.3f flash=%%d",
\t\t\t\t\tlevel.maptime, int(w.Sprite), w.Frame, w.alpha, fl != null ? 1 : 0);
\t\t\tlevel.MakeScreenShot();
\t\t\tshotsLeft--;
\t\t}
\t}
}
"""


def main() -> None:
    which = (sys.argv[1] if len(sys.argv) > 1 else "plasma").lower()
    if which not in WEAPONS:
        raise SystemExit(f"usage: {sys.argv[0]} [{'|'.join(WEAPONS)}]")
    base, ammo, amt, steps = WEAPONS[which]

    if steps is None:
        zs = ZSCRIPT_AUTO % {"weapon": base, "ammo": ammo, "ammoamt": amt, "cycle": 6}
        with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("MAPINFO", MAPINFO)
            z.writestr("ZSCRIPT", zs)
        print(f"wrote {OUT}  ({which} -> {base}, autofire)")
        return

    fire_lines = []
    for step in steps:
        _label, spr, frm, bright = step[:4]
        action = step[4] if len(step) > 4 else None
        fire_lines.append(
            f"\t\t\t{spr} {frm} {HOLD}{' BRIGHT' if bright else ''}"
            + (f" {action}" if action else "")
        )
    decorate = DECORATE_TMPL % {
        "base": base,
        "readyspr": steps[0][1],
        "readyfrm": steps[0][2],
        "firestates": "\n".join(fire_lines),
    }
    zs = ZSCRIPT % {
        "ammo": ammo,
        "ammoamt": amt,
        "hold": HOLD,
        "labels": ", ".join(f'"{s[0]}"' for s in steps),
    }
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MAPINFO", MAPINFO)
        z.writestr("DECORATE", decorate)
        z.writestr("ZSCRIPT", zs)
    print(f"wrote {OUT}  ({which} -> {base}, {len(steps)} frames x {HOLD} tics)")


if __name__ == "__main__":
    main()
