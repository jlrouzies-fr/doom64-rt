"""Build the UE-only bridge into gzdoom-rt's existing RT options menu."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-rt-menu.pk3"
ZSCRIPT = b'''version "4.11.0"

// UE v1.0.3 builds Player, Gameplay, Aesthetics, and Music pages in this
// order. Remove the Player page by name, then recenter the surviving tabs.
// Subclassing is additive and avoids replacing a script included by UE's own
// archive, whose cross-archive lookup rules are not part of this contract.
class D64UE_RT_CustomizationMenu : D64UE_CustomizationMenu
{
    override void Init(Menu parent)
    {
        super.Init(parent);

        for (int i = 0; i < tabs.Size(); i++)
        {
            if (!(tabs[i].name ~== "Player")) continue;
            tabs.Delete(i);
            pages.Delete(i);
            break;
        }

        int tabsWidth = 0;
        for (int i = 0; i < tabs.Size(); i++)
            tabsWidth += tabs[i].width;

        int tabX = 160 - tabsWidth / 2;
        for (int i = 0; i < tabs.Size(); i++)
        {
            tabs[i].x = tabX;
            tabX += tabs[i].width;
        }

        menu_curPage = 0;
        UpdateControls();
    }
}
'''
MENUDEF = b'''// Loaded after D64UnseenEvil-v1.0.3.pk3. UE's ListMenu drawer
// deliberately paints TextItem.mText itself. That is fine for UE's ordinary
// labels, but bypasses TextItem_RT.Draw() and exposes raw RTMNU_* keys. Keep
// UE's drawer on its menus and give only this bridge page the stock drawer.
ListMenu "D64UE_RT_OptionsMenu"
{
    Class "ListMenu"
    StaticPatch -16, 10, "M_DISOPT"
    Position 45, 35
    Font "SmallFont"
    Selector "M_RTSLCT", 0, 0
    Linespacing 10

    TextItem_RT "RTMNU_WINDOW_RESOL"
    Linespacing 10
    TextItem_RT "RTMNU_DXGI"
    Linespacing 10
    TextItem_RT "RTMNU_VSYNC"
    Linespacing 14
    TextItem_RT "RTMNU_HDR"
    Linespacing 10
    TextItem_RT "RTMNU_MODE"
    Linespacing 10
    TextItem_RT "RTMNU_PRESET"
    Linespacing 14
    TextItem_RT "RTMNU_FRAMEGEN"
    Linespacing 10
    TextItem_RT "RTMNU_CLASSIC"
    Linespacing 10
    TextItem_RT "RTMNU_BLOOM"
    Linespacing 14
    TextItem_RT "Quality", "RT_QualityMenu"
    Linespacing 10
    TextItem_RT "Flashlight", "RT_FlashlightMenu"
    Linespacing 10
    TextItem_RT "RTMNU_HUD_SIZE"
    Linespacing 18
    TextItem_RT "HUD Opacity", "RT_HudMenu"
    TextItem_RT "Other", "OptionsMenu"
}

// Preserve UE's main-menu class and every UE-specific destination. Only route
// Options through the compact RT page; its Other entry reaches base GZDoom.
ListMenu "MainMenuTextOnly"
{
    Class "D64UE_Menu_MainMenu"
    Size 320, 240
    Position 108, 138
    TextItem "New Game", "n", "PlayerclassMenu"
    TextItem "Load Game", "l", "LoadGameMenu"
    TextItem "Save Game", "s", "SaveGameMenu"
    TextItem "Customization", "c", "D64UE_RT_CustomizationMenu"
    TextItem "Options", "o", "D64UE_RT_OptionsMenu"
    TextItem "Quit Game", "q", "QuitMenu"
}
'''


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("MENUDEF", MENUDEF)
        archive.writestr("ZSCRIPT", ZSCRIPT)
    with ZipFile(output) as archive:
        if archive.read("MENUDEF") != MENUDEF:
            raise SystemExit("generated UE RT MENUDEF differs from source")
        if archive.read("ZSCRIPT") != ZSCRIPT:
            raise SystemExit("generated UE RT menu ZScript differs from source")
    print("verified: RT Options bridge, Player tab removal, retained UE menu class")
    print(f"wrote {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the UE overlay")
    args = parser.parse_args()
    if not args.write:
        parser.error("pass --write to build the overlay")
    build(OUT)
