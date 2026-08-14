# Sprite shadows and contact occlusion

Everything in Doom 64 that is not a wall, a floor or a ceiling is a **sprite** —
a camera-facing quad with no thickness. Under a path tracer that shows, in two
separate and independent ways, and this document is both of them:

| | the complaint | the mechanism | cvar |
|---|---|---|---|
| **§1** | an actor casts no shadow when the light is to its side, and its shadow changes shape as you turn | invisible crossed quads at fixed world angles, in the acceleration structure, visible only to shadow rays | `rt_sprite_shadow` |
| **§2** | things float — they do not sit *on* the floor, and dropped weapons and corpses have nothing under them at all | a soft dark blob on the floor, as an RTGL1 decal multiplied into the floor's albedo | `rt_sprite_ao` |

**They are not alternatives and neither replaces the other.** A cast shadow
answers *where is the light*, and a board answers that badly: when the light lies
**in** the board's plane the shadow projects to a line and vanishes. Contact
occlusion answers *is something touching this floor*, which has the same answer
from every light direction — so it is precisely the term that survives the frame
the cast shadow loses. §1 also refuses the flat classes (corpses, gibs, dropped
weapons) on purpose, because a vertical cross is the wrong shape for them, and §2
is what covers those.

Both ship **on**. Both are compiled on *and* pinned in `tools/d64rt-pins.cfg` — a
pin overrides the compiled default, so changing only one changes nothing, and that
has cost time here before.

    .	oolsb.cmd sprshadow-off 02   .	oolsb.cmd sprshadow-on  02
    .	oolsb.cmd spriteao-off  02   .	oolsb.cmd spriteao-on   02

**The recurring lesson across both**, and the thing to read before extending
either: *one proxy shape cannot serve every sprite class.* Every artefact found in
play on either mechanism was its shape assumption failing somewhere it did not
fit, and every fix narrowed **where the feature applies** rather than improving
the proxy. The useful question is never "is the proxy better" — it is "does this
object match the assumption", and where it does not, the honest move is to leave
that class alone.

Companion docs: `docs/rt-voxel-models.md` (why voxelising the actors is a
documented dead end), `docs/moon-and-sky-leaks.md` §5.2 (the light-selection
mechanism §1's open issue turns on), `docs/sprite-illumination.md` (making sprites
*emit* light, which is a different problem entirely).

---

## 1. A sprite has no thickness — `rt_sprite_shadow`

Reported straight after the moon's own light-selection fix landed
(`moon-and-sky-leaks.md` §5.2), and it is the other half of the same complaint. A sprite is a **camera-facing quad**, so its shadow is the projection
of a plane:

- **A light lying in that plane projects it to a line.** Look at an actor with
  the light exactly to your left and it casts nothing at all.
- **The quad turns to face you, so the shadow's shape changes as you rotate.**
  Nothing physical does this, and it reads as instability.

Voxelising the actors would fix it properly and is a **documented dead end** here
— `docs/rt-voxel-models.md` §6: silhouette carving from Doom's 8 hand-drawn
rotations cannot represent a concavity, "the ceiling of the method, not a tuning
problem."

**What ships instead: invisible crossed quads.** Each visible actor also submits
`rt_sprite_shadow_planes` (2) quads at **fixed world angles**, flagged
`RG_MESH_PRIMITIVE_SHADOW_ONLY`. At 90° apart no light direction is degenerate —
as one plane goes edge-on the other is face-on — and being world-fixed, the
shadow stops following the camera.

| | |
|---|---|
| **Invisible how** | The proxies land on `INSTANCE_MASK_RESERVED_0`, which is absent from `rayCullMaskWorld` (`WORLD_0\|1\|2`) and therefore from the primary, reflection, refraction and indirect cull masks *by construction*. One line in `VulkanDevice.cpp` adds it to `rayCullMaskWorld_Shadow`, and that is the only ray that can see them. |
| **Why it is cheap** | `CalculateTrueTransformAndItsVerts` already factors a billboard into (rotation, pivot) + un-rotated local verts, so a proxy is **the same vertices under a different transform** — no vertex maths, no second geometry copy, no texture work. |
| **Silhouette, not a rectangle** | The alpha test is carried over in the flags. |
| **Skipped** | Translucent sprites — spectres, the nightmare imp, additive fire. RTGL1 rasterizes those, so they are not in the AS and cast nothing today; giving them a solid shadow would be a change in look, not a fix. |
| **Bounded** | `rt_sprite_shadow_dist` (40 m). The cost is per visible actor per frame. |
| **The caster** | `rt_sprite_shadow_hidecaster` (on) puts `NO_SHADOW` on the visible billboard, or the umbra is the union of all three quads — fatter than the actor and still camera-dependent, i.e. the artefact survives diluted. |

Unique IDs are `actor pointer + 0x4000000000000000 + plane`, deliberately beyond
any Windows x64 user-space pointer: a collision would make RTGL1 drop one of the
two primitives with *"a primitive with the same ID already exists"*, silently,
and the proxy is the one that would lose.

**SHIPPING ON** (2026-08-13) — compiled default `rt_sprite_shadow true` **and**
pinned in `tools/d64rt-pins.cfg`, along with the scope, plane count, width,
hidecaster and distance. Both are needed: a pin overrides the compiled default,
so changing only one changes nothing. A/B:

    .\tools\ab.cmd sprshadow-off 02      stock billboards
    .\tools\ab.cmd sprshadow-on  02      what ships

### What a proxy can and cannot stand in for

A proxy is **an assumption about 3D shape**, and the four artefacts found in play
are all that assumption failing somewhere it does not fit. Worth keeping
together, because each fix narrows *where the feature applies* rather than
improving the proxy:

| symptom | cause | answer |
|---|---|---|
| swinging corner shadows across the flashlight beam | the **player's own** body is a `FirstPersonViewer` sprite that is also an `ExportInstance`, so it got proxies — and clearing the mesh flags dropped `FIRST_PERSON_VIEWER`, making them world occluders standing at the camera | skip viewer sprites. Keeping the flag instead fails: `PV_FIRST_PERSON_VIEWER` is tested before `PV_SHADOW_ONLY`, so the proxy would become *visible* geometry in front of the camera |
| black stripe down the middle of every enemy in the beam | a proxy plane passes through the actor's **own axis**, so it shadows the half of its own billboard behind it — and with the flashlight (a light along the sprite's normal) the perpendicular plane is edge-on and projects to a line down the centre | alpha-tested instances carry `INSTANCE_CUSTOM_INDEX_FLAG_IGNORE_SHADOW_PROXY`; `getShadowCullMask` strips `RESERVED_0` for them, so sprites do not **receive** proxy shadows |
| shadow spilling onto the floor *in front* of a sprite | proxies were as wide as the sprite's **canvas** (a marine: 64 units of art around a radius of 17), so the plane facing the viewer overhung the actor by ~2× | `rt_sprite_shadow_width` scales the horizontal axis to `actor->radius` |
| radiating spokes from corpses, gibs and dropped weapons (`screen/shadowissue.png`) | those are **flat plates on the ground**; four vertical cards through one is simply the wrong shape | emit proxies only for upright things — `!MF_CORPSE && Height >= 24 && Height >= 1.5·radius`. Corpses and pickups keep their stock billboard shadow, exactly as before the feature |
| a **mirrored twin** beside the shadow, on some enemies of a class but not others (`screen/invertedSpriteShadow.png`) | a textured plane's shadow is the **mirror** of its mask when the light is on the plane's far side, so roughly half the world-fixed planes cast a flipped silhouette | flip each proxy's U so its un-mirrored face points at the **camera** — gzdoom already chose the sprite's rotation frame for the camera's angle, so that is the only available definition of correct, and it is the right one for the flashlight |
| that mirroring **surviving the flip**, specifically on side-on enemies | the local verts are not axis-aligned. `hw_sprites.cpp` hands `push_apply_spriterotation` the **actor's own yaw**, so the quad keeps its camera-facing orientation baked in, offset by `camera_yaw − actor_yaw` | canonicalise the quad from its own vertices before using it (below) |

**The one that invalidated three earlier fixes.** Because the local verts carry
that baked offset, a proxy built as "the same verts under a `yaw_k` transform"
actually sat at `yaw_k + (camera_yaw − actor_yaw)`. Consequences, all silent:

- the planes were **not world-fixed** — they rotated with the camera, which is
  the property the whole design rests on;
- **local Y was not the width axis**, so `rt_sprite_shadow_width` narrowed the
  wrong one;
- the mirror test's normal was off by the same angle, worst when the actor is
  **side-on** to the viewer — exactly where the mirrored shadow survived.

The fix derives the quad's frame from its own vertices: take the face normal
(`(p1−p0)×(p2−p0)`), pick the side the camera is on since winding is not
guaranteed, then rotate the verts about local Z until that normal is `+X`. The
quad is then canonical — normal `+X`, width along `Y`, upright along `Z` — and a
rigid rotation cannot mirror it, so the texture's handedness relative to the
normal survives. Only then do the width scaling, the world yaws and the mirror
test mean what they say.

The height test is shape, not taste: gzdoom quarters an actor's `Height` on
death, so a corpse lands near **H/R 0.7** while every standing monster is 1.8+
(demon 30/56) and a barrel is 4.2; pickups are short without ever being corpses
(shotgun 20/16 = 0.8).

**Shipping scope is live monsters only** — `rt_sprite_shadow_scope 1`
(`MF3_ISMONSTER && health > 0`, on top of the shape tests). Scope 0 widens it to
anything upright, which also takes in barrels, torches and tall props.

`health > 0` is not redundant with `MF_CORPSE`: an actor is dead the moment its
health reaches 0 and plays a death animation for several tics **before**
`MF_CORPSE` is set and its height quartered. Without it, a dying enemy keeps
full-height vertical proxies through exactly the frames where it is folding onto
the floor.

**The general lesson.** One proxy shape cannot serve every sprite class. The
useful question is not "is the proxy better" but "does this object match the
assumption" — and where it does not, the honest move is to leave that class on
the stock billboard rather than to keep tuning.

### The plane spread was wrong for 3 and 4 planes

The yaws were a fixed table `{0, π/2, π/6, π/3}`. A plane's orientation is modulo
π — a quad and its 180° twin are the same occluder — so for `planes 4` that table
is **0/30/60/90**: every plane packed into one quadrant, with the 90°–180° half
uncovered. The consequence is that **how wide a shadow an actor casts depends on
the light's compass bearing**, worst case 0.71× the actor's width against 0.97×
at the best. It is derived now, `k·π/n`, so 4 planes are 0/45/90/135 and the
worst case rises to 0.92×. `planes 2` was correct by luck and is unchanged;
**the default is now 4**, which reads better in play.

### Open: a missing shadow on a WALL

Reported 2026-08-13 and **not yet resolved**. Sprite ahead, light to its right,
wall to its left: the shadow lands on the floor but the wall gets nothing. Two
candidates, and they need opposite fixes:

- **Geometry** — the plane facing that bearing is too narrow, or no proxy reached
  that surface. But the spacing arithmetic above predicts a *narrower* shadow,
  not an absent one, so this is the weaker candidate.
- **Light selection** — `moon-and-sky-leaks.md` §5.2 again, for a *local* lamp. `rt_sun_split` took only
  the moon out of ReSTIR's per-pixel draw; every ordinary light still competes,
  so a lamp's shadow resolves only where that lamp wins. Near the sprite it
  dominates the floor and wins; on a wall several lights reach, it wins on a
  fraction of pixels, and a sparse shadow is what the denoiser flattens. That
  predicts "floor yes, wall no" with no geometry involved.

Two arms separate them, both run from the exact viewpoint where it is missing:

    .\tools\ab.cmd sprshadow-probe 02    rt_debug_visibility 1 -- is the ray blocked?
    .\tools\ab.cmd sprshadow-max   02    shadow_samples 8 + spp_direct 4

Actor-shaped **black** on the wall under `probe` means the proxies *are*
occluding and the loss is downstream; the shadow appearing under `max` confirms
selection variance. If selection is the answer, the fix is not more planes — it
is extending the `rt_sun_split` treatment to the dominant local light, which is a
real design job, not a cvar.

Both arms also set `rt_sun_split 1`, since outdoors there is no point testing
sprite shadows the moon was never resolving. **The check that matters most is a
negative one:** nothing new should ever be *visible* — not directly, not in a
mirror or water, not as a brightening from indirect light. A faint cross around
an actor would mean the instance mask is wrong, and that is the single failure
mode this design has.

---

## 2. The other half — contact occlusion, `rt_sprite_ao`

Requested 2026-08-13, in the same breath as the wall shadow above: *"can we have
a bit of ambient occlusion under enemies / props sprites (e.g. weapons on the
floor) — to compensate that a sprite 2d board doesn't always cast shadows if
light is perpendicular."*

**It is a second mechanism, not a tuning of §1, and the reason is the whole
point.** A cast shadow answers *where is the light*, and a board answers that
badly by construction: §1's crossed proxies remove the camera dependence and
the fully degenerate direction, but a plane is still a plane, and how much
shadow an actor throws still swings with the light's bearing (0.92× at best,
by the arithmetic in §1). Contact occlusion answers a different question —
*is there an object touching this floor* — and that question **has the same
answer from every light direction**. So it survives exactly the frame the cast
shadow loses.

And it reaches the classes §1 deliberately refuses. `rt_sprite_shadow_scope 1`
is live monsters only, because a vertical cross through a corpse, a gib or a
dropped shotgun is the wrong shape and threw radiating spokes
(`screen/shadowissue.png`). Those things kept their stock billboard shadow,
which is to say very little. **A blob on the floor is the right shape for a flat
thing lying on a floor** — which is why this is worth building rather than
adding a fifth plane.

### What ships: an RTGL1 decal, not geometry

Each qualifying thing submits a **triangle fan** on the floor beneath it, flagged
`RG_MESH_PRIMITIVE_DECAL`: black, alpha `rt_sprite_ao_strength` at the centre
falling to 0 at the rim. The falloff is **vertex-colour interpolation**, so the
feature ships no art, writes no `textures.json` entry and touches no material —
with no texture bound, RTGL1 samples its 1×1 white (`TextureManager::
CreateEmptyTexture`), which is the identity this needs.

The decal pipeline blends `SRC_ALPHA / ONE_MINUS_SRC_ALPHA` into the G-buffer
albedo, so a black decal leaves the floor at `albedo × (1 − a)` — a pure
**multiplicative darkening**. Three properties fall out of that, and all three
are the reason a decal was chosen over a light or a shadow caster:

| | |
|---|---|
| **It scales with the light already there** | Full strength on a lit floor, invisible in a dark room. An occlusion term must never be able to push a surface below unlit, and an additive black overlay would. |
| **It cannot occlude or be hit** | Rasterized, never in the acceleration structure. No reflection, refraction or bounce ray can see it, and it costs nothing in the AS. |
| **It stops at edges for free** | `RsDecal.frag` discards where the traced surface under the pixel is more than **5 cm** from the quad. So the blob stops at a step instead of smearing down it — and it is hidden behind the sprite's own pixels without a depth test (the pipeline has `depthTestEnable = VK_FALSE`). |

### The footprint's shape — one shape cannot serve every class

Requested after the first working build: *"under a shotgun on the floor it should
not be round, it should be a line the length of the shotgun sprite."* Correct, and
it is §1's lesson again in a new place.

- **Standing things keep a circle** at the collision radius. A body's footprint
  really is roughly round, the circle is camera-independent, and the collision
  radius is the honest measure — the sprite's canvas is about twice the body (the
  marine drawn on 64 units around a radius of 17), which is the trap
  `rt_sprite_shadow_width` exists for.
- **Things lying down get an ellipse fitted to the sprite quad.** For a dropped
  shotgun the art is the *only* description of the shape there is, so the
  along-axis is measured from the quad's real horizontal extent in world space.

The along-axis is derived by **2×2 principal axis of the quad's world XY
vertices**, not by "take local Y" — that is precisely the mistake §1 spent three
fixes on, because the local verts carry a baked `(camera_yaw − actor_yaw)` offset
and no local axis means what its name says. A covariance carries no such
assumption and is also correct for a pitched quad, where the up axis has a
horizontal component too.

**The across-axis is not measurable and is not pretended to be.** A single
camera-facing billboard carries no information whatsoever about how deep an object
is — the same ceiling `docs/rt-voxel-models.md` §6 documents for silhouette
carving. So it is a declared constant, `rt_sprite_ao_aspect` (0.4), and no work on
this code reaches past that.

**The fitted ellipse turns with the billboard**, and this was accepted when it was
asked for. Note it is the exact opposite of the §1 proxies, which are
world-fixed *precisely so the shadow stops following the camera* — and the two are
consistent rather than contradictory: a **cast shadow**'s shape must not follow
the viewer, because nothing physical does that; a **footprint traced from the drawn
object** should track what is actually drawn. `rt_sprite_ao_shape 0` reverts to the
disc as a pin change, and raising `rt_sprite_ao_aspect` toward 1 is the middle
position — it rounds the ellipse out and shrinks the swing without giving up the
fit.

    .\tools\ab.cmd spriteao-disc 02     circle everywhere
    .\tools\ab.cmd spriteao-on   02     fitted -- walk a circle around a dropped gun

### Size: the blob must not be a scale model of the object

Requested 2026-08-13: *"the bigger the sprite, the less there is."*

Both sizing paths are otherwise **linear in the object** — the circle is a
multiple of the collision radius, the ellipse a multiple of the sprite's own
width — so a soldier got a footprint as much bigger than a shotgun lying beside
him as his body is. That reads wrong, and the reason is worth stating because it
also says how far to take the correction: **contact occlusion is not a scale model
of the object.** It is the gap where the object meets the floor, and that gap does
not grow with the object — a soldier's boots meet the floor on about as much area
as a shotgun's receiver does.

So the footprint is pulled toward a reference size by an exponent:

    f = (ref / size) ^ rt_sprite_ao_sizefall

`0` leaves the linear behaviour untouched, `1` makes every blob exactly `ref`
across whatever its owner's size, and the default `0.6` sits between — big things
still read bigger, just far less than proportionally.

An **exponent rather than a clamp** because it has no discontinuity: no actor size
is a special case, and nothing pops when a thing changes size in play — which does
happen, since gzdoom quarters an actor's `Height` on death.

`ref` is fixed at **one metre** (32 map units, an ordinary Doom actor) rather than
being a cvar. Moving the pivot point is what `rt_sprite_ao_radius` and
`rt_sprite_ao_fit` already do; `sizefall` only decides how much **spread** there is
around it.

### Standing bodies get a fainter blob than things lying flat

Reported after the size falloff landed: the shotgun reads right, the soldier is
about 30% too heavy. **Size cannot explain that and `rt_sprite_ao_sizefall` cannot
fix it** — once the size falloff is applied the two footprints are within a few
centimetres of each other. What actually differs is that the shotgun's is a thin
ellipse (`aspect` 0.4) and the soldier's a full circle, so the soldier's covers
roughly **three times the area** at the same strength.

`rt_sprite_ao_upright` (0.7) scales strength for upright things only, and it is a
class rule rather than a fudge because the physics agrees:

- a **dropped weapon is in contact with the floor across its whole footprint**, so
  the occlusion under it is strong and tight;
- a **standing body touches the floor only at its feet**. Everything above the
  ankles is far enough up that the floor still sees most of the sky, so real
  contact occlusion under a standing figure genuinely is weaker and broader.

It reuses the same upright test `rt_sprite_shadow` keys on, so nothing new is
classified: the soldier passes (`h 56 >= 1.5·r 20`), the shotgun pickup fails on
the absolute height floor (`h 20 < 24`), and a corpse moves to the lying-down side
the moment gzdoom quarters its `Height`.

**If monsters still read heavy, this is the knob** — not `rt_sprite_ao_strength`,
which would take the props down with them.

### Strength: 0.7, and why the a-priori number was too low

Settled in play (2026-08-13). It **shipped at 0.45** on the written argument that
anything past ~0.6 would stop reading as contact and start reading as a painted
black disc. That argument was wrong, and the reason generalises to every knob in
this feature:

**`rt_sprite_ao_strength` is not the darkness you see.** The blob multiplies the
floor's *albedo*, so what reaches the screen is already scaled by the light in the
room, by the rim falloff, and by however much of the blob the sprite itself is
covering. The cvar is the darkness you would get on a fully-lit floor at the exact
geometric centre — a case that essentially never fills a pixel. Reasoning about it
as if it were a screen-space overlay under-shoots, and it under-shot by about a
third.

The same caution applies in the other direction to `rt_sprite_ao_aspect` and
`rt_sprite_ao_fit`: pick them by looking at a dropped weapon in a lit room, not by
argument. The one number that should still be reasoned about rather than eyeballed
is `rt_sprite_ao_fade`, because its failure (a disc following a flying enemy) is
not visible at all from the viewpoint where you would be tuning the others.

### The blob is a single fan, and it must stay one

A dead end worth recording, because the fix for it is not the obvious one.

An attempt to give the blob a flat dark **core** — a full-strength inner ring, then
a ramp to the rim — put visible **triangles** around every blob. The cause is
structural, so more segments does not help:

| triangle of a ring quad | alpha | iso-lines run |
|---|---|---|
| `(i0,o0,o1)` | `A·λ(i0)` | parallel to the **outer** edge |
| `(i0,o1,i1)` | `A·(λ(i0)+λ(i1))` | parallel to the **inner** edge |

Two gradient directions meeting along the diagonal is a crease, and it appears in
every segment at once. Banding the penumbra over several thin rings shrinks it but
does not remove it.

**A single fan has no such quad.** Every triangle's alpha is `A·λ(centre)`, so all
the gradients agree, and the only polygonal boundary is the rim — which sits at
alpha 0, where a facet cannot be seen. That is why the original looked smooth, and
it is the property to preserve: **do not introduce a high-alpha ring.**

If a genuinely different radial profile is ever wanted, the answer is a per-pixel
falloff — a radial-gradient texture bound to the decal, since `RsDecal.frag`
already multiplies `baseColor()` by its texture sample — not more geometry.

### The four things that decide whether it is honest

Each of these is the feature admitting where its assumption stops, in the same
spirit as §1's scope tests:

- **Height fade** (`rt_sprite_ao_fade`, 56 map units). The blob asserts the thing
  is *on* the floor. A lost soul crossing a room, a cacodemon, a rocket in flight
  and a jumping player must not carry a disc with them, so it fades linearly from
  contact to nothing. This is the single most important knob for not looking fake.
- **The floor comes from the playsim.** `actor->floorz`, plumbed through
  `m_lastthingfloorz`, not re-derived in the renderer. It is already resolved
  across 3D floors and slopes, and getting it wrong buries the quad in the floor
  where the 5 cm test silently discards it — a failure that looks exactly like
  the feature not being built.
- **Radius is the actor's, not the quad's.** `rt_sprite_ao_radius` multiplies
  `actor->radius`. A sprite quad is the art's canvas and is roughly twice the
  body (a marine: 64 units of art around a radius of 17) — the same trap
  `rt_sprite_shadow_width` exists for. The default is 1.6× on purpose: occlusion
  reaches past a silhouette, and a blob cut exactly at the body reads as a
  sticker.
- **One blob per actor per frame.** A sprite with a fog layer draws **twice**
  (`hw_sprites.cpp` ~390/398), and unlike a mesh primitive a decal has no ID
  collision check to save us — two passes would blend twice and square the
  darkening. Gated on `primitiveIndexInMesh == 0`, which resets per actor, so it
  needs no static state and no frame counter.

The player's own viewer sprite is excluded, for the same reason §1 excludes it:
it is drawn at the eye, and a blob under it is a dark ring painted around the
camera.

### Cvars

| cvar | default | note |
|---|---|---|
| `rt_sprite_ao` | `true` | master switch |
| `rt_sprite_ao_strength` | `0.7` | fraction of the floor's albedo removed at the centre. Settled in play — see below |
| `rt_sprite_ao_radius` | `1.6` | multiple of `actor->radius`, for the **circle** |
| `rt_sprite_ao_upright` | `0.7` | strength multiplier for standing things only. The knob for "monsters read too heavy" |
| `rt_sprite_ao_sizefall` | `0.6` | how much smaller, relative to its owner, a blob gets as the sprite grows. 0 = proportional, 1 = all the same size |
| `rt_sprite_ao_shape` | `1` | 0 = circle always; 1 = circle upright / ellipse lying down; 2 = ellipse always |
| `rt_sprite_ao_fit` | `1.0` | multiple of the **sprite's** horizontal extent, for the ellipse. 1 = the art's own width |
| `rt_sprite_ao_aspect` | `0.4` | the ellipse's across-axis over its along-axis. A declared assumption, not a measurement |
| `rt_sprite_ao_fade` | `56` | map units of height over which it fades out |
| `rt_sprite_ao_scope` | `0` | 0 = everything with a floor; 1 = only what `rt_sprite_shadow` skips |
| `rt_sprite_ao_segments` | `32` | angular resolution — the silhouette only; the rim sits at alpha 0 |
| `rt_sprite_ao_dist` | `30` | metres. Tighter than the proxies' 40 — see the limitation below |
| `rt_sprite_ao_debug` | `false` | **`RT_CVAR_NOARCH`** — per-60-draw count of blobs *uploaded*, plus the nearest one's world position. Read the trap below before using it |

Compiled defaults **and** pins in `tools/d64rt-pins.cfg`, both, per the rule in
§1: a pin overrides the compiled default, so changing one alone changes
nothing.

    .\tools\ab.cmd spriteao-off  02     control
    .\tools\ab.cmd spriteao-on   02     what ships
    .\tools\ab.cmd spriteao-loud 02     0.9 / 2.5x -- "is it running at all"

`spriteao-loud` exists because the shipping values are deliberately subtle and
*"I see no difference"* is ambiguous between "working and subtle" and "not
running". Run it first when something looks wrong, then judge strength on
`spriteao-on` — judging strength on `loud` is how a feature ships as a sticker.

### The trap: a decal's world position is NOT its transform

**The first version shipped invisible**, and the failure is worth the space
because nothing about it is guessable from the API and nothing at all is logged.

`RsDecal.vert` is three lines long and the middle one is the problem:

```glsl
outTexCoord = texCoord;
outWorldPos = position;                                    // <- LOCAL, untransformed
gl_Position = rasterizerVertInfo.viewProj * vec4( position, 1.0 );
```

The push constant is *already* `model * viewProj` (`RasterizedPushConst`
premultiplies `info.transform`), so **`gl_Position` is transformed and
`outWorldPos` is not.** The fragment shader then tests that untransformed value
against a true world-space `framebufSurfacePosition`.

So the blob was built the way the shadow proxies above legitimately are — verts
around a local origin, location in `mesh.transform` — and the result is a quad
that **rasterizes in exactly the right place on screen and then discards 100 % of
its fragments**, because its "world" position is ~(0,0,0) while the floor is tens
of metres away. Not misplaced. Invisible, silently, with no warning and no
geometry to inspect.

gzdoom's own wall decals never hit this: world geometry takes the `MakeTransform`
branch in `InternalDraw`, where the transform is identity and local already *is*
world. **A sprite is the only caller that arrives at the decal path with a real
transform**, which is why a working decal system could be sitting right there and
still not save the first attempt.

The fix is one line of policy — **world-space vertices, identity transform** —
and `rt_sprite_ao_debug` exists so this class of failure can never again be
confused with the feature being switched off. It counts *uploads*: `emitted > 0`
with a clean screen means a position bug, not a disabled feature. That distinction
is the entire reason the cvar is there.

### Known limitations, stated rather than hidden

- **Not in reflections or water.** It is rasterized into the primary G-buffer, so
  a mirror shows the floor with no blob. This is the cost of the approach and it
  is the thing to look at first if the feature ever needs replacing.
- **Long range.** The decal's 5 cm test compares against the *checkerboard
  neighbour's* traced surface position, and at distance a pixel footprint can
  exceed 5 cm on a grazing floor, which drops fragments. `rt_sprite_ao_dist 30`
  is the bound; the same limit applies to the game's bullet-hole decals.
- **`rt_sprite_ao_scope 0` overlaps `rt_sprite_shadow` on live monsters.** Both
  are present under a standing enemy. That is deliberate — the proxy shadow is
  what vanishes when the light lies in its plane, and the blob is what is left.
  It was the stated reason for a conservative default strength; in play that
  double-darkening turned out not to be the problem the argument predicted.

### Status, and what is still unverified

**Confirmed in play** (2026-08-13/14). It took four rounds, and the sequence is
the useful part — every one of them was a *different* kind of wrong:

| round | reported | what it actually was |
|---|---|---|
| 1 | nothing visible at all | the world-position trap: drawn, then 100% of fragments discarded |
| 2 | *"the bigger the sprite, the less there is"* | a **request** for size-dependent scaling, misread as a bug report and built backwards |
| 3 | *"small triangles all around"* | the plateau from round 2 — a high-alpha ring creases along every quad diagonal |
| 4 | *"soldier still too visible by ~30%"* | not size at all: a circle covers ~3× a thin ellipse, and a standing body should be fainter anyway |

Rounds 2 and 3 were the same mistake twice: acting on an a-priori argument about
what would look right instead of on what was reported. The values that survived
(`strength 0.7`, `upright 0.7`, `sizefall 0.6`) were all settled by looking.

**Still unverified — and they are all *negative* claims**, which is why they
survive: nothing in a mirror or in water, no blob following a flying enemy or a
jumping player, none surviving into an unlit room, and no blob smearing over a
ledge. `spriteao-loud`, a cacodemon and a lift are what test those.


---

## 3. Files

| file | role |
|---|---|
| `rt_draw.cpp` | both mechanisms — the §1 shadow proxies and the §2 AO decal fan, at the bottom of `InternalDraw` |
| `hw_sprites.cpp` | the per-actor facts they run on: `m_lastthingupright`, `m_lastthinglivemonster`, `m_lastthingradius`, `m_lastthingfloorz` |
| `rt_state.h` | where those live, with the reasoning for each |
| `rt_cvars.inc` | every `rt_sprite_shadow_*` and `rt_sprite_ao_*` |
| `tools/d64rt-pins.cfg` | the shipping pins. Must agree with the compiled defaults |
| `tools/arms/sprshadow-*.cfg` | §1 arms — `off` / `on` / `probe` / `max` |
| `tools/arms/spriteao-*.cfg` | §2 arms — `off` / `on` / `loud` / `disc` |
| `RTGL/.../RsDecal.vert` | **the world-position trap** — reads §2 before touching it |
| `RTGL/.../RsDecal.frag` | the 5 cm surface test and the albedo blend §2 is built on |
| `RTGL/.../VulkanDevice.cpp` | `rayCullMaskWorld_Shadow` — the one line that makes §1's proxies shadow-only |

## 4. Troubleshooting

| symptom | look at |
|---|---|
| **no blob at all** | `.	oolsb.cmd spriteao-loud 02` and read the console. `emitted 0` = the gates rejected it (height fade, distance, scope, `floorz`); `emitted > 0` with a clean screen = a **position** bug, not a strength one. Do not touch strength |
| **triangles / facets around a blob** | something reintroduced a high-alpha ring. §2, "the blob is a single fan" — more segments will not fix it |
| **monsters read too heavy** | `rt_sprite_ao_upright`, *not* `rt_sprite_ao_strength`, which takes the props with them |
| **blob visible in a dark room** | it should be invisible — the decal multiplies albedo. If a black disc survives unlit, something is writing screen emission; check `aoprim.emissive` |
| **blob smears over a ledge** | it should stop at the edge; that is the 5 cm test. If it smears, the quad is not on `floorz` |
| **a faint cross around an actor** | §1's instance mask is wrong. This is the single failure mode that design has, and nothing new should ever be *visible* |
| **shadow gone outdoors** | `rt_sun_split` — see `moon-and-sky-leaks.md` §5.2. Sprite shadows the moon never resolved |
| **a mirror shows no blob** | expected. §2 is rasterized into the primary G-buffer only |
