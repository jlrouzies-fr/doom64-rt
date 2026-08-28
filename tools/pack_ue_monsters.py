"""Build d64r-ue-monsters.pk3 -- Unseen Evil's D64-style monsters for Retribution.

Retribution has no art for the Chaingunner, Revenant, Arch-Vile or Spider
Mastermind. It *declares* those classes, but only as scale tweaks on the stock
Doom 2 monsters ("ACTOR 64Revenant : Revenant REPLACES Revenant { Scale 1.2 }"),
so they render as Doom 2 sprites out of the IWAD and are never placed in any
Doom 64 map. Unseen Evil has real D64-style versions of all four, plus a redrawn
Shotgun Guy. This packs those assets, and only those assets, into an overlay
pk3; the actor code and the placement handler are authored in
tools/d64r-ue-monsters/ and are not copies of UE's.

THREE THINGS THAT WILL BITE, ALL OF THEM SILENT:

1. NEVER RE-ENCODE A SPRITE. Sprite PNGs carry a grAb chunk holding the Doom
   draw offset, and Pillow drops ancillary chunks. A sprite that loses grAb
   falls back to a zero offset and renders sunk into the floor. Everything here
   is a byte-for-byte zip-to-zip copy and _verify() asserts it stayed that way;
   there is no image library in this file on purpose. Same trap as
   tools/pack_lostsoul_rt.py.

2. MATCH LUMPS BY NAME, NOT BY EXTENSION. 30 of the Shotgun Guy's 78 frames are
   stored with no .png suffix -- "sprites/enemies/shotgunner/SPOSE1" is PNG data
   under a bare lump name, which GZDoom reads happily. A *.png glob drops every
   frame from E onward, i.e. the whole firing and death sequence, and the
   monster just freezes mid-animation with no error anywhere.

3. SPOS AND TRCR ARE NOT FREE. CPOS/SKEL/VILE/SPID/AVFR have zero lumps and zero
   RT material files in Retribution, so they drop in under their own names. SPOS
   and TRCR do not: they carry 98 and 34 baked _orm/_n files keyed on the bare
   name. Shipping UE's different art under those names would hand Retribution's
   materials to UE's pixels AND repaint Retribution's own Shotgun Guy and Mother
   Demon ball. They are renamed here, and the actors reference the new names.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[1]

UE_PK3 = PROJ_ROOT / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
SRC_DIR = PROJ_ROOT / "tools" / "d64r-ue-monsters"
OUT_PK3 = PROJ_ROOT / "Doom64-Retribution" / "d64r-ue-monsters.pk3"

# folder in the UE pk3 -> (sprite prefix there, prefix we ship it under)
SPRITE_SETS = [
    ("sprites/enemies/chaingunner/", "CPOS", "CPOS"),
    ("sprites/enemies/skeletoing/", "SKEL", "SKEL"),
    ("sprites/enemies/archvile/", "VILE", "VILE"),
    ("sprites/enemies/mastermind/", "SPID", "SPID"),
    # renamed -- see note 3 in the module docstring
    ("sprites/enemies/shotgunner/", "SPOS", "SPO2"),
    ("sprites/proj/revenant/", "TRCR", "TRC2"),
    # NOT under proj/ -- the Arch-Vile's flame is filed with the effects.
    ("sprites/fx/archfire/", "AVFR", "AVFR"),
]

# UE lump -> our lump. Kept under sounds/d64r/ and referenced from SNDINFO under
# a d64r/ logical namespace, so none of this can retune a Retribution monster.
SOUNDS = {
    "sounds/unseenevil/archvile/archvile_sight.ogg": "sounds/d64r/vile_sight.ogg",
    "sounds/unseenevil/archvile/archvile_roam.ogg": "sounds/d64r/vile_active.ogg",
    "sounds/unseenevil/archvile/archvile_attack.ogg": "sounds/d64r/vile_attack.ogg",
    "sounds/unseenevil/archvile/archvile_pain.ogg": "sounds/d64r/vile_pain.ogg",
    "sounds/unseenevil/archvile/archvile_death.ogg": "sounds/d64r/vile_death.ogg",
    "sounds/unseenevil/archvile/archvile_fireburn.ogg": "sounds/d64r/vile_burn.ogg",
    "sounds/unseenevil/smm_sight.ogg": "sounds/d64r/spid_sight.ogg",
    "sounds/unseenevil/smm_idle.ogg": "sounds/d64r/spid_active.ogg",
    "sounds/unseenevil/smm_pain.ogg": "sounds/d64r/spid_pain.ogg",
    "sounds/unseenevil/smm_death.ogg": "sounds/d64r/spid_death.ogg",
    "sounds/unseenevil/smm_attack.ogg": "sounds/d64r/spid_attack.ogg",
    "sounds/unseenevil/smm_windup.ogg": "sounds/d64r/spid_windup.ogg",
    "sounds/unseenevil/smm_laser.ogg": "sounds/d64r/spid_laser.ogg",
    "sounds/d64/metal.ogg": "sounds/d64r/spid_walk.ogg",
    "sounds/d64/enemies/revenant_sight.ogg": "sounds/d64r/skel_sight.ogg",
    "sounds/d64/enemies/revenant_active.ogg": "sounds/d64r/skel_active.ogg",
    "sounds/d64/enemies/revenant_hit.ogg": "sounds/d64r/skel_melee.ogg",
    "sounds/d64/enemies/revenant_swing.ogg": "sounds/d64r/skel_swing.ogg",
    "sounds/d64/enemies/revenant_die.ogg": "sounds/d64r/skel_death.ogg",
    "sounds/d64/tracer.ogg": "sounds/d64r/skel_attack.ogg",
    "sounds/d64/explode.ogg": "sounds/d64r/skel_tracex.ogg",
    "sounds/d64/pain_1.ogg": "sounds/d64r/pain.ogg",
    "sounds/d64/enemies/zombie_sight1.ogg": "sounds/d64r/cpos_sight1.ogg",
    "sounds/d64/enemies/zombie_sight2.ogg": "sounds/d64r/cpos_sight2.ogg",
    "sounds/d64/enemies/zombie_sight3.ogg": "sounds/d64r/cpos_sight3.ogg",
    "sounds/d64/enemies/zombie_active.ogg": "sounds/d64r/cpos_active.ogg",
    "sounds/d64/enemies/zombie_die1.ogg": "sounds/d64r/cpos_death1.ogg",
    "sounds/d64/enemies/zombie_die2.ogg": "sounds/d64r/cpos_death2.ogg",
    "sounds/d64/enemies/zombie_die3.ogg": "sounds/d64r/cpos_death3.ogg",
}

# Authored lumps, copied from SRC_DIR as-is. build() asserts this list covers
# every file at the top of SRC_DIR -- writing a lump and forgetting to list it
# here produces a pk3 that loads perfectly and silently does nothing, which is
# exactly how GLDEFS shipped absent and the monsters cast no light at all.
AUTHORED = ["ZSCRIPT", "MAPINFO", "CVARINFO", "SNDINFO", "LANGUAGE", "MENUDEF"]
AUTHORED_TREES = ["d64rue"]


def collect_sprites(zin: zipfile.ZipFile) -> dict[str, str]:
    """Map UE lump path -> our lump path.

    Matches on the LUMP NAME, so extension-less lumps come along (note 2), and
    RECURSIVELY, because UE files a sprite set across subfolders: the Shotgun
    Guy's walk cycle is under shotgunner/walking/ (49 of its 78 frames), and
    TRCR/AVFR are under sprites/proj/revenant/ and sprites/proj/ rather than at
    the top of proj/. A non-recursive match silently drops all of it -- the
    monster loads, and simply has no walk animation.
    """
    out: dict[str, str] = {}
    for name in zin.namelist():
        if name.endswith("/"):
            continue
        for folder, src_pre, dst_pre in SPRITE_SETS:
            if not name.startswith(folder):
                continue
            base = name.rsplit("/", 1)[-1]
            if not base.upper().startswith(src_pre):
                continue
            dst = "sprites/" + dst_pre + base[len(src_pre):]
            if dst in out and out[dst] != name:
                raise SystemExit(
                    f"two source lumps want the same destination {dst}: "
                    f"{out[dst]} and {name}")
            out[dst] = name
    return out


# Light rows, cloned from the Retribution sprite each renamed one stands in for.
#   ours   <- theirs
LIGHT_CLONES = {"SPO2": "SPOS", "TRC2": "TRCR"}
# The Arch-Vile's flame has no counterpart in Retribution, so it borrows the
# game's own flame light: the Lost Soul's (SKUL). Same idea, same palette.
LIGHT_BORROW = {"AVFR": "SKULA1"}

# The Arch-Vile's OWN body is not lit from here. Its fire is in the raised
# hands, and RTGL1 pins a sprite's attached light to the centre of the billboard
# quad -- so a lightIntensity on those frames lands in the chest, and with two
# hands both average into one point between them. tools/gen_vile_glow_emissives.py
# owns the VILE meta instead: reviewed per-frame _e masks plus emissiveMult, and
# it strips any lightIntensity it finds.


def patch_lights() -> int:
    """Give our sprites the light rows Retribution already uses for the same art.

    THIS, NOT GLDEFS, IS HOW THIS PROJECT LIGHTS PROJECTILES. Every emitter in
    the game carries a textures.json row -- TRCR 1200/ff8a38, MISL 2200, BAL1
    700, LPUF 300 (the Unmaker beam), SKUL 450 (the Lost Soul's flame), and the
    muzzle flashes CPOSF 520 / SPOSF 720 / POSSF 480. emissiveMult alone casts
    nothing; lightIntensity + lightColorHEX is what emits, and it works on
    sprites, which is all of these.
    
    So most of this is already solved and the only work is the two renames:
      * CPOSF* already has rows and our Chaingunner uses CPOS directly -> free.
      * LPUF* already has rows and our beam puffs use LPUF -> free.
      * SPOS -> SPO2 and TRCR -> TRC2 lost their rows in the rename; cloned here.
      * AVFR is new; it borrows the Lost Soul flame's row.

    An earlier version authored a GLDEFS lump with hand-picked pointlights for
    all of this. It was reinventing values the game already had, and it would
    have DOUBLED the Chaingunner's muzzle flash on top of the CPOSF rows.
    """
    # patch_global() lives in gen_enemy_eye_emissives, which imports PIL -- so
    # this step needs the project venv (tools/.venv-ai), unlike the rest of this
    # file, which is deliberately image-library-free so a sprite can never be
    # re-encoded. Reused rather than reimplemented because it carries the
    # write-BOTH-TREES rule: the build copy is xcopied over from
    # Retribution-RT-Materials on every build, so writing only one is erased
    # silently.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from gen_enemy_eye_emissives import patch_global, AUTHORED_GLOBAL
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"{exc} -- run this with the project venv: "
            r"tools\.venv-ai\Scripts\python.exe tools/pack_ue_monsters.py")

    rows = json.loads(AUTHORED_GLOBAL.read_text(encoding="utf-8"))["array"]
    by = {str(r["textureName"]): r for r in rows if "textureName" in r}

    with zipfile.ZipFile(OUT_PK3) as z:
        ours = {n.rsplit("/", 1)[-1].split(".")[0].upper()
                for n in z.namelist() if n.startswith("sprites/")}

    entries: dict[str, dict] = {}

    for mine, theirs in LIGHT_CLONES.items():
        src = {k: v for k, v in by.items()
               if k.upper().startswith(theirs) and "lightIntensity" in v}
        if not src:
            raise SystemExit(f"no lit {theirs}* rows to clone for {mine}")
        for name, row in src.items():
            target = mine + name[len(theirs):]
            if target not in ours:
                continue          # they light a frame we do not ship
            entries[target] = {k: v for k, v in row.items() if k != "textureName"}

    for mine, donor in LIGHT_BORROW.items():
        row = by.get(donor)
        if not row or "lightIntensity" not in row:
            raise SystemExit(f"donor row {donor} has no light to borrow for {mine}")
        meta = {k: v for k, v in row.items() if k != "textureName"}
        for name in sorted(n for n in ours if n.startswith(mine)):
            entries[name] = dict(meta)

    patch_global(entries)
    return len(entries)


def build() -> int:
    if not UE_PK3.exists():
        raise SystemExit(f"missing {UE_PK3} -- Unseen Evil is not installed")

    OUT_PK3.parent.mkdir(parents=True, exist_ok=True)
    grab = 0
    sprites_written = 0

    with zipfile.ZipFile(UE_PK3) as zin:
        sprites = collect_sprites(zin)
        have = set(zin.namelist())
        missing = [s for s in SOUNDS if s not in have]
        if missing:
            raise SystemExit("missing sound lumps in the UE pk3:\n  " + "\n  ".join(missing))

        with zipfile.ZipFile(OUT_PK3, "w", zipfile.ZIP_DEFLATED) as zout:
            for dst, src in sorted(sprites.items()):
                data = zin.read(src)
                # Byte-for-byte. If this ever stops being a straight copy, the
                # grAb offsets go with it -- see note 1.
                zout.writestr(dst, data)
                sprites_written += 1
                if b"grAb" in data[:512]:
                    grab += 1

            for src, dst in sorted(SOUNDS.items()):
                zout.writestr(dst, zin.read(src))

            # Both directions: every listed lump must exist, and every file
            # sitting in SRC_DIR must be listed.
            on_disk = {p.name for p in SRC_DIR.iterdir() if p.is_file()}
            unlisted = sorted(on_disk - set(AUTHORED))
            if unlisted:
                raise SystemExit(
                    "authored lump(s) in tools/d64r-ue-monsters/ that AUTHORED "
                    "does not pack: " + ", ".join(unlisted))

            for lump in AUTHORED:
                p = SRC_DIR / lump
                if not p.exists():
                    raise SystemExit(f"missing authored lump {p}")
                zout.write(p, lump)

            for tree in AUTHORED_TREES:
                root = SRC_DIR / tree
                for p in sorted(root.rglob("*")):
                    if p.is_file():
                        zout.write(p, str(p.relative_to(SRC_DIR)).replace("\\", "/"))

    print(f"{OUT_PK3.relative_to(PROJ_ROOT)}")
    print(f"  sprites {sprites_written}  ({grab} carry a grAb offset)")
    print(f"  sounds  {len(SOUNDS)}")
    print(f"  lumps   {len(AUTHORED)} + {AUTHORED_TREES}")
    print(f"  lights  {patch_lights()} textures.json rows")
    return verify()


def check_frames(shipped: set[str]) -> list[str]:
    """Every frame a state table names must have a lump in the pk3.

    UE's own Arch-Vile gets this wrong: its Heal state reads "VILE Z[\\" but the
    sprite set ships Z (25), [ (26) and ^ (29) -- 27 and 28 were never drawn. A
    state pointing at a frame with no lump animates nothing and says nothing, so
    it is worth catching here rather than in a playthrough.
    """
    # sprite prefixes we actually ship, so a state naming POSS or TNT1 (which
    # come from elsewhere) is not flagged.
    ours = {d for _, _, d in SPRITE_SETS}
    have: dict[str, set[str]] = {p: set() for p in ours}
    for lump in shipped:
        base = lump.rsplit("/", 1)[-1].split(".")[0]
        pre, rest = base[:4], base[4:]
        if pre in have and rest:
            have[pre].add(rest[0])
            if len(rest) > 2:
                have[pre].add(rest[2])

    state_line = re.compile(r"^\s*([A-Z0-9_]{4})\s+([A-Z0-9\[\]\\^_\"#]+)\s+-?\d")
    problems = []
    for zs in sorted((SRC_DIR / "d64rue").glob("*.zs")):
        for n, line in enumerate(zs.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue
            m = state_line.match(line)
            if not m:
                continue
            pre, frames = m.group(1), m.group(2)
            if pre not in have:
                continue
            for ch in frames:
                if ch not in have[pre]:
                    problems.append(f"{zs.name}:{n} {pre} frame '{ch}' has no lump")
    return problems


def verify() -> int:
    """Prove every sprite is byte-identical, and that the states can draw."""
    with zipfile.ZipFile(UE_PK3) as zin, zipfile.ZipFile(OUT_PK3) as zout:
        sprites = collect_sprites(zin)
        bad = [d for d, s in sprites.items() if zin.read(s) != zout.read(d)]
        shipped = {n for n in zout.namelist() if n.startswith("sprites/")}

    if bad:
        print(f"FAIL: {len(bad)} sprite(s) were altered in transit, e.g. {bad[:3]}")
        return 1
    print(f"  verified {len(sprites)} sprites byte-identical to the source")

    problems = check_frames(shipped)
    if problems:
        print("FAIL: state tables name frames that were never drawn:")
        for p in problems:
            print("  " + p)
        return 1
    print("  verified every state frame has a lump")
    return 0


if __name__ == "__main__":
    sys.exit(verify() if "--check" in sys.argv else build())
