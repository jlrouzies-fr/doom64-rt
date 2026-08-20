"""Adapt the existing Retribution mugshot HUD package for Unseen Evil.

The layout is not recreated here.  Doom64-Retribution/d64r-mugshot.pk3 remains
the single SBARINFO source and is copied wholesale.  This builder adds only the
resources that Retribution normally supplies through D64RTR_v15.WAD (HUD label
glyphs, key icons, and the IsPlaying inventory token).

Usage:
    py -3 tools/make_unseenevil_hud.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
MUGSHOT = ROOT / "Doom64-Retribution" / "d64r-mugshot.pk3"
WAD = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-retribution-hud.pk3"

FONT_GLYPHS = {
    "D64HF065", "D64HF069", "D64HF072", "D64HF076",
    "D64HF077", "D64HF079", "D64HF082", "D64HF084",
}
KEY_ICONS = {f"STKEYS{i}" for i in range(6)}

ZSCRIPT = r'''version "4.12"

// Retribution gives this token as a Player.StartItem and its SBARINFO uses it
// to suppress the HUD outside play.  UE has a different player class, so give
// the same token from an additive handler instead of replacing that class.
class IsPlaying : Inventory
{
    Default { Inventory.MaxAmount 1; }
}

// Retribution's automap-only SBARINFO block references these three tokens.
// UE does not implement the Retribution Unmaker-upgrade inventory, but SBARINFO
// validates every referenced type even when the player never owns it.  Empty
// compatibility tokens preserve the unchanged HUD definition; because UE never
// receives them, its automap does not draw Retribution's ART1/2/3 icons.
class UnmakerUpgrade1Icon : Inventory {}
class UnmakerUpgrade2Icon : Inventory {}
class UnmakerUpgrade3Icon : Inventory {}

class D64UE_RT_RetributionHudToken : EventHandler
{
    override void WorldTick()
    {
        for (int i = 0; i < MAXPLAYERS; i++)
        {
            if (!playeringame[i] || !players[i].mo) continue;
            if (!players[i].mo.FindInventory("IsPlaying"))
                players[i].mo.GiveInventory("IsPlaying", 1);
        }
    }
}
'''

MAPINFO = '''gameinfo
{
    AddEventHandlers = "D64UE_RT_RetributionHudToken"
}
'''


def wad_resources() -> dict[str, bytes]:
    # Reuse the project's established WAD reader; do not duplicate a parser.
    sys.path.insert(0, str(ROOT / "tools"))
    from make_map_3dfloor_rtfix import read_wad_lumps

    wanted = FONT_GLYPHS | KEY_ICONS
    found = {name: data for name, data in read_wad_lumps(WAD) if name in wanted}
    missing = sorted(wanted - found.keys())
    if missing:
        raise SystemExit(f"missing Retribution HUD resource(s): {', '.join(missing)}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if not MUGSHOT.exists():
        raise SystemExit(f"missing {MUGSHOT}")
    resources = wad_resources()
    print("HUD source: d64r-mugshot.pk3 SBARINFO/TEXTURES/FONTDEFS/mugface (unchanged)")
    print(f"compat resources: {len(FONT_GLYPHS)} label glyphs, {len(KEY_ICONS)} key icons, IsPlaying token")
    if not args.write:
        print(f"census only; pass --write to build {OUT.name}")
        return

    with ZipFile(MUGSHOT) as source, ZipFile(OUT, "w", compression=ZIP_DEFLATED) as out:
        for info in source.infolist():
            if info.is_dir():
                continue
            out.writestr(info.filename, source.read(info.filename))
        for name, data in sorted(resources.items()):
            out.writestr(f"graphics/{name}.png", data)
        out.writestr("ZSCRIPT", ZSCRIPT)
        out.writestr("MAPINFO", MAPINFO)

    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
