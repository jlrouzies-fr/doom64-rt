"""Make Unseen Evil barrels enter Retribution's RT explosion path.

UE v1.0.3 explodes ``D64UE_ExplosiveBarrel`` on ``BAR1 D`` and immediately
stops the actor.  Retribution, the volumetric barrel-smoke detector, and the
authored plate/scorch/ember system all agree on a different contract: the
explosion occurs on the rising edge of ``BEXP E``.  Missing that frame makes
the UE barrel disappear without any of the RT work firing.

This late, UE-only overlay keeps UE's replacement class, dimensions, health,
damage type, and explosion helper.  It changes only the death presentation to
Retribution's BEXP A-E timing, copies those exact Retribution frames, and gives
UE's separate explosion sprite the same timing/fade as Retribution's helper.

Usage:
    py -3 tools/make_unseenevil_barrel.py --write
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
UE = ROOT / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
RETRIBUTION = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-retribution-barrel.pk3"
SOURCE = "zscript/props.zsc"
FRAMES = tuple(f"BEXP{frame}0" for frame in "ABCDE")

START = "class D64UE_ExplosiveBarrel : Actor replaces ExplosiveBarrel\n"
END = "Class Column64 : Actor replaces Column\n"

REPLACEMENT = r'''class D64UE_ExplosiveBarrel : Actor replaces ExplosiveBarrel
{
	Default
	{
		XScale D64_SCALEX;
		YScale D64_SCALEY;
		Health 20;
		Radius 10;
		Height 42;
		+SOLID
		+SHOOTABLE
		+NOBLOOD
		+ACTIVATEMCROSS
		+DONTGIB
		+NOICEDEATH
		+OLDRADIUSDMG
		DeathSound "world/barrelx";
		Obituary "$OB_BARREL";
	}

	States
	{
	Spawn:
		BAR1 A -1;
		Stop;
	Death:
		BEXP ABC 5;
		BEXP D 5 A_Scream;
		BEXP E 0 A_NoBlocking;
		BEXP E 0 A_SpawnItemEx("BarrelExplosion64", 0, 0, 25);
		BEXP E 5 A_Explode(damagetype: 'ExplosiveBarrel');
		BEXP E 7 A_SetTranslucent(0.0);
		BEXP E 9;
		Stop;
	}
}

class BarrelExplosion64 : Actor
{
	Default
	{
		XScale D64_SCALEX;
		YScale D64_SCALEY;
		+NOBLOCKMAP
		+NOGRAVITY
		+BRIGHT
		Alpha 0.60;
		RenderStyle "Translucent";
	}
	States
	{
	Spawn:
		MISL B 0 BRIGHT;
		MISL B 8 BRIGHT;
		MISL C 6 BRIGHT A_FadeOut(0.12);
		MISL D 3 BRIGHT A_FadeOut(0.12);
		MISL EF 3 BRIGHT A_FadeOut(0.12);
		Stop;
	}
}


'''


def wad_lumps(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()
    if data[:4] not in (b"IWAD", b"PWAD"):
        raise SystemExit(f"not a WAD: {path}")
    count, directory = struct.unpack_from("<II", data, 4)
    result: dict[str, bytes] = {}
    for i in range(count):
        offset, size, raw_name = struct.unpack_from("<II8s", data, directory + i * 16)
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        if size:
            result[name] = data[offset : offset + size]
    return result


def sources() -> dict[str, bytes]:
    if not UE.exists():
        raise SystemExit(f"missing {UE}")
    with ZipFile(UE) as source:
        text = source.read(SOURCE).decode("utf-8").replace("\r\n", "\n")

    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("UE barrel source markers changed; refusing a blind patch")
    begin = text.index(START)
    finish = text.index(END, begin)
    text = text[:begin] + REPLACEMENT + text[finish:]

    if not RETRIBUTION.exists():
        raise SystemExit(f"missing {RETRIBUTION}")
    lumps = wad_lumps(RETRIBUTION)
    result = {SOURCE: text.encode("utf-8")}
    for name in FRAMES:
        if name not in lumps:
            raise SystemExit(f"{RETRIBUTION.name}: missing {name}")
        result[f"sprites/barrel/{name}"] = lumps[name]
    return result


def verify_output(expected: dict[str, bytes]) -> None:
    with ZipFile(OUT) as package:
        actual = {
            info.filename: package.read(info.filename)
            for info in package.infolist()
            if not info.is_dir()
        }
    if actual != expected:
        raise SystemExit("generated barrel package differs from patched sources")
    props = actual[SOURCE]
    for required in (
        b"BEXP ABC 5",
        b"BEXP E 5 A_Explode(damagetype: 'ExplosiveBarrel')",
        b"BEXP E 7 A_SetTranslucent(0.0)",
        b"MISL C 6 BRIGHT A_FadeOut(0.12)",
    ):
        if required not in props:
            raise SystemExit(f"generated package is missing {required!r}")
    print("verified: UE barrel reaches BEXP E; RT smoke/debris trigger is live")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    built = sources()
    print(f"affected UE source: {SOURCE}; Retribution frames: {len(FRAMES)}")
    if not args.write:
        print(f"census only; pass --write to build {OUT.name}")
        return

    with ZipFile(OUT, "w", compression=ZIP_DEFLATED) as package:
        for path, data in sorted(built.items()):
            package.writestr(path, data)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    verify_output(built)


if __name__ == "__main__":
    main()
