# Plan — sprite emissives and materials, weapons first

**Status:** planned, not started.

The material work so far has been about **walls and flats**. Sprites got emissives where a
specific effect needed them, and the object on screen more than any other — the weapon in
your hands — has almost nothing at all.

Related: [`sprite-illumination.md`](sprite-illumination.md) (**read first** — it is the
contract this page plans work against), [`material-authoring-spec.md`](material-authoring-spec.md)
(the `_n` / `_orm` / `_h` / `_e` authoring rules), [`flame-lighting.md`](flame-lighting.md)
(84 flame sprites, the largest sprite-lighting job already done),
[`rt-voxel-models.md`](rt-voxel-models.md) (where sprites stop and models begin).

---

## 0. Where the coverage actually is

Counted from the shipped data, not estimated:

| | |
|---|---|
| Files in `rt/mat_dev` | 3441 |
| `_orm` maps (metal/rough/AO) | 763 |
| `_e` maps (emissive) | 434 |
| Entries in `rt/data/textures.json` | 3015 |
| …with `emissiveMult` | 924 |
| …with `lightIntensity` | 409 |
| …with `lightColorHEX` | 500 |

And then the weapons, which is the finding that prompted this page:

**Every first-person weapon sprite in the game has exactly nine material files between
them, all of them `PLSG`, all of them `_e`.** `SHTG`, `SHT2`, `PISG`, `CHGG`, `MISG`,
`BFGG`, `SAWG`, `PUNG` and `UNMG` have **no material of any kind** — no emissive, no normal,
no `_orm`. The plasma rifle is the sole exception because `rt_gunglow` needed it: it is the
one weapon with a lit element in its art.

So the shotgun barrel, the chaingun and the Unmaker are flat dielectrics at default
roughness, held six inches from the camera, in front of 898 hand-labelled walls.

## 1. The contract, restated because it decides the whole plan

From [`sprite-illumination.md`](sprite-illumination.md), and it is the reason this page is
worth writing at all:

- **`emissiveMult` is screen glow. It cannot light anything.** A sprite with a big
  `emissiveMult` is bright on screen and contributes nothing to the room.
- **`lightIntensity` + `lightColorHEX` do cast — and they work on SPRITES ONLY.** Walls and
  flats need an engine-side analytic light; a sprite does not.

That asymmetry is the opportunity. Sprites are the one class of surface where a **texture
author** can put real light into the world with no engine work whatsoever. 409 entries
already use it. The question this plan answers is which of the remaining ones should.

## 2. Weapons — the priority, and one check before starting

**Verify first, and it is a ten-minute check:** the viewmodel goes through `rt_weapon.cpp`
as its own quad, not the world surface path. Whether that path samples `_orm` and `_n` at
all is unknown, and if it does not, the entire weapon half of this plan is an engine change
rather than an authoring one. Do not author 40 frames of material maps before answering it.

Assuming it does, the work in priority order:

1. **`_orm` for every weapon**, using the labelling page that already exists — the same tool
   and workflow as the 898-texture pass, on roughly 40 frames. A shotgun receiver is metal;
   its grip is not. This is the highest-visibility material in the game per unit of work.
2. **`_e` for the elements that glow.** The BFG's aperture, the Unmaker's emitter, the
   chaingun's flash frames. Note `gen_fx_emissives.py` already encodes the rule for *which
   frames* count as firing — "…F fires, …E stays dark" — so the frame selection is solved.
3. **`lightIntensity` on the firing frames**, so the weapon lights the room. This is where
   the contract above pays: the muzzle flash light is engine-side today
   (`RT_AddMuzzleFlash`), but a *glow* on the weapon's own lit element does not need to be.

**The trap that will cost a day if ignored:** a weapon sprite is drawn at a fixed screen
position derived from its offsets. **PIL drops PNG `grAb` offsets** — any sprite regenerated
through a Python imaging step loses them and renders sunk into the floor, or in the wrong
place on screen for a viewmodel. This has already happened once in this project. If the
authoring pipeline touches the PNG, the offsets must be re-applied.

## 3. World sprites — where the remaining wins are

Not a bulk pass. The 434 `_e` maps already cover the obvious families (flames, eyes,
projectiles), so what is left is specific:

- **Pickups that already carry a GLDEFS light but no emissive.** Retribution's own GLDEFS
  defines pointlights for the spheres, armour and keys — so they light the room while the
  sprite itself may not read as the source. An `_e` on those closes the loop visually at
  zero lighting cost.
- **Gore and corpses.** Currently matte. Not an emissive job; an `_orm` one, and it overlaps
  the wet-blood idea (a roughness ramp is what makes gore look wet).
- **Decorative fixtures that are lit in the art but dark in the world.** The standing rule
  from [`check-the-source-art-before-lighting-a-fixture`] applies with full force: **compare
  the authored art against the generated `_e` before adding light.** More than one "unlit
  fixture" in this project turned out to be our own generator's invention, not something the
  artist drew.

## 4. Traps that apply to all of it

These are all written up elsewhere and every one of them has already been paid for once:

- **Two opposite emissive contracts.** The ray-traced path uses the **raw** `_e`; only the
  rasterized path multiplies by baseColor. An `_e` authored against the wrong one is either
  invisible or nuclear.
- **Four material directories.** `mat_dev` and `mat`, in both the build tree and the tracked
  tree. `developerMode` reads `mat_dev`, and the build resyncs it — edit all four or the
  change is a ghost that reappears on the next build.
- **`textures.json` only.** The split `textures_*.json` overlays are inert; RTGL1 reads the
  one file, and the live build-dir copy must be edited too.
- **Animated sprites need every frame.** A material on frame 1 only reads as the object
  moving or pulsing, not as a material. This is exactly how the "texture is sliding up and
  down" bug happened.
- **`emissiveMult` does not cast.** Stated twice on purpose.

## 5. Open questions

- Does `rt_weapon.cpp`'s quad path sample `_orm` / `_n`? Gates §2 entirely.
- Should the weapon's material react to the muzzle flash, or is the flash light enough? A
  metal receiver lit by its own flash is a strong shot, but the flash is a one-frame event
  and the temporal denoiser may swallow it.
- Is there a case for `_n` on weapons at all? A normal map on a sprite that never rotates
  buys less than it does on a wall, and may fight the painted shading in the art — the
  standing rule is **keep the art, add shading on top**, never replace painted albedo with a
  ramp derived from it.
