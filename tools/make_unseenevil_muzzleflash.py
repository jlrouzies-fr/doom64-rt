"""Give Unseen Evil Retribution's first-person weapon presentation under RT.

The shared RT renderer keys its analytic muzzle flash, smoke, and plasma-gun
discharge boost on ``player.extralight``.  Retribution's weapon Flash states
raise that value with ``A_Light1``/``A_Light2`` and return through
``LightDone`` (which calls ``A_Light0``). UE v1.0.3 comments out or omits those
calls on its ballistic weapons even though their muzzle artwork is present.

The missing effects are not all renderer lights. Retribution's modern weapons
use dedicated animation and flash art that UE replaces with shorter, different
sequences: UNMF over the Unmaker, BFGF's green charge, PLSF plus PLSG D-H-D on
the plasma rifle, CHGG A-D plus paired CHGF flashes, and the extended SHTG/SH2F
reload sequences. Copy those original frames and reproduce their visual timing
while retaining UE's firing functions, ammo rules, projectiles, sounds, and
weapon classes.

The two small ballistic/Unmaker flash overlays get UE-only sprite aliases. The
art and offsets remain Retribution's, but the aliases deliberately do not match
the shared CHGF/UNMF material rows: UE's exposure made CHGF's screen emission
too hot, while UNMF's 900-intensity attached light lit the room from the HUD
quad and blew the whole Unmaker white. Analytic scene light remains driven by
the A_Light states, and the engine supplies the separate UE model-beam lights.
UE also retracts that model at 32 map units per tic, often completing between
two path-traced frames. The overlay slows only that visual actor to 12 units per
tic; the hitscan damage has already happened, so gameplay is unchanged while
the beam and its distributed lights remain observable.

Retribution stores its shotgun and super-shotgun animation art as ordinary
sprites. Those files must stay in the PK3 ``sprites/`` namespace; putting them
under ``patches/`` makes SHTG I/J disappear and makes every SH2G/SH2F firing
frame invisible. UE already supplies SHTG A-H and applies ``NoTrim`` to those
exact texture objects while its own TEXTURES file is parsed. Overriding them
from a later archive changes the object seen by that directive and aborts
startup, so the overlay deliberately keeps UE's eight compatible base frames
and adds only the missing Retribution sprites. Composite
chaingun/plasma/BFG/Unmaker art remains in ``patches/`` because the copied
TEXTURES blocks reference it there.

Two more compatibility repairs belong beside the muzzle trigger:

* gzdoom-rt's built-in ``CheelloRocket replaces Rocket`` wins over UE's own
  replacement at runtime.  That silently drops UE's projectile smoke sprites
  and its attached orange light.  The renderer restores that light under UE's
  compatibility identity; this package must not try to replace CheelloRocket,
  because engine ZScript is parsed after content and that class does not exist
  yet while this overlay is compiled.
* UE's live rocket inherits GZDoom's stock ``+ROCKETTRAIL`` particle/sprite
  trail from CheelloRocket. The UE launcher disables that raster trail so the
  engine's independent volumetric medium is the only smoke representation.

This late overlay copies only the affected UE weapon source files plus original
Retribution weapon patches and their exact TEXTURES definitions. It never edits
either original archive and is loaded only by the UE launcher.

Usage:
    py -3 tools/make_unseenevil_muzzleflash.py --write
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
UE = ROOT / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
RETRIBUTION = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-muzzleflash.pk3"

WEAPON_DIR = "zscript/d64ue/weapons"

# Exact source transformations.  Counts are checked before anything is written,
# so a future UE update cannot silently apply these to the wrong state.
PATCHES: dict[str, tuple[tuple[str, str, int], ...]] = {
    f"{WEAPON_DIR}/pistol.zsc": (
        (
            "\t\tFlash:\n"
            "\t\t\tPISG D 3 BRIGHT;\n"
            "\t\t\tStop;",
            "\t\tFlash:\n"
            "\t\t\tPISG D 1 BRIGHT A_Light1;\n"
            "\t\t\tPISG D 2 BRIGHT A_Light2;\n"
            "\t\t\tGoto LightDone;",
            1,
        ),
    ),
    f"{WEAPON_DIR}/rocketlauncher.zsc": (
        (
            "\t\tROCK C 3 Bright;// A_Light1;",
            "\t\tROCK C 3 Bright A_Light1;",
            1,
        ),
        (
            "\t\tROCK EF 4 Bright;// A_Light2;",
            "\t\tROCK EF 4 Bright A_Light2;",
            1,
        ),
    ),
    f"{WEAPON_DIR}/shotgun.zsc": (
        (
            "\t\t+D64UE_Weapon_Base.CORRECTASPECT\n",
            "\t\t// RT: UESG/UESF use Retribution's native psprite aspect.\n",
            1,
        ),
    ),
    f"{WEAPON_DIR}/unmaker.zsc": (
        (
            "\t\tdist += 32 * D64_SCALEX;",
            "\t\tdist += 12 * D64_SCALEX; // RT: retain the visual beam across traced frames.",
            1,
        ),
    ),
}

# Replace only Fire/Flash presentation spans. The markers are unique in the
# pinned UE v1.0.3 sources; counts are checked before replacement. Gameplay
# remains UE's because every firing action below calls the original UE method.
STATE_SPANS: dict[str, tuple[str, str, str]] = {
    f"{WEAPON_DIR}/shotgun.zsc": (
        "\t\tReady:\n",
        "\t\tSpawn:\n",
        "\t\tReady:\n"
        "\t\t\tUESG A 1 A_WeaponReady;\n"
        "\t\t\tLoop;\n"
        "\t\tDeselect:\n"
        "\t\t\tUESG A 1 A_Lower();\n"
        "\t\t\tLoop;\n"
        "\t\tSelect:\n"
        "\t\t\tUESG A 1 A_Raise();\n"
        "\t\t\tLoop;\n"
        "\t\tFire:\n"
        "\t\t\tUESG J 1\n"
        "\t\t\t{\n"
        "\t\t\t\tA_FireShotgun();\n"
        "\t\t\t\tA_D64Recoil();\n"
        "\t\t\t}\n"
        "\t\t\tUESG J 2;\n"
        "\t\t\tUESG I 3;\n"
        "\t\t\tUESG B 1;\n"
        "\t\t\tUESG C 1;\n"
        "\t\t\tUESG D 2;\n"
        "\t\t\tUESG E 3;\n"
        "\t\t\tUESG F 4;\n"
        "\t\t\tUESG G 1;\n"
        "\t\t\tUESG H 3;\n"
        "\t\t\tUESG GFEDC 2;\n"
        "\t\t\tUESG BIA 1;\n"
        "\t\t\tUESG A 2;\n"
        "\t\t\tUESG A 1 A_Refire();\n"
        "\t\t\tGoto Ready;\n"
        "\t\tFlash:\n"
        "\t\t\tUESF A 2 BRIGHT A_Light1;\n"
        "\t\t\tUESF B 2 BRIGHT A_Light2;\n"
        "\t\t\tGoto LightDone;\n",
    ),
    f"{WEAPON_DIR}/superdupershotgun.zsc": (
        "\tFire:\n",
        "\tSpawn:\n",
        "\tFire:\n"
        "\t\tTNT1 A 0 Offset(0,52);\n"
        "\t\tSH2G C 1\n"
        "\t\t{\n"
        "\t\t\tA_FireShotgun2();\n"
        "\t\t\tA_D64Recoil();\n"
        "\t\t}\n"
        "\t\tSH2G C 5;\n"
        "\t\tSH2G B 2;\n"
        "\t\tSH2G A 1 A_CheckReload;\n"
        "\t\tSH2F B 2;\n"
        "\t\tSH2F C 3;\n"
        "\t\tSH2F DE 2;\n"
        "\t\tSH2F F 2 A_StartSound(\"weapons/sshoto\", CHAN_5);\n"
        "\t\tSH2F GHIJK 2;\n"
        "\t\tSH2F L 2 A_StartSound(\"weapons/sshotl\", CHAN_5);\n"
        "\t\tSH2F MNOPQ 2;\n"
        "\t\tSH2F R 2 A_StartSound(\"weapons/sshotc\", CHAN_5);\n"
        "\t\tSH2F S 2;\n"
        "\t\tTNT1 A 0 Offset(0,32);\n"
        "\t\tSH2G A 2;\n"
        "\t\tSH2G A 1 A_Refire;\n"
        "\t\tGoto Ready;\n"
        "\tFlash:\n"
        "\t\tSSGF A 2 Bright A_Light1;\n"
        "\t\tSSGF B 2 Bright A_Light2;\n"
        "\t\tGoto LightDone;\n",
    ),
    f"{WEAPON_DIR}/chaingun.zsc": (
        "\tFire:\n",
        "\tSpawn:\n",
        "\tFire:\n"
        "\t\tCHGG A 1\n"
        "\t\t{\n"
        "\t\t\tA_FireCGun();\n"
        "\t\t\tA_GunFlash(\"Flash\");\n"
        "\t\t\tA_WeaponOffset(-1, 33);\n"
        "\t\t\tA_D64Recoil();\n"
        "\t\t}\n"
        "\t\tCHGG BCD 1;\n"
        "\t\tCHGG A 1\n"
        "\t\t{\n"
        "\t\t\tA_FireCGun();\n"
        "\t\t\tA_GunFlash(\"Flash2\");\n"
        "\t\t\tA_WeaponOffset(1, 33);\n"
        "\t\t\tA_D64Recoil();\n"
        "\t\t}\n"
        "\t\tCHGG BCD 1;\n"
        "\t\tCHGG C 0 A_ReFire();\n"
        "\t\tCHGG ABCD 1 A_WeaponReady();\n"
        "\t\tCHGG ABCD 2 A_WeaponReady();\n"
        "\t\tCHGG ABCD 3 A_WeaponReady();\n"
        "\t\tGoto Ready;\n"
        "\tFlash:\n"
        "\t\tUECF A 1 Bright A_Light2;\n"
        "\t\tUECF B 1 Bright A_Light2;\n"
        "\t\tGoto LightDone;\n"
        "\tFlash2:\n"
        "\t\tUECF C 1 Bright A_Light2;\n"
        "\t\tUECF D 1 Bright A_Light2;\n"
        "\t\tGoto LightDone;\n",
    ),
    f"{WEAPON_DIR}/plasmarifle.zsc": (
        "\t\tReady:\n",
        "\t\tSpawn:\n",
        "\t\tReady:\n"
        "\t\t\tPLSG A 0 A_StartSound(\"weapons/plasma/idle\", CHANNEL_WEAPONIDLE, CHANF_NOSTOP|CHANF_LOOP);\n"
        "\t\t\tGoto ReadyLoop;\n"
        "\t\tReadyLoop:\n"
        "\t\t\tPLSG ABC 2 A_WeaponReady();\n"
        "\t\t\tLoop;\n"
        "\t\tDeselect:\n"
        "\t\t\tPLSG A 0 A_StopSound(CHANNEL_WEAPONIDLE);\n"
        "\t\t\tPLSG A 1 A_Lower;\n"
        "\t\t\tLoop;\n"
        "\t\tSelect:\n"
        "\t\t\tPLSG A 0 A_StartSound(\"weapons/plasma/idle\", CHANNEL_WEAPONIDLE, CHANF_LOOP);\n"
        "\t\t\tPLSG A 1 A_Raise;\n"
        "\t\t\tWait;\n"
        "\t\tFire:\n"
        "\t\t\tPLSG R 1 Bright;\n"
        "\t\t\tPLSF B 3 Bright\n"
        "\t\t\t{\n"
        "\t\t\t\tA_FireProjectile(\"PlasmaBall\");\n"
        "\t\t\t\tA_GunFlash(\"Flash\");\n"
        "\t\t\t}\n"
        "\t\t\tPLSF A 1 Bright;\n"
        "\t\t\tPLSG D 1 A_ReFire;\n"
        "\t\t\tPLSG EFG 2;\n"
        "\t\t\tPLSG H 4;\n"
        "\t\t\tPLSG GFE 2;\n"
        "\t\t\tPLSG D 1;\n"
        "\t\t\tGoto Ready;\n"
        "\t\tFlash:\n"
        "\t\t\tTNT1 A 2 Bright A_Light1;\n"
        "\t\t\tTNT1 A 1 Bright A_Light0;\n"
            "\t\t\tGoto LightDone;\n",
    ),
    f"{WEAPON_DIR}/bfg9000.zsc": (
        "\t\tReady:\n",
        "\t\tSpawn:\n",
        "\t\tReady:\n"
        "\t\t\tBFGG A 1 A_WeaponReady;\n"
        "\t\t\tLoop;\n"
        "\t\tDeselect:\n"
        "\t\t\tBFGG A 1 A_Lower;\n"
        "\t\t\tLoop;\n"
        "\t\tSelect:\n"
        "\t\t\tBFGG A 1 A_Raise;\n"
        "\t\t\tLoop;\n"
        "\t\tFire:\n"
        "\t\t\tBFGG A 20 A_BFGSound;\n"
        "\t\t\tBFGG A 2 A_GunFlash;\n"
        "\t\t\tBFGG A 8;\n"
        "\t\t\tBFGG D 1 A_FireBFG;\n"
        "\t\t\tBFGG D 1;\n"
        "\t\t\tBFGG E 2;\n"
        "\t\t\tBFGG D 3;\n"
        "\t\t\tBFGG C 2;\n"
        "\t\t\tBFGG B 1;\n"
        "\t\t\tBFGG A 29 A_ReFire;\n"
        "\t\t\tGoto Ready;\n"
        "\t\tFlash:\n"
        "\t\t\tBFGG A 2 Bright;\n"
        "\t\t\tBFGF HGFE 1 Bright A_Light2;\n"
        "\t\t\tBFGF DCBA 1 Bright A_Light2;\n"
        "\t\t\tTNT1 A 0 A_Light0;\n"
        "\t\t\tGoto LightDone;\n",
    ),
    f"{WEAPON_DIR}/unmaker.zsc": (
        "\t\tReady:\n",
        "\t\tSpawn:\n",
        "\t\tReady:\n"
        "\t\t\tUNMA A 1 A_WeaponReady();\n"
        "\t\t\tLoop;\n"
        "\t\tDeselect:\n"
        "\t\t\tUNMA A 1 A_Lower;\n"
        "\t\t\tLoop;\n"
        "\t\tSelect:\n"
        "\t\t\tUNMA A 1 A_Raise;\n"
        "\t\t\tWait;\n"
        "\t\tFire:\n"
        "\t\t\tUNMA A 8\n"
        "\t\t\t{\n"
        "\t\t\t\tA_D64_FireLaser();\n"
        "\t\t\t\tA_GunFlash(\"Flash\");\n"
        "\t\t\t}\n"
        "\t\t\tUNMA A 3 A_Refire;\n"
        "\t\t\tGoto Ready;\n"
        "\t\tFlash:\n"
        "\t\t\tUEMF A 3 Bright A_Light1;\n"
        "\t\t\tUEMF A 8 Bright A_Light0;\n"
        "\t\t\tGoto LightDone;\n",
    ),
}

RETRIBUTION_WEAPON_PATCHES = (
    *(f"SHTG{frame}0" for frame in "ABCDEFGHIJ"),
    "SHTFA0", "SHTFB0",
    *(f"SH2G{frame}0" for frame in "ABC"),
    *(f"SH2F{frame}0" for frame in "BCDEFGHIJKLMNOPQRS"),
    "SSGFA0", "SSGFB0",
    *(f"CHGG{frame}0" for frame in "ABCD"),
    *(f"CHGF{frame}0" for frame in "ABCD"),
    *(f"PLSG{frame}0" for frame in "ABCDEFGH"),
    "PLSGR0", "PLSFA0", "PLSFB0",
    *(f"BFGG{frame}0" for frame in "ABCDE"),
    *(f"BFGF{frame}0" for frame in "ABCDEFGH"),
    "UNMAA0", "UNMFA0",
)

# These frames are composite Sprite definitions in Retribution rather than raw
# patch placement. Copy their exact blocks so scale and HUD offsets match too.
RETRIBUTION_TEXTURE_SPRITES = (
    *(f"CHGG{frame}0" for frame in "ABCD"),
    *(f"CHGF{frame}0" for frame in "ABCD"),
    *(f"PLSG{frame}0" for frame in "ABCDEFGH"),
    "PLSGR0", "PLSFA0", "PLSFB0",
    *(f"BFGG{frame}0" for frame in "ABCDE"),
    *(f"BFGF{frame}0" for frame in "ABCDEFGH"),
    "UNMAA0", "UNMFA0",
)

# Entries not rebuilt as TEXTURES composites are live state sprites. Keep the
# namespaces distinct: a patch can be consumed by a composite but cannot be
# resolved directly by a four-letter weapon state.
RETRIBUTION_DIRECT_SPRITES = tuple(
    name for name in RETRIBUTION_WEAPON_PATCHES
    if name not in RETRIBUTION_TEXTURE_SPRITES
)

UE_DIRECT_ALIASES = {
    **{f"SHTG{frame}0": f"UESG{frame}0" for frame in "ABCDEFGHIJ"},
    **{f"SHTF{frame}0": f"UESF{frame}0" for frame in "AB"},
}

# Keep Retribution's exact composite geometry but give the two UE-only flash
# overlays names that cannot inherit the shared material rows described above.
UE_FLASH_ALIASES = {
    **{f"CHGF{frame}0": f"UECF{frame}0" for frame in "ABCD"},
    "UNMFA0": "UEMFA0",
}


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


def retr_texture_blocks(blob: bytes) -> bytes:
    text = blob.decode("utf-8").replace("\r\n", "\n")
    blocks: list[str] = []
    for name in RETRIBUTION_TEXTURE_SPRITES:
        marker = f"Sprite {name},"
        if text.count(marker) != 1:
            raise SystemExit(f"TEXTURES: expected one {marker!r}")
        start = text.index(marker)
        brace = text.index("{", start)
        end = text.index("\n}", brace) + 2
        block = text[start:end]
        if name in UE_FLASH_ALIASES:
            block = block.replace(
                f"Sprite {name},", f"Sprite {UE_FLASH_ALIASES[name]},", 1
            )
        if name == "UNMAA0":
            old = "Offset -99, -113 // -78"
            if block.count(old) != 1:
                raise SystemExit("UNMAA0: expected Retribution offset was not found")
            block = block.replace(
                old,
                "Offset -99, -133 // UE: lower the gun by 20 logical pixels",
                1,
            )
        elif name == "UNMFA0":
            old = "Offset -114, -113 // -78"
            if block.count(old) != 1:
                raise SystemExit("UNMFA0: expected Retribution offset was not found")
            block = block.replace(
                old,
                "Offset -114, -133 // UE: keep the red cap aligned with the gun",
                1,
            )
        blocks.append(block)
    return ("// Exact first-person Sprite definitions from D64RTR_v15.WAD.\n\n" +
            "\n\n".join(blocks) + "\n").encode("utf-8")


def patched_sources() -> dict[str, bytes]:
    if not UE.exists():
        raise SystemExit(f"missing {UE}")

    result: dict[str, bytes] = {}
    with ZipFile(UE) as source:
        paths = set(PATCHES) | set(STATE_SPANS)
        for path in sorted(paths):
            text = source.read(path).decode("utf-8").replace("\r\n", "\n")
            for old, new, expected in PATCHES.get(path, ()):
                count = text.count(old)
                if count != expected:
                    raise SystemExit(
                        f"{path}: expected {expected} exact source match(es), found {count}"
                    )
                text = text.replace(old, new)
            if path in STATE_SPANS:
                start_marker, end_marker, replacement = STATE_SPANS[path]
                if text.count(start_marker) != 1 or text.count(end_marker) < 1:
                    raise SystemExit(f"{path}: state-span markers are not unique/present")
                start = text.index(start_marker)
                end = text.index(end_marker, start)
                text = text[:start] + replacement + text[end:]
            result[path] = text.encode("utf-8")

    if not RETRIBUTION.exists():
        raise SystemExit(f"missing {RETRIBUTION}")
    lumps = wad_lumps(RETRIBUTION)
    for name in RETRIBUTION_WEAPON_PATCHES:
        if name not in lumps:
            raise SystemExit(f"{RETRIBUTION.name}: missing {name}")
        if name in RETRIBUTION_DIRECT_SPRITES:
            alias = UE_DIRECT_ALIASES.get(name, name)
            result[f"sprites/{alias}.png"] = lumps[name]
        else:
            result[f"patches/{name}"] = lumps[name]
    if "TEXTURES" not in lumps:
        raise SystemExit(f"{RETRIBUTION.name}: missing TEXTURES")
    result["TEXTURES"] = retr_texture_blocks(lumps["TEXTURES"])
    return result


def verify_output(expected: dict[str, bytes]) -> None:
    with ZipFile(OUT) as package:
        files = {
            info.filename: package.read(info.filename)
            for info in package.infolist()
            if not info.is_dir()
        }
    if files != expected:
        raise SystemExit("generated muzzle-flash package differs from patched sources")

    direct_paths = {
        f"sprites/{UE_DIRECT_ALIASES.get(name, name)}.png"
        for name in RETRIBUTION_DIRECT_SPRITES
    }
    composite_paths = {
        f"patches/{name}" for name in RETRIBUTION_TEXTURE_SPRITES
    }
    if {path for path in files if path.startswith("sprites/")} != direct_paths:
        raise SystemExit("direct shotgun/SSG art is not exactly in the sprite namespace")
    if {path for path in files if path.startswith("patches/")} != composite_paths:
        raise SystemExit("TEXTURES inputs are not exactly in the patch namespace")

    joined = b"\n".join(files.values())
    for required in (
        b"A_Light1",
        b"A_Light2",
        b"Goto LightDone",
        b"UESG J 1",
        b"UESF A 2 BRIGHT A_Light1",
        b"TNT1 A 0 Offset(0,52)",
        b"TNT1 A 0 Offset(0,32)",
        b"SH2F R 2",
        b"SSGF A 2 Bright A_Light1",
        b"CHGG ABCD 3 A_WeaponReady",
        b"UECF A 1 Bright A_Light2",
        b"PLSF B 3 Bright",
        b"PLSG EFG 2",
        b"BFGF HGFE 1 Bright A_Light2",
        b"UEMF A 3 Bright A_Light1",
        b"UEMF A 8 Bright A_Light0",
        b"dist += 12 * D64_SCALEX",
        b"Sprite UEMFA0,",
        b"Offset -99, -133",
        b"Offset -114, -133",
    ):
        if required not in joined:
            raise SystemExit(f"generated package is missing {required!r}")
    print(
        f"verified: {len(files)} files; Retribution shotgun/SSG/chaingun/"
        "plasma/BFG/Unmaker presentation and ballistic triggers present"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    sources = patched_sources()
    source_count = sum(path.startswith(f"{WEAPON_DIR}/") for path in sources)
    patch_count = sum(path.startswith("patches/") for path in sources)
    sprite_count = sum(path.startswith("sprites/") for path in sources)
    print(
        f"affected UE weapon sources: {source_count}; Retribution art: "
        f"{patch_count} composite patches + {sprite_count} direct sprites"
    )
    if not args.write:
        print(f"census only; pass --write to build {OUT.name}")
        return

    with ZipFile(OUT, "w", compression=ZIP_DEFLATED) as package:
        for path, data in sorted(sources.items()):
            package.writestr(path, data)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    verify_output(sources)


if __name__ == "__main__":
    main()
