# MAP02 Blue Room — RT Lighting Investigation

**Date:** 2026-08-07  
**Status:** Engine change implemented and built; visual confirmation still pending.

## Problem

The Retribution MAP02 blue armor room did not match the original game in the RT renderer. In the original, the room has a strong blue atmosphere/filter. In the RT version, the aligned ceiling spotlight textures appeared neutral white and the room lost most of its blue character.

This was separate from the previously fixed false blinking lights in the middle of the room. Those were caused by over-broad ceiling emissive/analytic-light handling and are not recreated by this fix.

## Diagnosis

Inspection of Retribution MAP02 `TEXTMAP` data in `Doom64-Retribution/D64RTR_v15.WAD` found sectors in the blue armor area using:

```text
lightcolor = 20735 = 0x0050FF
```

The RT compatibility path in `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp` intentionally forces world vertex RGB to white under `rt_mod_compat`. That earlier fix is necessary because sector colors and light levels caused other problems, including yellow key-door neon wash and black/light-absorbing dark rooms. However, forcing every world primitive to white also discarded the original MAP02 blue sector filter.

The missing color was therefore not treated as a missing point light or a new emissive texture. The correction restores the original sector color as a narrowly scoped surface tint.

## Implementation

The following engine files were changed:

- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_state.h`
  - Added `FRtState::m_sectorLightColor` to carry the active sector colormap color.

- `sourcecode/gzdoom-rt/src/rendering/hwrenderer/scene/hw_flats.cpp`
  - Stores `FColormap.LightColor` in RT state for floors and ceilings.

- `sourcecode/gzdoom-rt/src/rendering/hwrenderer/scene/hw_walls.cpp`
  - Stores the active wall colormap color in RT state.
  - Also updates the state for 3D-light wall slices using their local colormap.

- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`
  - Detects Retribution MAP02 using the RT map name.
  - Matches only the strong blue profile: low red, medium green, and high blue, corresponding to the measured `0x0050FF` color.
  - Applies a bounded tint of approximately `(0.35, 0.58, 1.0)` to affected world primitives.
  - Keeps the existing white-world-albedo behavior everywhere else.

The change does **not**:

- Add a point light at the sector center.
- Re-enable generic ceiling lamps.
- Add or restore `SFLAT*` emissive masks.
- Affect other maps.
- Tint ordinary MAP02 sectors such as the yellow-door areas.
- Change sprites, weapons, UI, sky, decals, or particles.

## Validation

The first build exposed type issues in the new code (`FVector3` uses `X/Y/Z`, and strict MSVC narrowing rules require float literals). Those were corrected.

The final engine build completed successfully:

```text
sourcecode/gzdoom-rt/build/RelWithDebInfo/gzdoom.exe
```

## Remaining confirmation

Launch MAP02 with the rebuilt engine:

```text
tools/launch-retribution-rt.cmd 2
```

Compare the blue armor room against:

```text
screen/level2-blueroom.png
screen/level2-currentblueroom.png
```

Confirm that:

1. The room has the intended blue cast.
2. The aligned spotlights remain visually plausible rather than becoming overbright blue emitters.
3. The yellow key-door area does not regain its previous neon wash.
4. No center-room blinking light returns.

If the tint is too weak or too strong after visual testing, adjust the three bounded tint constants in `rt_main.cpp`; do not restore global sector-color multiplication.