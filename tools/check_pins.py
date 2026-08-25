"""Fail loudly when a launcher pin disagrees with its compiled default.

WHY THIS EXISTS. tools/d64rt-pins.cfg is exec'd before the map, so a pin
OVERRIDES the compiled default. Change one without the other and the game keeps
running the old value while the source says otherwise -- there is no warning, no
log line, and nothing on screen to notice.

That has already cost this project a full round: commit 0503ebc lowered the
rocket-smoke defaults and left d64rt-pins.cfg holding the pre-reduction numbers,
so "far less rocket smoke" was true of the source and false of the game, and the
next session re-derived the whole thing from scratch. This check is the cheap
version of that hour.

It also flags two quieter mistakes:

  ORPHAN PINS   -- a pin naming a cvar that no longer exists. The engine prints
                   "Unknown command" during startup, buried in hundreds of lines
                   nobody reads, and the pin silently does nothing forever.

  PINNED PRESET -- a pin naming a cvar that Options -> Quality owns through
                   rt_quality_preset (rt_quality.cpp). Pins run at launch and
                   override anything a preset set, so such a pin silently undoes
                   the player's choice on every start. ALWAYS an error.

  PINNED NOARCH -- RT_CVAR_NOARCH cvars are deliberately not archived: they are
                   diagnostics (rt_smoke_debug, rt_autoshot, rt_autofire) that
                   should be passed on the command line for one run, never
                   baked into the play launcher. A pinned one is on for
                   everybody, every session.

  UNPINNED WRITE -- an ARCHIVED cvar that ENGINE CODE assigns at runtime and
                   this file does not restate. That combination means the
                   engine's own value gets archived into gzdoom-rt2.ini on quit
                   and nothing ever puts it back, so the player's LAST SESSION
                   silently becomes the configuration of every session after it.
                   ALWAYS an error.

                   This is what rt_clouds_volumetric was. rt_firesky.cpp writes
                   it true on the five hell maps; quitting there archived a 1
                   that no pin reset, so whether a player got the ray-marched
                   clouds or the painted shell deck on MAP12 came down to
                   whether they had ever visited MAP23 -- same build, same
                   launcher, two different renderers. It took a viewer's video
                   of v0.1.15 to spot, and neither this checker nor the CI pin
                   gate could see it. Fix by pinning the cvar to its compiled
                   default, or by adding it to RUNTIME_WRITE_OK below with a
                   reason if it is genuinely per-frame or player-owned.

WHAT IS AND IS NOT AN ERROR. A pin differing from its default is usually
CORRECT -- that is what the launcher is for (rt_sun_intensity 90 against a
compiled 1000, rt_upscale_dlss 2 against 0). So a bare run REPORTS differences
and exits 0.

Give it a PREFIX and differences become errors. That is for families kept in
deliberate lockstep, where the pin exists to restate the default rather than to
override it -- rt_smoke_* is maintained that way precisely because of the rocket
episode above.

Orphan pins are ALWAYS an error: a pin naming a cvar that does not exist cannot
be intentional.

Usage:
    python tools/check_pins.py            # survey; exits 0 unless a pin is orphaned
    python tools/check_pins.py rt_smoke   # lockstep check for one family; exits 1 on any drift
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
# BOTH sources: rt_cvars.inc is the X-macro list, but a few cvars are declared
# directly in rt_cvars.cpp (rt_mod_compat is one). Parsing only the .inc reports
# those as orphaned pins, which is a false alarm -- and a checker that cries wolf
# is a checker nobody runs.
INC = ROOT / r"sourcecode\gzdoom-rt\src\common\rendering\rt\rt_cvars.inc"
INC_CPP = ROOT / r"sourcecode\gzdoom-rt\src\common\rendering\rt\rt_cvars.cpp"
PINS = ROOT / r"tools\d64rt-pins.cfg"
# THIRD source: not every rt_* cvar is an engine cvar. The gore family
# (rt_gore_life, rt_gore_burst*) is declared in a CVARINFO lump inside
# d64r-blood-persist.pk3, because the feature it belongs to is a pk3 -- and the
# launcher pins those the same way it pins engine ones. Without this the checker
# calls all nine of them orphans and exits 1 on a healthy tree, which is the
# crying-wolf failure the comment above is about.
PK3_DIR = ROOT / "Doom64-Retribution"

# Where the engine assigns cvars back. rt_cvars.cpp is excluded on purpose --
# it is the declaration site, not a writer. hw_skyportal.cpp is in here because
# the cloud deck lives outside the rt/ directory and is exactly the file the
# rt_clouds_volumetric episode ran through.
WRITE_DIRS = [ROOT / "sourcecode/gzdoom-rt/src/common/rendering/rt"]
WRITE_FILES = [ROOT / "sourcecode/gzdoom-rt/src/rendering/hwrenderer/scene/hw_skyportal.cpp"]
WRITE_SKIP = {"rt_cvars.cpp"}

# `cvar::name =` but not `cvar::name ==`.
WRITE = re.compile(r"cvar::(?P<name>rt_\w+)\s*=(?!=)")

# Archived cvars the engine writes on purpose, where an archived copy cannot
# decide anything. Each needs a reason, because the default answer is "pin it".
RUNTIME_WRITE_OK = {
    # Re-derived from playsim or hardware state every frame, so a stale ini
    # value is overwritten before the first tic is drawn.
    "rt_flsh_charge": "flashlight battery level, rewritten every frame",
    "rt_flsh_battstate": "flashlight battery state, rewritten every frame",
    "rt_flsh_flicker": "flashlight flicker phase, rewritten every frame",
    "rt_pw_lightamp": "light-amp powerup, rewritten every frame from the player",
    # Player-owned settings that the first-start GPU probe seeds ONCE
    # (rt_main.cpp, RT_Init). A pin would overwrite the player's choice on every
    # later launch -- the same mistake rt_quality.cpp's header describes.
    "rt_vsync": "player setting; first-start probe seeds it once",
    "rt_ef_vintage": "player setting; first-start probe seeds it once",
    "rt_remix_taa": "player setting; first-start probe seeds it once",
}

# The X-macro list. Every entry is RT_CVAR( name, default, "help" ) or one of the
# NOARCH / COLOR / STRING variants, and the default may be 12, 12.f, true, or
# 0xRRGGBB.
DECL = re.compile(
    r"RT_CVAR(?P<kind>_NOARCH|_COLOR|_STRING)?\(\s*(?P<name>\w+),\s*(?P<value>[^,]+?),"
)


# A CVARINFO declaration: [server|user] [noarchive] <type> <name> = <value>;
CVARINFO_DECL = re.compile(
    r"^\s*(?:server|user)\s+(?P<noarch>noarchive\s+)?"
    r"(?:int|float|bool|color|string)\s+(?P<name>\w+)\s*=\s*(?P<value>[^;]+);",
    re.M,
)


def parse_pk3_defaults() -> dict[str, tuple[str, str]]:
    """Cvars declared by a loaded pk3's CVARINFO rather than by the engine."""
    out: dict[str, tuple[str, str]] = {}
    for pk3 in sorted(PK3_DIR.glob("*.pk3")):
        try:
            with zipfile.ZipFile(pk3) as z:
                names = [n for n in z.namelist() if Path(n).name.upper() == "CVARINFO"]
                for n in names:
                    text = z.read(n).decode("utf-8", errors="replace")
                    for m in CVARINFO_DECL.finditer(text):
                        out[m.group("name")] = (
                            m.group("value").strip(),
                            "_NOARCH" if m.group("noarch") else "",
                        )
        except (zipfile.BadZipFile, OSError):
            # A pk3 locked by a running game, or not a zip at all. Skipping is
            # right: this source only ever ADDS known names.
            continue
    return out


def parse_defaults() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for src in (INC, INC_CPP):
        if not src.exists():
            continue
        for m in DECL.finditer(src.read_text(encoding="utf-8", errors="replace")):
            out[m.group("name")] = (m.group("value").strip(), m.group("kind") or "")
    # Engine declarations win on a name collision -- if both ever declare the
    # same cvar, the engine's is the one the pin is really talking to.
    for name, decl in parse_pk3_defaults().items():
        out.setdefault(name, decl)
    return out


def parse_runtime_writes() -> set[str]:
    """Cvars the ENGINE assigns back at runtime, `cvar::name = ...`.

    Deliberately a text scan and not a real parse: a false positive here costs
    one allowlist line with a reason on it, and a false negative costs what
    rt_clouds_volumetric cost.
    """
    srcs = list(WRITE_FILES)
    for d in WRITE_DIRS:
        if d.exists():
            srcs += [f for f in sorted(d.glob("*.cpp")) if f.name not in WRITE_SKIP]
    out: set[str] = set()
    for f in srcs:
        if not f.exists():
            continue
        for m in WRITE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            out.add(m.group("name"))
    return out


def parse_pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in PINS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        parts = line.split()
        # Bare commands (god, notarget) have no value and are not cvars.
        if len(parts) == 2:
            out[parts[0]] = parts[1]
    return out


def same(default: str, pinned: str) -> bool:
    """Numeric where possible, so 12 / 12.f / 12.0 do not false-positive, and
    hex colours compare case- and 0x-insensitively."""
    d = default.rstrip("f").replace("true", "1").replace("false", "0")
    p = pinned.replace("true", "1").replace("false", "0")
    try:
        return abs(float(d) - float(p)) < 1e-9
    except ValueError:
        return d.lower().lstrip("0x") == p.lower().lstrip("0x")


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    defaults, pins = parse_defaults(), parse_pins()

    disagree, orphan, noarch = [], [], []
    for name, pinned in sorted(pins.items()):
        if prefix and not name.startswith(prefix):
            continue
        if name not in defaults:
            # Only report names that look like ours; the pins file also carries
            # stock GZDoom cvars (vid_fullscreen, sv_cheats) we do not declare.
            if name.startswith("rt_"):
                orphan.append(name)
            continue
        value, kind = defaults[name]
        agrees = same(value, pinned)
        # A NOARCH cvar pinned to its own default is FINE and usually deliberate:
        # the play launcher stating "this diagnostic is off" so no stray ini or
        # arm can leave it on. Only a NOARCH pinned to something OTHER than its
        # default is a problem -- that is a diagnostic turned on for everybody,
        # every session, which is what this is meant to catch.
        if kind == "_NOARCH" and not agrees:
            noarch.append((name, value, pinned))
        elif not agrees:
            disagree.append((name, value, pinned))

    # Owned by Options -> Quality via rt_quality_preset. Parsed straight out of
    # the preset table so the two can never drift: a cvar added to the preset is
    # guarded here the moment it is added, with nothing to remember.
    owned = set()
    try:
        q = (ROOT / "sourcecode" / "gzdoom-rt" / "src" / "common" / "rendering"
             / "rt" / "rt_quality.cpp").read_text(encoding="utf-8", errors="replace")
        table = q[q.index("g_quality[] = {"):]
        table = table[:table.index("};")]
        owned = set(re.findall(r'\{\s*"([A-Za-z_][A-Za-z0-9_]*)"', table))
    except Exception:
        # No engine tree (sourcecode/ is gitignored, so a docs-only checkout has
        # none). Silence beats a false pass here: say the guard did not run.
        print("check_pins: NOTE -- rt_quality.cpp not found, preset guard skipped")

    preset_pinned = sorted(n for n in pins if n in owned)

    # ARCHIVED, WRITTEN BY THE ENGINE, NOT PINNED -- the class that cost the
    # v0.1.15 cloud path. Skipped under a prefix run: that mode is a lockstep
    # check on one family, not a survey of the tree.
    written_unpinned = []
    if not prefix:
        for name in sorted(parse_runtime_writes()):
            if name in pins or name in RUNTIME_WRITE_OK:
                continue
            # Not declared by RT_CVAR at all -- the capability flags
            # (rt_available_*, rt_hdr_available) are plain CVARs elsewhere and
            # are pure hardware readback, never a configuration.
            if name not in defaults:
                continue
            # NOARCH is the other valid fix: the engine can still write it, but
            # nothing archives it, so it cannot come BACK from a later session.
            if defaults[name][1] == "_NOARCH":
                continue
            written_unpinned.append(name)


    if not (disagree or orphan or noarch or preset_pinned or written_unpinned):
        n = sum(1 for k in pins if not prefix or k.startswith(prefix))
        print(f"check_pins: OK -- {n} pins agree with their compiled defaults")
        return 0

    print("=" * 72)
    if prefix:
        print(f"PIN / DEFAULT DRIFT in {prefix}* -- the game uses the PIN, not the source.")
    else:
        print("PIN SURVEY -- differences below are usually INTENTIONAL (that is what")
        print("the launcher is for). Only orphaned pins are errors in this mode.")
    print("=" * 72)
    for name, value, pinned in disagree:
        print(f"   {name:32} default={value:<12} pinned={pinned}")
    for name in orphan:
        print(f"   {name:32} PINNED BUT NO SUCH CVAR (silently does nothing)")
    for name in preset_pinned:
        print(f"   {name:32} PINNED BUT OWNED BY rt_quality_preset"
              f" -- the pin wins at launch and the Quality menu does nothing")
    for name, value, pinned in noarch:
        print(f"   {name:32} NOARCH pinned ON: default={value} pinned={pinned}"
              f" -- a diagnostic left on for every session")
    for name in written_unpinned:
        print(f"   {name:32} ARCHIVED, WRITTEN AT RUNTIME, NOT PINNED"
              f" -- last session becomes the configuration")
    print()
    if prefix or orphan:
        print("Fix BOTH halves: the RT_CVAR default in rt_cvars.inc and the line in")
        print("tools/d64rt-pins.cfg. Changing only one is the failure this exists for.")
    # Orphans are always broken. Bare-run value differences are the launcher
    # doing its job, so they do not fail the build.
    if preset_pinned:
        print("Remove those lines from tools/d64rt-pins.cfg. The preset's High level")
        print("restates every shipped value, so nothing is lost by unpinning them.")
    if written_unpinned:
        print("Each of those is archived into gzdoom-rt2.ini on quit and never put")
        print("back, so whatever the engine last wrote decides every later session.")
        print("Pin it to its compiled default in tools/d64rt-pins.cfg, or make it")
        print("RT_CVAR_NOARCH, or add it to RUNTIME_WRITE_OK with a reason.")
    return 1 if (orphan or preset_pinned or written_unpinned or (prefix and disagree)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
