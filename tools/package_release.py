"""Assemble the Doom 64 - Ray Traced release package.

Takes a finished build tree and produces a folder (and optionally a zip) that a
user can extract and run, containing everything EXCEPT the things we are not
allowed to ship: the DOOM II IWAD, Doom 64: Retribution, its brightmaps, its
soundfont and the OGG music pack. Those are what the startup check asks for.

    python tools/package_release.py --out dist --zip

Most of the work is deciding what to leave out. The raw build tree is ~2.9 GB and
about 90% of that is Doom II: Ray Traced's own content, which this project does
not use and has no right to redistribute.
"""
from pathlib import Path
import argparse
import os
import shutil
import sys
import zipfile

PROJ_ROOT = Path(__file__).resolve().parents[1]

BUILD = PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo"

# Engine files that belong in the package. Everything else at the build root is
# either a PDB or somebody else's game.
ENGINE_FILES = [
    "gzdoom.exe", "gzdoom.pk3", "game_support.pk3", "game_widescreen_gfx.pk3",
    "lights.pk3", "brightmaps.pk3",
    "zmusic.dll", "libsndfile-1.dll", "openal32.dll",
]

# Under rt/ : what we keep, and why everything else goes.
RT_KEEP_DIRS = {
    "bin":      "RTGL1.dll + the DLSS/FSR runtime",
    "shaders":  "the SPIR-V RTGL1 just built",
    "data":     "our authored textures.json (~236 KB, not the stock 30 KB one)",
    "mat_dev":  "our authored PNG materials - what developerMode reads",
    "wad":      "our menu overlay",
}
RT_DROP_DIRS = {
    "replace_old":        "1.9 GB of Doom II glTF replacements, unused here",
    "scenes":             "Doom II static scenes; our maps have none",
    "scenes_doom2_backup": "backup of the above",
    "bin_remix":          "the D3D9/Remix path; we are native Vulkan",
    "mat":                "stock Doom II KTX2 materials; developerMode reads mat_dev",
    "mat_src":            "source art for the above",
    "launcher":           "RT's own launcher; we pass -rtnolauncher",
    "mat_quarantine_water": "disabled art",
    "mat_dev_quarantine_water": "disabled art",
}
# rt/wad is Doom II: Ray Traced's resource wad. Its filter/ and sounds/ subtrees
# are 224 MB of Doom II assets; the small lumps are engine plumbing we do want.
RT_WAD_DROP = {"filter", "sounds"}

# Exactly what the launcher loads -- not every d64r-*.pk3 in the tree, which
# would drag in the galleries, the smoke lab and the A/B probes.
# D64RTR_BRIGHTMAPS.PK3 is deliberately NOT here: it is Retribution's file, so
# the user brings it with the rest of the mod.
MODS = [
    "d64r-lostsoul-rt.pk3", "d64r-rt-flashlight.pk3",
    "d64r-3dfloor-rtfix.wad", "d64r-seqlight-fix.wad",
    "d64r-bulb-textures.wad", "d64r-ctel-fix.wad",
    "d64r-rt-sky.pk3", "d64r-lava-fx.pk3", "d64r-blood-persist.pk3",
    "d64r-widescreen-gfx.pk3", "d64r-mugshot.pk3", "d64r-rt-titlelogo.pk3",
]

DOCS = ["README.md", "CREDITS.md", "AI-DECLARATION.md", "DEVELOPERS.md"]


def copy_tree(src: Path, dst: Path, skip=None):
    n = 0
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        if skip and rel.parts and rel.parts[0] in skip:
            dirs[:] = []
            continue
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(Path(root) / f, dst / rel / f)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist", help="output folder")
    ap.add_argument("--build", default=str(BUILD), help="finished build tree")
    ap.add_argument("--zip", action="store_true", help="also write a .zip")
    ap.add_argument("--name", default="Doom64-RT", help="package folder name")
    args = ap.parse_args()

    build = Path(args.build)
    if not (build / "gzdoom.exe").exists():
        sys.exit("no gzdoom.exe in %s - build the engine first" % build)
    if not (build / "rt" / "bin" / "RTGL1.dll").exists():
        sys.exit("no rt/bin/RTGL1.dll in %s - build RTGL1 first" % build)

    out = Path(args.out).resolve() / args.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # --- engine ------------------------------------------------------------
    for f in ENGINE_FILES:
        p = build / f
        if p.exists():
            shutil.copy2(p, out / f)
        elif f in ("gzdoom.exe", "gzdoom.pk3"):
            sys.exit("missing required engine file: " + f)

    # --- rt/ ---------------------------------------------------------------
    for d, why in RT_KEEP_DIRS.items():
        src = build / "rt" / d
        if not src.exists():
            print("  ! rt/%-9s missing (%s)" % (d, why))
            continue
        skip = RT_WAD_DROP if d == "wad" else None
        n = copy_tree(src, out / "rt" / d, skip=skip)
        print("  rt/%-9s %5d files   %s" % (d, n, why))
    for f in (build / "rt").glob("*.json"):
        shutil.copy2(f, out / "rt" / f.name)

    # a package must never ship developerMode off: without it every authored
    # PNG material is ignored and the game quietly looks stock.
    (out / "rt" / "RTGL1.json").write_text(
        '{\n  "version": 0,\n  "developerMode": true,\n  "vulkanValidation": false,\n'
        '  "dx12Validation": false,\n  "dlssValidation": false,\n  "fpsMonitor": false\n}\n',
        encoding="ascii")

    # --- our mods ----------------------------------------------------------
    mods = out / "mods"
    mods.mkdir()
    src_mods = PROJ_ROOT / "Doom64-Retribution"
    count = 0
    for name in MODS:
        p = src_mods / name
        if not p.exists():
            sys.exit("missing mod file the launcher requires: " + name)
        shutil.copy2(p, mods / name)
        count += 1
    shutil.copy2(PROJ_ROOT / "tools" / "d64rt-pins.cfg", mods / "d64rt-pins.cfg")
    print("  mods/       %5d files" % (count + 1))

    # --- launcher + docs ---------------------------------------------------
    for f in ["launch-doom64-rt.cmd", "launch-doom64-rt-ui.ps1"]:
        shutil.copy2(PROJ_ROOT / f, out / f)
    banner = PROJ_ROOT / "docs" / "img" / "doom64rt-banner.png"
    if banner.exists():
        shutil.copy2(banner, out / "launcher-banner.png")
    for d in DOCS:
        if (PROJ_ROOT / d).exists():
            shutil.copy2(PROJ_ROOT / d, out / d)
    lic = PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "LICENSE"
    if lic.exists():
        shutil.copy2(lic, out / "LICENSE-gzdoom-GPLv3.txt")
    lic = PROJ_ROOT / "deps" / "RTGL" / "LICENSE"
    if lic.exists():
        shutil.copy2(lic, out / "LICENSE-RTGL1-MIT.txt")

    # --- the folder the user fills ----------------------------------------
    game = out / "game"
    game.mkdir()
    (game / "PUT-YOUR-GAME-FILES-HERE.txt").write_text(
        "Doom 64 - Ray Traced needs four files that are not ours to ship.\n"
        "Drop them in this folder, then run launch-doom64-rt.cmd:\n\n"
        "  doom2.wad               a DOOM II you own (Steam or GOG).\n"
        "                          The launcher finds Steam and GOG installs by\n"
        "                          itself, so you may not need to copy it here.\n"
        "  D64RTR_v15.WAD          Doom 64: Retribution v1.5, free:\n"
        "                          https://www.moddb.com/mods/doom-64-retribution\n"
        "  D64MUS.PK3              the OGG music pack (D64MUS.ZIP), same page:\n"
        "                          .../addons/doom-64-retribution-ogg-music-pack-v13\n"
        "  DOOMSND.SF2             optional, ships with Retribution. Without it\n"
        "                          the few MIDI tracks stay silent.\n",
        encoding="ascii")

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    files = sum(1 for f in out.rglob("*") if f.is_file())
    print("\npackage: %s\n  %d files, %.0f MB" % (out, files, total / 1e6))

    if args.zip:
        zpath = out.parent / (args.name + ".zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for f in sorted(out.rglob("*")):
                if f.is_file():
                    z.write(f, Path(args.name) / f.relative_to(out))
        print("  zip: %s  %.0f MB" % (zpath, zpath.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
