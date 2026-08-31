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
# The keep-list above is what actually decides the package, so these are dropped
# by omission. Listed for the record -- and if this project ever ships its own
# rt/replace models, "replace" has to move up into RT_KEEP_DIRS.
RT_DROP_DIRS = {
    "replace":            "1.9 GB of Doom II glTF model replacements (the stock name)",
    "replace_old":        "the same folder, renamed locally to switch it off",
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
#
# KEEP THIS IN STEP WITH launch-doom64-rt.cmd. check_mods_match_launcher()
# below enforces it, and that check exists because three files went missing
# from releases without a word: d64r-liquid-art.wad (the blood/poison/sludge
# art -- the game silently fell back to Retribution's stock flats) and the two
# d64r-smonf-*.wad. This list lives in three hand-maintained copies (here, the
# shipped launcher, and tools/launch-retribution-rt.cmd) and nothing compared
# them.
MODS = [
    "d64r-lostsoul-rt.pk3", "d64r-rt-flashlight.pk3",
    "d64r-seqlight-fix.wad",
    "d64r-bulb-textures.wad", "d64r-sflatas-broken.wad", "d64r-ctel-fix.wad",
    "d64r-liquid-art.wad",
    "d64r-smonf-blink.wad", "d64r-smonf-lights.wad",
    "d64r-rt-sky.pk3", "d64r-lava-fx.pk3", "d64r-poison-fx.pk3",
    "d64r-blood-persist.pk3",
    "d64r-widescreen-gfx.pk3", "d64r-mugshot.pk3", "d64r-rt-titlelogo.pk3",
    # Copied always, loaded only when the classic-recolour add-on is ticked --
    # the launcher hangs it off RECOLORARGS. Packaged unconditionally because a
    # player can tick that box at any later start.
    "d64r-caco-ball-recolor.pk3",
]

# NAMED BY THE LAUNCHER, PACKAGED ONLY IF PRESENT -- and on a clean CI checkout
# it is not, deliberately.
#
# d64r-ue-monsters.pk3 is BUILT from Doom64: Unseen Evil's sprites, and both the
# built pk3 and the whole Doom64-UnseenEvil/ source folder are gitignored: those
# sprites are DrPyspy's, Unseen Evil ships no licence statement, and CREDITS.md
# records the decision -- credited local add-on, ask before redistributing. A
# GitHub release zip is redistribution, to the public, permanently. So this file
# is absent from every CI build ON PURPOSE and its absence must not fail the
# release; it was in MODS, which hard-exits on a missing file, and that is what
# broke the v0.1.19 build.
#
# A local package built on a machine that has the pk3 picks it up and ships it,
# which is the intended way to hand someone a build with the monsters in it.
OPTIONAL_MODS = [
    "d64r-ue-monsters.pk3",
]

DOCS = ["README.md", "CREDITS.md", "AI-DECLARATION.md", "DEVELOPERS.md"]


def check_mods_match_launcher() -> None:
    """MODS must be exactly what launch-doom64-rt.cmd passes to -file.

    A file that is packaged but never loaded is dead weight; a file the
    launcher names but nobody packages is a missing feature that looks like a
    bug in the feature itself. The second is what happened to the liquid art:
    the release shipped its material overlays AND its textures.json tags, so
    everything looked wired, and only the wad carrying the art was absent.
    """
    text = (PROJ_ROOT / "launch-doom64-rt.cmd").read_text(
        encoding="utf-8", errors="ignore")
    marker = "%MODS%" + chr(92)
    named = set()
    for piece in text.split(marker)[1:]:
        name = piece.split('"')[0].strip()
        if name.lower().endswith((".wad", ".pk3")):
            named.add(name)

    listed = set(MODS) | set(OPTIONAL_MODS)
    missing = sorted(named - listed)
    extra = sorted(listed - named)
    if missing or extra:
        lines = ["MODS and launch-doom64-rt.cmd disagree:"]
        lines += ["  launcher loads it, MODS does not copy it: " + m for m in missing]
        lines += ["  MODS copies it, launcher never loads it: " + e for e in extra]
        lines.append("Fix both lists, then run again.")
        raise SystemExit(chr(10).join(lines))


# The liquid families whose look IS an authored relief map. Blood and sludge get
# their still, ridged surface only because rt_blood_relief / rt_sludge_relief mix
# the global animated water wave out in favour of the _n -- and that mix has
# nothing to give back if the maps did not ship. 64 frames each, both halves of
# each ANIMDEFS sequence.
RELIEF_FAMILIES = ["D64B1_", "D64B2_", "D64S1_", "D64S2_"]
RELIEF_FRAMES = 64
RELIEF_SUFFIXES = ["_n", "_h", "_orm"]

# The cvar families that carry the liquid look. Pinned as a restatement of their
# compiled defaults, so any difference is drift, not an override.
LIQUID_PIN_PREFIXES = ["rt_water", "rt_blood", "rt_sludge", "rt_nukage", "rt_liquid"]


def check_liquid_relief(build: Path) -> None:
    """The blood and sludge relief maps must be in the tree we are about to ship.

    They reach a release through exactly ONE path -- rt/mat_dev, because the
    packager drops rt/mat and RTGL1.json ships developerMode: true -- so this is
    the single place the art can vanish without a word.

    It matters more than a missing texture usually would. The animated water wave
    is GLOBAL: getNormal() applies it to every water-flagged primitive, and the
    per-liquid relief mix is the only thing that takes it off a blood or sludge
    bed. Ship the pins without the maps and the relief has nothing to mix in --
    the surface is wrong, nothing errors, and the report comes back as "the water
    wave is on the blood", pointing at the renderer rather than the package.
    """
    mat = build / "rt" / "mat_dev"
    if not mat.exists():
        sys.exit("no rt/mat_dev in %s - nothing to check, and nothing to ship" % build)

    bad = []
    for fam in RELIEF_FAMILIES:
        for suf in RELIEF_SUFFIXES:
            n = len(list(mat.glob(fam + "*" + suf + ".png")))
            if n != RELIEF_FRAMES:
                bad.append("  %s*%s.png : %d, expected %d" % (fam, suf, n, RELIEF_FRAMES))
    if bad:
        lines = ["rt/mat_dev is missing liquid relief maps:"]
        lines += bad
        lines.append("Regenerate with tools/gen_liquid_art.py and rebuild, or the")
        lines.append("release ships blood and sludge wearing the animated water wave.")
        raise SystemExit(chr(10).join(lines))


def check_pins_lockstep() -> None:
    """The liquid pins must agree with the compiled defaults, and must exist.

    Two failures this catches, both silent in play:

      DRIFT   -- a pin and its RT_CVAR default disagree. The game uses the pin,
                 the source says otherwise, and the next session re-derives the
                 whole thing. That is the rocket-smoke episode check_pins.py was
                 written for; the liquid family is now maintained the same way.

      ORPHAN  -- a pin naming a cvar the shipped engine does not have, which is
                 what a release built from a stale exe produces. GZDoom prints
                 one "Unknown command" into hundreds of boot lines, the pin does
                 nothing, and the uniform keeps whatever RTGL1 left in it.
    """
    sys.path.insert(0, str(PROJ_ROOT / "tools"))
    try:
        import check_pins
    finally:
        sys.path.pop(0)

    defaults, pins = check_pins.parse_defaults(), check_pins.parse_pins()
    drift, orphan = [], []
    seen = 0
    for name, pinned in sorted(pins.items()):
        if not any(name.startswith(p) for p in LIQUID_PIN_PREFIXES):
            continue
        seen += 1
        if name not in defaults:
            orphan.append(name)
            continue
        value, _kind = defaults[name]
        if not check_pins.same(value, pinned):
            drift.append("  %-28s default=%-10s pinned=%s" % (name, value, pinned))

    if not seen:
        raise SystemExit(
            "d64rt-pins.cfg has no liquid pins at all - the shipped look would be "
            "whatever the player's gzdoom-rt2.ini happens to say")

    if drift or orphan:
        lines = ["the liquid pins disagree with the engine:"]
        lines += drift
        lines += ["  %-28s PINNED BUT NO SUCH CVAR (silently does nothing)" % n
                  for n in orphan]
        lines.append("Fix rt_cvars.inc and tools/d64rt-pins.cfg together, then rebuild.")
        raise SystemExit(chr(10).join(lines))


def check_engine_fresh(build: Path) -> None:
    """Refuse to package a binary older than the source it is built from.

    A stale exe is the quietest way to ship a broken feature: every pin naming a
    cvar it predates becomes an orphan, the matching uniform reads whatever was
    left in it, and both the pins file and the source read correctly the whole
    time. Costs one rebuild to fix and a bug report to find.

    Each binary is checked against ITS OWN source tree. Comparing both against
    both flags RTGL1.dll every time an engine .cpp is touched, and a check that
    cries wolf is a check nobody runs.
    """
    pairs = [
        ("gzdoom.exe",
         PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "src" / "common" / "rendering" / "rt",
         "tools/build-gzdoom-rt.cmd"),
        ("rt/bin/RTGL1.dll",
         PROJ_ROOT / "deps" / "RTGL" / "Source",
         "tools/build-rtgl.cmd"),
    ]
    exts = (".cpp", ".h", ".inc", ".inl", ".hpp")

    stale = []
    for rel, src, how in pairs:
        binary = build / rel
        # deps/ is gitignored, so a docs-only checkout has no RTGL source to
        # compare against. Nothing to say in that case.
        if not binary.exists() or not src.exists():
            continue
        newest, newest_file = 0.0, None
        for root, dirs, files in os.walk(src):
            # Source/Generated/*.h are build OUTPUTS -- the header generator
            # runs after the link, so they are always newer than the DLL and
            # comparing against them fails every single time.
            dirs[:] = [d for d in dirs if d != "Generated"]
            for f in files:
                if f.lower().endswith(exts):
                    t = os.path.getmtime(os.path.join(root, f))
                    if t > newest:
                        newest, newest_file = t, os.path.join(root, f)
        if newest_file and os.path.getmtime(binary) < newest:
            stale.append("  %s is older than %s%s     rebuild with %s"
                         % (rel, newest_file, chr(10), how))
    if stale:
        lines = ["the build tree is older than the source it came from:"]
        lines += stale
        lines.append("A stale engine turns new pins into orphans -- the pin is "
                     "read, the cvar does not exist, and nothing says so.")
        raise SystemExit(chr(10).join(lines))


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

    # Before anything is copied: a mismatch here is a silently incomplete
    # release, and the whole point is to find it now rather than in play.
    check_mods_match_launcher()
    check_pins_lockstep()
    check_engine_fresh(Path(args.build))
    check_liquid_relief(Path(args.build))

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
    # Loose files at the root of rt/. Not optional: BlueNoise_LDR_RGBA_128.ktx2,
    # DirtMask.ktx2, SceneBuildWarning.ktx2 and WaterNormal_n.ktx2 are renderer
    # inputs, and the renderer aborts with "Can't find blue noise file" without
    # the first. Copying only *.json here is what shipped a broken v0.1.1.
    RT_ROOT_SKIP = {
        "devmode_settings.json",  # this machine's Dev window layout
        "imgui.ini",              # ditto
        "RTGL1.json",             # rewritten below with developerMode on
    }
    for f in (build / "rt").iterdir():
        if f.is_file() and f.name not in RT_ROOT_SKIP:
            shutil.copy2(f, out / "rt" / f.name)

    # A package must never ship developerMode off: the main material path uses
    # RTGL1's OnlyKTX2LoaderIfNonDevMode(), which outside devmode is KTX2-ONLY,
    # so every authored PNG material is ignored and the game quietly looks stock.
    #
    # developerMode also used to open the ImGui debug window, which a player must
    # never see. RTGL1 now takes a separate "debugWindows" flag, so the loader and
    # the window can be asked for independently -- this writes the one combination
    # a release wants: materials yes, window no.
    (out / "rt" / "RTGL1.json").write_text(
        '{\n  "version": 0,\n  "developerMode": true,\n  "debugWindows": false,\n'
        '  "vulkanValidation": false,\n'
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
    for name in OPTIONAL_MODS:
        p = src_mods / name
        if p.exists():
            shutil.copy2(p, mods / name)
            count += 1
        else:
            print(f"  NOT PACKAGED  {name} -- see OPTIONAL_MODS. This is expected on CI.")
    # THE PINS ARE A DEVELOPMENT FILE AND MUST BE FILTERED, NOT COPIED.
    # d64rt-pins.cfg is written for launch-retribution-rt.cmd -- the tester's
    # launcher -- and its head carries `sv_cheats 1`, `god` and `notarget`, plus
    # a windowed/no-prompt video block. The release launcher execs the same file,
    # so a straight copy shipped every player an invulnerable game that monsters
    # ignore, and reasserted the window size over whatever they chose in the
    # menus. Strip the marked block instead.
    pins_src = (PROJ_ROOT / "tools" / "d64rt-pins.cfg").read_text(encoding="utf-8")
    kept, dropped, skipping = [], 0, False
    for line in pins_src.splitlines(keepends=True):
        if ">>> DEV-ONLY <<<" in line:
            skipping = True
        if skipping:
            dropped += 1
            if ">>> END-DEV-ONLY <<<" in line:
                skipping = False
            continue
        kept.append(line)
    if skipping:
        sys.exit("d64rt-pins.cfg: DEV-ONLY block is never closed - refusing to ship it")
    if dropped == 0:
        sys.exit("d64rt-pins.cfg: no DEV-ONLY block found - the cheat pins would ship")
    (mods / "d64rt-pins.cfg").write_text("".join(kept), encoding="utf-8")
    print("  pins        stripped %d dev-only line(s)" % dropped)
    print("  mods/       %5d files" % (count + 1))

    # --- launcher + docs ---------------------------------------------------
    # launch-doom64-rt-checks.ps1 is dot-sourced by the window: without it the
    # launcher throws before it can explain anything. The -classic window is the
    # fallback the .cmd runs if WPF will not start.
    for f in ["launch-doom64-rt.cmd", "launch-doom64-rt-ui.ps1",
              "launch-doom64-rt-ui-classic.ps1", "launch-doom64-rt-checks.ps1"]:
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
        "Doom 64 - Ray Traced ships the renderer, not the game. Put the game files\n"
        "in THIS folder, then run launch-doom64-rt.cmd one level up.\n"
        "\n"
        "1. Doom 64: Retribution v1.5   (free)\n"
        "     https://www.moddb.com/mods/doom-64-retribution\n"
        "\n"
        "   Extract the WHOLE download in here, not just the WAD. It contains\n"
        "   several files this needs and they are easy to miss one at a time:\n"
        "     D64RTR[v1.5].WAD        the mod itself\n"
        "     D64RTR_BRIGHTMAPS.PK3   every enemy eye and glowing panel is masked from it\n"
        "     DOOMSND.SF2             without it the few MIDI tracks stay silent\n"
        "     libfluidsynth*.dll      plays those MIDI tracks\n"
        "\n"
        "2. OGG music pack v1.3   (free, same ModDB page, file D64MUS.ZIP)\n"
        "     .../addons/doom-64-retribution-ogg-music-pack-v13\n"
        "   Unzip it here too - that gives you D64MUS.PK3.\n"
        "\n"
        "3. doom2.wad   -   a DOOM II you own, from Steam or GOG.\n"
        "   The launcher finds Steam and GOG installs by itself, so you probably\n"
        "   do not need to copy this at all. If yours lives somewhere unusual,\n"
        "   the startup check has a Browse button.\n"
        "\n"
        "The launcher checks all of this on startup and tells you what is missing,\n"
        "with a link to each download.\n",
        encoding="ascii")

    # Ships empty but present, because a folder that has to be created by hand
    # is a folder nobody creates: the startup window's add-on row says "put the
    # wad in the Addons folder", and it has to be there to be put into. The same
    # file the source checkout carries, so the two cannot drift apart.
    addons = out / "Addons"
    addons.mkdir()
    shutil.copy2(PROJ_ROOT / "Addons" / "PUT-YOUR-ADDONS-HERE.txt",
                 addons / "PUT-YOUR-ADDONS-HERE.txt")

    # The engine checks for these at startup (rt_main.cpp) and shows a "DLL check
    # failure" dialog naming whatever is absent. The stock package ships none of
    # the NVIDIA ones, so they have to arrive from the RTGL1 release bundle.
    engine_dlls = [
        "D3D12Core.dll", "nvngx_dlss.dll", "nvngx_dlssd.dll", "nvngx_dlssg.dll",
        "NvLowLatencyVk.dll", "sl.dlss.dll", "sl.dlss_g.dll", "sl.reflex.dll",
        "sl.pcl.dll", "sl.common.dll", "sl.interposer.dll",
        "ffx_fsr2_x64.dll", "ffx_fsr3_x64.dll", "ffx_fsr3upscaler_x64.dll",
        "ffx_frameinterpolation_x64.dll", "ffx_opticalflow_x64.dll",
        "ffx_backend_dx12_x64.dll", "ffx_backend_vk_x64.dll",
    ]
    for tex in ["BlueNoise_LDR_RGBA_128.ktx2", "DirtMask.ktx2",
                "SceneBuildWarning.ktx2", "WaterNormal_n.ktx2"]:
        if not (out / "rt" / tex).exists():
            sys.exit("rt/%s is missing - the renderer needs it at startup" % tex)

    lacking = [d for d in engine_dlls if not (out / "rt" / "bin" / d).exists()]
    if lacking:
        print("\n  ! rt/bin is missing %d DLL(s) the engine checks for:" % len(lacking))
        for d in lacking:
            print("      " + d)
        print("    The user gets a 'DLL check failure' dialog. Take them from")
        print("    https://github.com/vs-shirokii/RTGL/releases (rt/bin inside the zip).")

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
