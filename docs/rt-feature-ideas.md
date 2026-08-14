# RT feature ideas — what is worth building, and what was ruled out

A shortlist of path-tracing features this project could add, with the decisions already
taken. Kept so nothing here gets re-proposed from scratch, and so the rejections keep their
reasons.

Ordered by payoff per unit of work when it was drawn up (2026-08-14).

| # | Idea | Status |
|---|---|---|
| 1 | Light shafts from ordinary lamps, not just the moon | **done** — `rt_volume_shafts`, `rt_light_shafts.cpp` |
| 2 | Glass and refraction on windows and grates | **rejected** — see below |
| 3 | Mirrors on polished floors and metal | **rejected** — see below |
| 4 | Finish metal/roughness authoring for real reflections | **done** — 898 textures, seven classes |
| 5 | `ACID` liquid type for nukage and slime | **rejected** — see below |
| 6 | Heat haze over lava and fire | **planned** → [`plan-heat-haze.md`](plan-heat-haze.md) |
| 7 | Impact sparks and scorch decals | sparks **done** (`rt_spark_*`, ships off); scorch still planned → [`plan-impact-fx.md`](plan-impact-fx.md) |
| 8 | Shootable lights — kill the fixture, kill the light | open |
| 9 | Projectile impacts: plasma arcs, Unmaker melt, rocket embers | **planned** → [`plan-projectile-impact-fx.md`](plan-projectile-impact-fx.md) |
| 10 | Flames and lava in the froxel medium, not just lamps | open |
| 11 | Dust motes drifting in the lit shafts | open |
| 12 | Underwater volumetrics below the water plane | open |

---

## Rejected

**2. Glass and refraction.** `RG_MESH_PRIMITIVE_GLASS` exists and tagging by texture name
would have been cheap — but **Doom 64 has no glass**. The midtex "windows" and control-room
screens this was aimed at are opaque panels in the art, not panes. There is nothing to tag.

**3. Mirrors.** Same verdict for the same reason: **the game has no polished surfaces**.
`MIRROR` stays water-only, which is the one genuinely reflective thing in it. Note this is a
judgement about the *art*, not about the plumbing — the flag works; there are simply no
customers for it.

**5. `ACID` liquid type.** RTGL1 has a dedicated acid/nukage primitive flag that this
project has never set, and on paper Doom 64's slime should use it. In practice **the game
has no levels with visible acid**: the only floor that would qualify is in MAP34, a bonus
map, and it is not even visible there. Nothing to apply it to.

## Still open, not planned

**10. Flames and lava in the froxel medium.** Idea 1 shipped, but its fixture list is
exactly three *lamp* families — inset, edge/lattice and solo bulbs (`rt_light_shafts.cpp:69`,
selected by the `rt_volume_shaft_src` bitmask). Flames (`rt_flame_light_on`) and lava
(`rt_lava_light_on`) get analytic lights that illuminate **surfaces only**, and never enter
the medium. The result is a renderer that contradicts itself: walk past a ceiling grate on a
fogged map and there is a beam; walk past a torch and the wall lights up while the air around
it stays dead. Adding two source kinds to the existing mask reuses the cull, the budget and
the per-cell contribution test that already shipped.

**11. Dust motes in the shafts.** Sparse drifting particles in lit air — the thing that makes
volumetrics read as volume rather than as a gradient. The particle path is already wired:
`rgSpawnFluid` is live and `rt_sparks.cpp` drives it for impact debris. Needs no per-map
work and pays off on every map already lit.

**12. Underwater volumetrics.** Water is flagged, reflective and casts caustics — but only
from above; submerged sectors have clear air under the surface. A scattering medium below
the plane, with light refracted through it, reuses the froxel machinery rather than adding a
pass.

**8. Shootable lights.** Retribution lights fixtures with 9800/9801/9802 things; making a
few destructible means shooting a lamp actually drops the room into darkness. The only
gameplay item on this list, and the one most likely to make someone say "that is really ray
traced". Needs DECORATE work in a pk3 as well as renderer awareness.

## Constraints that apply to all of these

- `emissiveMult` is screen glow and **cannot light anything**. Casting needs
  `lightIntensity` + `lightColorHEX`, and that works on sprites only — walls and flats need
  an engine-side analytic light.
- Light positions are **metres**: multiply by `ONEGAMEUNIT_IN_METERS`, or the light lands
  32× away and looks absent.
- Sector colormaps tint **albedo**, not light, so an effect can read weak or wrongly
  coloured on a map for reasons that have nothing to do with the effect.
- Density in the froxel volume is shared: fog, smoke and shafts all live in it, and
  `rt_volume_far` changes all of them at once.
- Adding N lights per fixture family is how MAP07 nearly got 105 flickering monitors.
  Density limits belong in the design, not in a later tuning pass — `rt-lighting-practices`
  §20.
