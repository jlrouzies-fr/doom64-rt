# RT feature ideas — what is worth building, and what was ruled out

A shortlist of path-tracing features this project could add, with the decisions already
taken. Kept so nothing here gets re-proposed from scratch, and so the rejections keep their
reasons.

Ordered by payoff per unit of work when it was drawn up (2026-08-14).

| # | Idea | Status |
|---|---|---|
| 1 | Light shafts from ordinary lamps, not just the moon | **planned** → [`plan-light-shafts.md`](plan-light-shafts.md) |
| 2 | Glass and refraction on windows and grates | open |
| 3 | Mirrors on polished floors and metal | open |
| 4 | Finish metal/roughness authoring for real reflections | **rejected** — see below |
| 5 | `ACID` liquid type for nukage and slime | **rejected** — see below |
| 6 | Heat haze over lava and fire | **planned** → [`plan-heat-haze.md`](plan-heat-haze.md) |
| 7 | Impact sparks and scorch decals | **planned** → [`plan-impact-fx.md`](plan-impact-fx.md) |
| 8 | Shootable lights — kill the fixture, kill the light | open |

---

## Rejected

**4. Finish the metal/roughness authoring.** The idea was that once `metallic` and
`roughness` are right, path tracing gives reflections and highlights for free, with no
engine work. It is a data problem, and the data cannot be produced: **no AI parsing of the
textures was able to reliably tell metal from non-metal**, and doing 1000+ textures by hand
is not worth it. `tools/fix_orm_metallic_ai.py` is the record of that attempt. Do not
re-propose it as "just an authoring pass" — the authoring is the hard part.

**5. `ACID` liquid type.** RTGL1 has a dedicated acid/nukage primitive flag that this
project has never set, and on paper Doom 64's slime should use it. In practice **the game
has no levels with visible acid**: the only floor that would qualify is in MAP34, a bonus
map, and it is not even visible there. Nothing to apply it to.

## Still open, not planned

**2. Glass and refraction.** `RG_MESH_PRIMITIVE_GLASS` and `GLASS_IF_SMOOTH` exist and are
used in exactly one place (`rt_draw.cpp:306`). Doom 64 is full of midtex windows and
control-room screens that render opaque or alpha-tested. Tagging them by texture name, the
way `l_waterflag` tags water at `rt_draw.cpp:869`, would need no per-map work. This is
probably the most unmistakably ray-traced effect available for the least engine work.

**3. Mirrors.** `MIRROR_IF_SMOOTH` keyed on flat name, used sparingly — a few hell-marble
floors, some tech-base metal. `MIRROR` is currently water-only. Note this partly overlaps
idea 4: a mirror flag sidesteps the metal-authoring problem by naming the handful of
surfaces that should reflect, instead of trying to classify every texture.

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
