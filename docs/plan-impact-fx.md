# Plan — scorch decals

**Status:** planned, not started.

**The sparks and debris half of this plan shipped** and has its own page:
→ **[`docs/rt-impact-fx.md`](rt-impact-fx.md)**

What is left here is the persistent half: a mark on the wall after the fight, rather than
particles during it.

Related: [`blood-persist.md`](blood-persist.md) (the decal path, and where a lifetime
actually lives), [`rt-impact-fx.md`](rt-impact-fx.md) (the impact hook these would ride).

---

## 1. Scorch decals

**Where they go.** Plasma, rocket and BFG impacts. The decal path is live — the sprite
contact-AO blob uses it — so this is a new decal texture and a spawn rule, not new plumbing.

**The impact hook already exists.** `rt-impact-fx.md` §1 put a real hook in `P_LineAttack`
with a true surface normal and the hit texture in hand. But note that hook is **hitscan
only**: plasma, rockets and the BFG are projectiles and never reach it. A projectile impact
needs its own trigger, and `rt_smoke.cpp`'s rocket source is the precedent — tracked by
pointer, with `MF_MISSILE` clearing as the death event, needing no DECORATE edit.

**The trap that is already written down:** RTGL1 decals need **world-space vertices** and an
identity transform. `RsDecal.vert` writes `outWorldPos = position` untransformed, so a decal
built with a transform rasterizes in the right place on screen and then discards every
fragment — nothing renders, nothing errors. See `rt_draw.cpp` and `blood-persist.md`.

**A second trap, from the AO blob:** the decal shader falls back to `ldrEmis = albedo` when
no emissive texture is bound, so a non-zero `emissive` on an untextured decal makes it glow
and write screen emission where there should be none. That directly constrains §2.

**Lifetime.** Blood persistence had to solve exactly this and the answer was not in the
renderer — the one-second lifetime was in the WAD's DECORATE, and `rt_gore_max` is a ZScript
FIFO in `d64r-blood-persist.pk3`, not a renderer cap. Check where a scorch's lifetime is
actually decided before adding a cvar for it.

**Fade.** Shrink the alpha; do not tint toward the floor colour. The floor colour is not
knowable, and sector colormaps tint albedo rather than light, so a "matching" tint will be
wrong on any coloured map.

**Geometry.** A single triangle **fan**, centre opaque and rim at zero, exactly as the AO
blob does. A ring/plateau topology puts a visible crease in every segment; the reasoning is
written out at length in `rt_draw.cpp` and should not be rediscovered.

**Classification is available and worth using.** `rt/data/spark_surfaces.txt` already says
what every labelled texture is made of (`rt-impact-fx.md` §2). A scorch on `fluid` is wrong,
and one on `flesh` should probably be a burn rather than soot.

## 2. Optional — glowing plasma burns

A plasma scorch could carry a short emissive tail: bright cyan for ~0.3 s, fading to plain
soot. That buys a genuinely ray-traced moment — a fading pool of light on the floor after a
firefight — for one extra decal layer with an `_e` mask.

If it is done: the emissive mask must be a **raw** `_e`, never sampled from the albedo. The
ray-traced path uses `_e` directly and only the rasterized path multiplies by baseColor. And
note the decal emissive fallback above — an emissive decal needs a real `_e` bound, not just
a non-zero `emissive` float.
