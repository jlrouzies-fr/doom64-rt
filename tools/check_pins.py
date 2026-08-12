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

  PINNED NOARCH -- RT_CVAR_NOARCH cvars are deliberately not archived: they are
                   diagnostics (rt_smoke_debug, rt_autoshot, rt_autofire) that
                   should be passed on the command line for one run, never
                   baked into the play launcher. A pinned one is on for
                   everybody, every session.

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
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
# BOTH sources: rt_cvars.inc is the X-macro list, but a few cvars are declared
# directly in rt_cvars.cpp (rt_mod_compat is one). Parsing only the .inc reports
# those as orphaned pins, which is a false alarm -- and a checker that cries wolf
# is a checker nobody runs.
INC = ROOT / r"sourcecode\gzdoom-rt\src\common\rendering\rt\rt_cvars.inc"
INC_CPP = ROOT / r"sourcecode\gzdoom-rt\src\common\rendering\rt\rt_cvars.cpp"
PINS = ROOT / r"tools\d64rt-pins.cfg"

# The X-macro list. Every entry is RT_CVAR( name, default, "help" ) or one of the
# NOARCH / COLOR / STRING variants, and the default may be 12, 12.f, true, or
# 0xRRGGBB.
DECL = re.compile(
    r"RT_CVAR(?P<kind>_NOARCH|_COLOR|_STRING)?\(\s*(?P<name>\w+),\s*(?P<value>[^,]+?),"
)


def parse_defaults() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for src in (INC, INC_CPP):
        if not src.exists():
            continue
        for m in DECL.finditer(src.read_text(encoding="utf-8", errors="replace")):
            out[m.group("name")] = (m.group("value").strip(), m.group("kind") or "")
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

    if not (disagree or orphan or noarch):
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
    for name, value, pinned in noarch:
        print(f"   {name:32} NOARCH pinned ON: default={value} pinned={pinned}"
              f" -- a diagnostic left on for every session")
    print()
    if prefix or orphan:
        print("Fix BOTH halves: the RT_CVAR default in rt_cvars.inc and the line in")
        print("tools/d64rt-pins.cfg. Changing only one is the failure this exists for.")
    # Orphans are always broken. Bare-run value differences are the launcher
    # doing its job, so they do not fail the build.
    return 1 if (orphan or (prefix and disagree)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
