# Doom 64: Unseen Evil / Retribution compatibility

## Purpose

This project supports **both** Doom 64 Retribution and Doom 64: Unseen Evil with
the same native RT engine.  They are separate content packs with incompatible
assumptions in several places, so Unseen Evil support must be opt-in through its
own launcher and overlays.  A change for one must not change the other's normal
launch path.

Run Unseen Evil with:

```powershell
.\tools\launch-unseenevil-rt.cmd
```

The launcher defaults to DOOM II MAP01.  `doom1`, a map number/name, `menu`, and
`bare` are documented at its head.  It loads `Doom64-UnseenEvil` plus only the
small compatibility overlays that belong to that mod; it does not make the
Retribution launcher load Unseen Evil content.

## What the older work established

The investigation was implemented in commits `11a2758`, `3fb8f38`, `5a34512`,
`26fdc43`, `439e6c00c`, and `c021ef9` (2026-08-15 through 2026-08-16).  It found
two different texture issues that are easy to conflate.

### 1. The mod's texture replacements were being blocked

Unseen Evil's `D64UE_Terraformer_Event` retextures stock DOOM maps during
`WorldLoaded`: it calls `level.ReplaceTextures` using its
`resources/d64ue_textures.*` mapping tables.  The RT engine's
`FLevelLocals::ReplaceTextures` deliberately returns early when `rt_mod_compat`
is non-zero.  Therefore the normal RT setting made the mod appear to load but
left stock DOOM walls in place.

This was measured on DOOM II MAP01:

| `rt_mod_compat` | Unseen Evil walls | stock walls | Unseen Evil flats |
| --- | ---: | ---: | ---: |
| `1` | 3 | 387 | 0 |
| `0` | 334 | 56 | 17 |

The Unseen Evil launcher sets `+rt_mod_compat 0` **after** the shared pins file.
That is the actual fix for the missing/wrong texture-rendering report.  It is
not a bulk conversion of texture names to Retribution names.

Despite its name, `rt_mod_compat` is not a universal compatibility level. It
is a bundle of the original gzdoom-rt mod-compatibility policies: among other
things it changes world opacity/alpha handling, removes baked sector shading
from traced albedo, enables selected brightmap and weapon-presentation paths,
and unconditionally suppresses `FLevelLocals::ReplaceTextures`. Those policies
fit Retribution but are not all valid for every mod. UE therefore keeps the
bundle off so its core Terraformer works, then restores only the renderer
behaviours it actually needs through `rt_world_white` and exact UE gates.

`rt_mod_compat` also used to keep sector lightlevel and sector colour out of
path-traced albedo. Turning it off for Unseen Evil exposed its Terraformer's
authored sector palette as an albedo tint. Commit `439e6c00c` added
`rt_world_white`, default `0`, solely to decouple this protection. This remains
correct and required, but a later white-albedo diagnostic proved that tint was
not the persistent MAP02 red illumination described below. The Unseen Evil-only
`tools/d64ue-lighting.cfg` sets it to `1`; Retribution retains its previous
behaviour because the engine default and its launcher path are unchanged.

### 2. One source mapping selected a Retribution lamp by mistake

The separate `tools/make_unseenevil_texfix.py` overlay changes exactly this
Unseen Evil table entry:

```text
FLAT2:SFLATAS  ->  FLAT2:SFLATAP
```

`FLAT2` is a widely-used ordinary grey DOOM II flat.  `SFLATAS` is a real Doom 64
lamp flat in this RT project: it has material emission and triggers analytic
ceiling-inset lights.  Thus an ordinary ceiling could become a huge light source.
`SFLATAP` is the visually related recessed grille and is intentionally not a
lamp.  The two genuine Unseen Evil ceiling-light mappings, `TLITE6_5:SFLATAS`
and `TLITE6_6:SFLATAS`, remain untouched.

So the recollection is partly right: there was a targeted correction of an
Unseen Evil mapping to a better Doom 64 texture name.  It was not the cause of
most Unseen Evil textures failing to render; the compatibility guard was.

## Compatibility overlays

All generated Unseen Evil fixes live under `Doom64-UnseenEvil/` and load *after*
`D64UnseenEvil-v1.0.3.pk3`.  They override only matching resources and never
edit the mod archive or Retribution's authored materials.

| Overlay | Generator / purpose | Required by launcher |
| --- | --- | --- |
| `d64ue-brightmap-tone.pk3` | `tone_unseenevil_brightmaps.py`; lowers 18 fully pinned brightmaps from 255 to 192 without removing their hue | Yes |
| `d64ue-texfix.pk3` | `make_unseenevil_texfix.py`; the `FLAT2` retarget above, plus (2026-08-27) the LIQUID retargets: `FWATER*`→`D64W1_01`, `NUKAGE*`→`D64N1_01`, `BLOOD*`→`D64B2_01`, `SLIME01-08`→`D64S1_01`, `LAVA*`→`HLAVA1`, so every RT liquid system keys in by name | Yes |
| `d64ue-retribution-liquids.pk3` | `make_unseenevil_liquids.py`; Retribution's liquid construction verbatim -- the ten warp patches, HLAVA1-5, the 576 `D64[WNBSL]n_nn` TEXTURES composites and their ANIMDEFS. Followed in the launcher by Retribution's own `d64r-liquid-art.wad` (coagulated blood/poison/sludge), `d64r-poison-fx.pk3` and `d64r-lava-fx.pk3`, all self-contained | Yes |
| `d64ue-monitor-lights.pk3` | `make_unseenevil_monitorlights.py`; spawns Retribution's own 9802 `PointLightFlicker` on every `SMON*` panel (one per 64-unit tile, per-family colours measured over all 34 maps) plus Retribution's SMON art and ANIMDEFS | Yes |
| `d64ue-sky-rt.pk3` | `make_unseenevil_skies.py`; bakes Unseen Evil shader skies into textures RTGL1 can draw | Optional |
| `d64ue-liquid-anim.pk3` | declares the mod's shipped water frames as animations | Optional |
| `d64ue-pickup-lights.pk3` | `make_unseenevil_pickup_lights.py`; pickup glows for the armour/health/powerup classes UE leaves unlit, in **Retribution's own GLDEFS colours** at UE's own sizes | Optional |
| `d64ue-rt-menu.pk3` | adds a **Ray Tracing** item to UE's existing Options menu | Optional |
| `d64ue-keytrim-lights.pk3` | `make_unseenevil_keylights.py`; adds Retribution-style 9800 PointLight stacks after the Terraformer | Yes |
| `d64ue-grille-emis.pk3` | `make_unseenevil_grille.py`; a brightmap cut from the mod's own SFLATAP art plus one GLDEFS line, so the grille pane glows under RT at `rt_ue_grille_emis` -- UE only, because the shared materials give that flat no emissive on purpose | Yes |
| `d64ue-retribution-hud.pk3` | `make_unseenevil_hud.py`; copies Retribution's existing SBARINFO HUD and supplies only its missing WAD dependencies | Yes |
| `d64ue-retribution-player.pk3` | `make_unseenevil_player.py`; replaces UE's shader-coloured green player masks with Retribution's traced PLAY art | Yes |
| `d64ue-muzzleflash.pk3` | `make_unseenevil_muzzleflash.py`; retains UE firing/gameplay actions while restoring Retribution's shotgun, SSG, chaingun, plasma, and Unmaker first-person frames/timing plus RT light triggers | Yes |
| `d64ue-retribution-barrel.pk3` | `make_unseenevil_barrel.py`; makes UE's replacement barrel enter Retribution's `BEXP E` explosion contract so the existing smoke, plate, scorch, and ember systems run | Yes |
| `d64rt-autolights.pk3` | experimental sector-centre point lights | Optional and disabled by config |

Rebuild a generated overlay with its tool's `--write` option.  Preserve the
load order: a same-path resource only wins when the overlay follows the mod.

## Lighting policy and boundaries

Retribution maps were authored around real 9800/9801/9802 light things and
Retribution-specific fixture detection.  Vanilla DOOM maps used by Unseen Evil
largely have baked sector light levels instead.  Do not make either system the
global answer for the other.

For Unseen Evil, `d64ue-lighting.cfg` deliberately sets:

```text
rt_sector_lights 0
rt_sector_emis 0
rt_water_glow 0.08
rt_world_white 1
rt_sector_tint_albedo 0
rt_sector_tint_lights 0
cl_rockettrails 0
```

The first two reject invented lights: sector-centre point lights produce ceiling
discs, while sector emission turns painted brightness into an ungrounded source.
The accepted result is a darker game lit by actual mod emitters and the
flashlight.  The launcher also disables Retribution's moon and map-name preset
tables, because bare DOOM map names such as `MAP22` collide with Retribution
per-map presets and Doom's sky ceilings are not authored as moon-lit openings.

Two existing Retribution components are intentionally reused. The flashlight
event handler is additive and independent of Doom 64 actors. The mugshot HUD's
SBARINFO, textures, font definition, and faces are copied unchanged into a UE
compatibility package, with only the resources it normally receives from the
Retribution WAD added. Retribution map, sky, title, blood, and material patches
remain excluded; the launcher documents each exclusion and why it is unsafe.

## First-person weapon states and RT triggers -- 2026-08-20

The missing cast light was a weapon-state problem, not another texture-name or
RT material mapping problem. The shared renderer's `RT_AddMuzzleFlash()` path
is already the path Retribution uses. It uploads the coloured analytic light
while `player.extralight > 0`; the same signal drives firing smoke and the
plasma gun-glow boost. Retribution raises it with `A_Light1` / `A_Light2` and
returns through `Weapon.LightDone`, whose `A_Light0` clears it.

Repairing only that signal was not enough. A source-level comparison against
`D64RTR_v15.WAD` found that UE also replaces the first-person presentation:

- the shotgun and SSG use shorter/different pump and reload sequences;
- the chaingun uses `CHGG A/B` plus combined `CHGG C/D` flashes instead of
  Retribution's `CHGG A-D` spin and dedicated `CHGF A-D` fire frames;
- the plasma rifle omits Retribution's `PLSF` discharge and `PLSG D-H-D`
  recovery/raise animation;
- the BFG omits Retribution's animated `BFGF H-A` green charge overlay and its
  `A_Light2` signal;
- the Unmaker uses UE's `LASR` art instead of Retribution's `UNMA` gun plus
  `UNMF` red discharge overlay.

`tools/make_unseenevil_muzzleflash.py` patches eight exact UE weapon sources.
It preserves UE's firing functions, ammo rules, projectiles, recoil calls, and
sounds, while replacing only the visual state spans. The generated archive
uses 69 Retribution presentation frames: 34 patch-namespace inputs for exact
chaingun/plasma/BFG/Unmaker `TEXTURES` composites and 35 direct
sprite-namespace shotgun/SSG frames. The complete shotgun is renamed to the
UE-private `UESG` / `UESF` families instead of reusing UE's `SHTG` objects;
this preserves Retribution's art while avoiding UE's earlier same-name
`NoTrim` declarations.
The generator requires exact source matches before writing, so a future UE
update cannot silently patch a similar-looking state.
Rebuild it with:

```powershell
py -3 tools/make_unseenevil_muzzleflash.py --write
```

Do **not** compensate by making an entire combined HUD weapon frame emissive or
adding sprite `lightIntensity`. That is a separate screen-material path and can
bleach the art or double the analytic source. This happened in UE: copied
`UNMF` inherited a global 900-intensity material light and illuminated the room
from the HUD quad, while copied `CHGF` inherited a screen multiplier that was
too bright at UE's exposure. The overlay therefore gives only those two
otherwise identical composites UE-private names (`UEMF` and `UECF`). Their
`Bright` states remain visible and `A_Light1` / `A_Light2` still drive the
analytic source. BFG uses Retribution's `BFGF H-A` charge art and green
`A_Light2` edge while retaining UE's `A_FireBFG` gameplay call.

Runtime validation used an unattended MAP02 pistol shot and quit after 105 map
tics. The trace showed the full state transition:

```text
extralight=0 -> wantFlash=0
extralight=1 -> wantFlash=1  weapon=D64UE_Weapon_Pistol
extralight=2 -> wantFlash=1
extralight=0 -> wantFlash=0
```

The later short runs confirmed the full plasma discharge/recovery art and the
Unmaker's `UNMF`-derived overlay (now named `UEMF` in the final package). At
Unmaker tic 110 the trace showed
`weapon=D64UE_Weapon_Unmaker extralight=1`. A subsequent comparison found that
the ordinary muzzle source illuminated the world but did not reliably wash the
first-person gun. The engine now borrows the existing geometry-derived weapon
glow anchor for the exact UE Unmaker class during that same three-tic
`extralight` edge. It is red, centimetres in front of the actual `UNMA` quad,
and cannot activate for Retribution. Because the archive is referenced only by
`launch-unseenevil-rt.cmd`, Retribution also keeps its original states and
never loads UE source.

## Projectile and remaining weapon parity -- 2026-08-20

These three reports looked related on screen but came from three independent
compatibility gaps. None is fixed by broadening a global texture prefix.

### Unmaker firing light and wall arcs

Retribution and UE implement the weapon differently:

- Retribution fires a speed-200 `UnmakerLaser : FastProjectile`. Its visible
  trail is a large set of `UnmakerLaserTrail` actors using `UNML` / `LPUF`
  sprites. Those sprite names already carry red RT material lights. Its weapon
  Flash state also calls `A_Light1`, so the shared analytic red source exists at
  the muzzle immediately and illuminates the view weapon. When the projectile
  dies, `rt_impacts.cpp` sees the dead `UnmakerLaser`, probes the nearby surface,
  and creates the persistent `rt_laser_*` red burn and arcs.
- UE performs an immediate ZScript `LineTrace`, draws a model actor named
  `D64UE_UnmakerBolt`, and places `D64UE_UnmakerPuff` at the hit position. It
  never creates either Retribution class or any `UNML` / `LPUF` primitive, so
  both the material light and the impact event were absent.

An initial UE repair attached one ordinary point light to `D64UE_UnmakerBolt`.
That interpretation was wrong: UE spawns the bolt actor at the midpoint of the
entire traced beam, then advances it toward the hit point. The light therefore
appeared late and downrange and could not illuminate the gun. The attachment
has been removed. The compatibility overlay now uses Retribution's `UNMA` gun
and `UNMF A 3 BRIGHT A_Light1` state while retaining UE's
`A_D64_FireLaser()`. `RT_AddMuzzleFlash()` supplies the immediate world light,
and its existing per-weapon class match selects `rt_mzlflsh_color_unmaker`.
That source is not close enough to the rasterized first-person quad to recreate
Retribution's red wash on the weapon itself, so `RT_AddWeaponGlow()` also uses
the captured `UNMA` quad anchor for exact `D64UE_Weapon_Unmaker` while
`extralight > 0`. The gate is UE's isolated identity pair plus exact class;
the passive plasma glow is unchanged and Retribution cannot enter the new arm.

`rt_impacts.cpp` now accepts the exact class `D64UE_UnmakerPuff` as the second
door into the existing laser-impact implementation. The alias is enabled only
for UE's isolated pair (`rt_mod_compat 0` and `rt_world_white 1`); Retribution
still enters through its unchanged dead-`UnmakerLaser` test. MAP02 runtime
validation produced two real surface events while firing:

```text
rt_laser: IMPACT at 34.50 50.75 0.91 n -0.00 -1.00 0.00 (tic 91)
rt_laser: IMPACT at 34.50 50.75 0.91 n -0.00 -1.00 0.00 (tic 99)
```

The first capture shows the compact red impact pool on the struck panel; the
later captures show it cooling. Arc count, lifetime, colour, surface probe, and
smoke remain the same `rt_laser_*` implementation Retribution uses.

The final implementation separates all three roles instead of asking one HUD
quad or one midpoint light to do everything:

- `UEMF A 3 Bright A_Light1` provides the immediate muzzle/gun illumination;
- `rt_draw.cpp` gives only `models/beam_unmaker.png` a screen-emissive,
  no-shadow primitive override;
- `RT_UploadUnseenEvilProjectileLights()` reconstructs the stretched model's
  current direction and length and distributes three red analytic samples
  along it.

UE originally retracts the visual actor by 32 map units per tic. At the low
frame rates used for path-traced captures, it can complete between two rendered
frames even though the hitscan shot and impact are visible. The overlay lowers
only this visual step to 12 units per tic. Damage is resolved by the preceding
`LineTrace`, so this changes presentation duration but not aim, damage, ammo, or
impact location. Every part is guarded by the existing UE identity pair and
exact asset/class names; Retribution keeps its original UNML trail and lights.

The final UE view-weapon placement is intentionally not byte-for-byte
Retribution. UE's `D64UE_Weapon_Base.CORRECTASPECT` applies another psprite
transform after the composite offset. With Retribution's original `-113` Y
offset, `screen/unmakerSpriteCut.png` left the gun roughly 20 logical pixels
above the bottom edge. Only the UE overlay changes UNMA/UEMF to `-133`; their
relative alignment remains identical. `UEMF` keeps its red art visible for the
full 11-tic Fire/refire span, but calls `A_Light0` after the original first
three tics, so the longer red cap does not prolong the analytic room light.

### Rocket smoke while in flight

The engine's volumetric tracker was not failing to recognise UE. Runtime showed
the actual projectile class is `CheelloRocket`, from gzdoom-rt's built-in voxel
package, not UE's declared `D64UE_Rocket`. It still matches the existing
case-sensitive `"Rocket"` row and generated eleven two-tic trail parcels before
the impact burst:

```text
rt_smoke PROJECTILE: tracking CheelloRocket ... (tic 99)
rt_smoke PROJECTILE: burst ... (tic 121)
```

What the replacement chain bypasses is UE's own projectile state:
`D64UE_Rocket` calls `A_D64_SpawnSmoke()` and attaches a small orange light,
while `CheelloRocket` does neither. In UE's intentionally dark maps the engine
parcels were therefore present but nearly unlit until the explosion, matching
the report that impact smoke existed while the trail did not.

`RT_UploadUnseenEvilProjectileLights()` restores the light UE authored: exact
live class `CheelloRocket`, colour `#C43F21`, radius 20, positioned 32 map units
behind the missile where the newest smoke parcel is dropped. It obeys the
existing `rt_dynlight` intensity/radius/minimum/maximum controls and is gated by
the UE compatibility pair. Retribution cannot enter the function and retains
its material-lit rocket without a doubled source. Do not attempt to repair this
with `replaces CheelloRocket` in a content overlay: engine ZScript defines that
class after mod ZScript is compiled, so the replacement target does not exist at
that stage.

The little grey squares were a second, independent trail. `CheelloRocket`
inherits GZDoom's stock `+ROCKETTRAIL`, and `cl_rockettrails 1` draws those
raster particle billboards even while the RT volumetric parcels are present.
`d64ue-lighting.cfg` now sets `cl_rockettrails 0`; the shared pins explicitly
restore the normal value `1`, so the suppression applies only after the UE
launcher runs its own config. `rt_smoke_rocket` remains enabled. The automated
rocket/barrel capture fired before the longer weapon switch completed, so the
square-free trail still needs a normal-play visual check; the two independent
configuration paths and the live volumetric class match are verified.

### Chaingun, plasma, and shotguns

The final overlay uses the complete Retribution presentation rather than a
single substituted frame. Chaingun Fire alternates the original `CHGG A-D`
spin cycles and `CHGF AB/CD` flash pairs. Plasma uses `PLSF B/A` for discharge
and the full `PLSG D-E-F-G-H-G-F-E-D` recovery. The shotgun and SSG use the
original long `SHTG` and `SH2F B-S` pump/reload sequences and their `SHTF` /
`SSGF` flash art. UE's actual firing calls remain in the action blocks.

The final package audit passed with eight patched sources and all 69 borrowed
art files, including BFG. Plasma was captured live with the full blue discharge
and gun animation. Chaingun and both shotguns are source/package verified but
still need a normal-play feel check; no result from a different selected weapon
is counted as visual evidence.

The first package incorrectly wrote every retrieved WAD lump to `patches/`.
That namespace is correct only when a copied TEXTURES composite consumes the
image. A weapon state resolves raw art through the sprite namespace. UE happened
to supply SHTG A-H itself, hiding most of the mistake; SHTG I/J disappeared,
while the new SH2G/SH2F SSG sequence had no resolvable frame and vanished for
its complete firing animation. A first correction added only the 27 missing
raw frames and retained UE's own SHTG A-H, but that was not a full visual
replacement: their art and aspect treatment still differed from Retribution.

The final generator writes all 35 direct frames under `sprites/`. Retribution's
SHTG A-J and SHTF A-B are renamed to `UESG A-J` and `UESF A-B`, while SH2G,
SH2F, and SSGF retain their names. The normal shotgun's complete Ready through
Flash span uses those aliases and removes UE's `CORRECTASPECT`, because
Retribution's raw sprites already use their native psprite aspect. Unique names
are essential: placing the same-name SHTG A-H raw files late in the load order
makes UE's earlier `TEXTURES.weapons` `NoTrim` directives fail with
`NoTrim: SHTGA0 is not a sprite` before our TEXTURES lump can run.

The SSG deliberately keeps UE's correctly aligned resting SHT2 frame and its
aspect hook. Only its borrowed firing animation was high, so Fire temporarily
sets the psprite Y offset from 32 to 52 and restores 32 immediately before
returning to Ready. The restore belongs after the final two `SH2G A` recovery
states; placing it before them made the last three tics jump upward. This is
state-local and does not move the resting weapon or any other weapon.

The chaingun fire composites use the UE-private `UECF A-D` aliases described
above. This is the same Retribution art, placement, and two-pair cadence, but it
does not inherit the globally authored `CHGF` screen multiplier that made UE's
muzzle card excessively bright. The alias also revealed an engine split:
`hw_weapon.cpp` made bright flash layers additive only when `rt_mod_compat` was
enabled, while UE must disable that cvar for its Terraformer. Under UE's exact
identity pair, only `PSP_FLASH` now regains additive composition. The red/yellow
flame art is submitted as a separate additive card again, without restoring
CHGF material emission; its
`A_Light2` world source is unchanged.

A minimized MAP02 slot-4 autofire run confirmed the split at the renderer
boundary: the `CHGG` weapon body logged `destalpha=3, emis=0`, while the live
`UECFC0` flash logged `destalpha=1, emis=0.150`. The one-tic flame is therefore
on the Flash layer rather than baked into or emitted by the gun body.

### BFG charge

UE's original BFG state held `BFGG A` and commented out the light calls, so it
had neither Retribution's animated green charge overlay nor green illumination
on the weapon and nearby geometry. The compatibility span now uses original
`BFGG A-E` and `BFGF H-A` art/timing, raises `A_Light2` for the eight charge
frames, clears through `A_Light0`, and still invokes UE's own `A_FireBFG`.
Projectile behavior is therefore unchanged and Retribution never loads the
span.

### Exploding barrels

UE's replacement barrel used `BAR1 BC`, exploded on `BAR1 D`, and immediately
reached `Stop`. Retribution and both RT barrel systems deliberately use the
rising edge of `BEXP E`: `RT_BarrelSmoke()` emits the volumetric burst there,
while `BarrelWalkActor()` creates the authored plate, floor scorch, and ember
bed independently of the smoke cvar. The mismatch explains why UE's prop simply
vanished and why none of the finished Retribution work appeared.

`tools/make_unseenevil_barrel.py` creates a separate UE-only overlay. It keeps
`D64UE_ExplosiveBarrel`'s health, radius, height, damage type, and replacement
identity, but uses Retribution's exact `BEXP A-E` frames/timing and the matching
`BarrelExplosion64` fade sequence. The final short run killed that real UE
class with the Unmaker and logged, on the same tic:

```text
rt_smoke BARREL: burst ... (tic 127)
rt_barrel: BLAST D64UE_ExplosiveBarrel ... (tic 127)
rt_barrel: 60 shards ... (pool 60)
```

The capture also shows the explosion animation instead of an instantaneous
disappearance. Retribution never loads this overlay and continues to enter the
same renderer systems through its original `64ExplosiveBarrel` state.

## Rules for future changes

1. Keep Unseen Evil options in `launch-unseenevil-rt.cmd`, `d64ue-lighting.cfg`,
   or an Unseen Evil overlay.  Do not add them to the Retribution launcher.
2. Keep engine behaviour safe by default.  A global engine cvar used only by
   Unseen Evil must default to the pre-Unseen-Evil behaviour and be pinned by
   the Unseen Evil launcher/config (as `rt_world_white` is).
3. Before changing a Terraformer mapping, distinguish a blocked
   `ReplaceTextures` call from a bad mapping.  Inspect the source table and the
   RT fixture/material classification; do not select a replacement by image
   similarity alone.
4. Keep the source mod immutable.  Make a minimal later-loading overlay and
   make its generator fail loudly if the upstream entry no longer matches.
5. Test both launchers after an engine-side compatibility change:

   ```powershell
   .\tools\launch-unseenevil-rt.cmd 1
   .\tools\launch-retribution-rt.cmd 1
   ```

6. Log engine changes in `compat-patches.md` and update the living project plan
   when the files exist on the active branch.

## Short-run validation — 2026-08-20

The current `unseenevil` branch was checked with the rebuilt engine and all
generated overlays present. Later captures use `rt_autoshot 100` and
`rt_autoquit 150`, giving live geometry and the denoiser time to settle while
keeping each minimized game run to a few seconds.

| Check | Result |
| --- | --- |
| Overlay audit | Passed: the 18 brightmap edits preserve hue/mask shape; the texture-fix generator makes only `FLAT2:SFLATAS -> SFLATAP`; all baked-sky inputs are readable. |
| Unseen Evil MAP01 | Passed: the Terraformer architecture and props render rather than stock DOOM textures; the level stays deliberately dark with `rt_sector_lights 0` and `rt_sector_emis 0`. The outdoor orange sky is visible again without becoming indirect interior light. |
| Unseen Evil MAP02 | Passed: replacement textures and `WATERA`/`WATERB` RT-water tagging are live; `rt_water_debug 1` paints only the pool magenta, proving the stylized shader branch rather than JSON metadata is active. The normal UE run retains a modest visible water sheen. |
| UE RT menu / HUD | Passed: RT labels and live values render instead of raw `RTMNU_*` keys. The active HUD is Retribution's unchanged SBARINFO layout: BATTERY/HEALTH/mugshot left and keys/ARMOR/AMMO right; BATTERY follows the same integer scale. |
| UE key actors | Runtime wiring passed: MAP02 found 24 transformed faces and spawned 72 ordinary PointLights, and the close capture proved they cast onto geometry. That capture was over-bright; the final quarter-flux narrow-face rule and 0.5 surface multiplier were applied after the fifth permitted launch and remain the first visual check for the next iteration budget. |
| UE player muzzle flash | Passed: a real MAP02 pistol shot raised `extralight` 0 -> 1 -> 2, activated the shared RT muzzle source, spawned firing smoke, visibly lit nearby geometry, returned to 0 through `LightDone`, and auto-quit. |
| UE weapon presentation | Plasma captured Retribution's blue `PLSF` discharge and recovery sequence. The final package statically verifies Retribution's BFG charge, UE-private chaingun/Unmaker flash aliases, immediate analytic light states, the slowed visual-only Unmaker beam, and all 35 shotgun/SSG raw frames in the sprite namespace. Full Retribution shotgun art uses collision-free `UESG`/`UESF` aliases with UE's aspect hook removed; the SSG applies a firing-only +20 Y offset through its final recovery states and preserves its correct rest position. UE's exact `PSP_FLASH` layer regains additive composition, restoring the chaingun's red/yellow flame without CHGF material emission. Unmaker retains `CORRECTASPECT`, uses a UE-only 20-pixel lower art offset, keeps the red cap visible after its three-tic analytic light ends, and gains a separately gated three-tic red light at the actual weapon quad. The generated PK3 passed a short startup/parser run; a final normal-play visual check remains appropriate. |
| UE exploding barrel | Passed: a real `D64UE_ExplosiveBarrel` reached `BEXP E`; one tic produced the visible explosion, six volumetric burst parcels, the floor/scorch event, and all 60 authored shard pieces. |
| UE rocket raster trail | Implemented and statically verified: UE alone pins `cl_rockettrails 0` while `rt_smoke_rocket` remains on; a normal-play square-free trail capture is pending because the automated shot occurred during weapon selection. |
| Retribution MAP01/MAP02 | Passed after the UE changes: MAP01 keeps its original RT lighting/HUD path; MAP02 retains `D64RtSkyFix: MAP02 sky -> SKYMTNA` and its own scene identity. |

The Unseen Evil archive still reports its pre-existing ZScript deprecation
warnings, two unresolved brightmap references, and MAP30 model-material
warnings at startup.  They did not prevent MAP01 or MAP02 from loading,
rendering, capturing, and quitting.

The corresponding Retribution short-run capture remains the first regression
check for the next iteration budget.

### MAP02 red-wash result — 2026-08-20

There were two red contributions, but the first was initially diagnosed
incorrectly. The runtime `whatsthat` result in the reported view is sector 38,
texture `STRAKR`. UE's own texture rules map a 16-wide `DOORRED` pillar to that
name on all four faces, and UE's `GLDEFS.brightmaps` assigns it the wide red-key
mask. It is a real key fixture and must not be excluded.

The important correction is that Retribution never asked the key texture to
light the room. Its base WAD already contains six ordinary type-9800
`PointLight` things at a locked-door recess, arranged as two vertical stacks of
three. `RT_UploadGzDoomDynamicLights()` forwards those actors and explicitly
attenuates co-located stacks. The texture brightmap has the separate job of
making every painted inlay pixel visibly glow.

UE transforms IWAD maps at runtime and those maps contain no Retribution light
things. `d64ue-keytrim-lights.pk3` therefore waits until the Terraformer has
finished, finds the final STRAKR/B/Y and full-path key-trim faces, and spawns the
same three-`PointLight` actor stack in front of each face. A narrow four-sided
pillar exposes one fixture on four faces, so each stack receives one quarter of
the RGB energy; wider jambs remain full energy. The UE launcher pins the old
engine analytic key-light path off. The attempted mask-shaped eleven-sphere
approximation and its dedicated radius were removed.

The global PBR catalogue also labels STRAKR's metal/roughness without an
`emissiveMult`, which caused RTGL to overwrite the UE brightmap fallback with
zero. UE world brightmaps now claim the emissive override flag under the
existing isolated compatibility pair. `rt_ue_keytrim_emis 0.5` matches
gzdoom-rt's stock brightmap fallback and is surface emission only, still shaped
by UE's exact mask. The PointLight actors provide the cast illumination. Both
paths are gated away from non-key brightmaps and Retribution.

That removed the initial orange blast but **not** the settled room wash. The
remaining source was an RT scene-name collision:

- UE transforms the IWAD's MAP02 at runtime, so `RT_MapName` was still `map02`.
- RTGL matched the unrelated `map02` row in `rt/data/scenes.json`.
- `SceneMetaManager::Modify` applied that row *after* frame parameters and forced
  sky intensity to `400`, which is why even `+rt_sky 0` initially appeared inert.
- UE's red sky environment then leaked through non-watertight IWAD geometry and
  illuminated the sealed start room and water.

The engine namespaces this existing UE compatibility combination as
`d64ue_<mapname>`. That prevents the unrelated scene row from changing UE's
frame parameters. RTGL now also separates primary sky visibility from indirect
sky radiance: the launcher restores `rt_sky 25`, while UE sends
`skyLightingMultiplier = 0` only for its isolated compatibility pair. MAP01's
orange sky is therefore visible outdoors, but an indirect ray escaping through
unsealed DOOM geometry contributes no dome light indoors. Retribution keeps
multiplier 1, its name, scene metadata, sky, and lights.

The isolation ladder ruled out the tempting alternatives: the wash survived
white albedo, `rt_emis_mapboost 0`, screen emission zero, all uploaded light
families off, and volume off. After the namespace fix, a settled zero-lighting
capture removed it while cyan/green emissive and analytic sources remained.
SFLATAI/SFLATAB are mildly warm in the source art, but their measured colour was
far less saturated than the rendered wash and was not replaced.

The shared auto-exposure floor remains unchanged. Raising it neither removed the
red sources nor respected the flashlight, which became visibly too dim.

### MAP02 monitor light gap - 2026-08-20

The user's last `whatsthat` was sector 28, wall texture `SMONDD`, at lightlevel
240. Its authored `SMONDD_e` mask and `emissiveMult: 2.8` are present, but they
only make a surface glow; they do not cast light. Retribution supplies a real
map-authored 9802 light for its monitor panels. Unseen Evil's DOOM II map does
not, so there was no source to upload.

`rt_lights_fixtures.cpp` now detects Unseen Evil's `SMONDA` through `SMONDD`
only under `rt_mod_compat 0` and uploads cyan analytic wall lights. A short
MAP02 run confirmed 12 uploads under the existing 128-light wall-fixture cap,
while `rt_sector_emis` remains zero. The Unseen Evil config also reduces water
reflectance (0.02 down-facing / 0.25 grazing). The UE indirect-sky policy does
not touch these real monitor lights.

### UE material, water, and menu follow-up - 2026-08-20

`rt_mod_compat` bit 1 normally turns an active GZDoom brightmap/glowmap into an
RT emissive mask. UE must set the whole cvar to `0` so its Terraformer can call
`ReplaceTextures`, which accidentally disabled the fallback as well. The renderer
now restores that one brightmap fallback only when UE's dedicated launcher pair
is active (`rt_mod_compat 0` plus `rt_world_white 1`). It also applies the same
unlit-albedo protection to UE sprites, preventing their sector palette from
tinting pickup and emissive artwork. That gives UE's authored blue health-vial
art, keys, panels, pillars, doors, and other brightmapped elements their visual
emissive masks again; it does **not** invent point lights for arbitrary walls.

The existing water engine tags were already correct (`WATERA` and `WATERB` are
logged as `RG_MESH_PRIMITIVE_WATER`); the UE config had deliberately zeroed
`rt_water_glow`, making the live shader read as black in unlit rooms. It now uses
the restrained `0.08` value. `rt_water_debug 1` is the validation instrument.

UE replaces the same main and skill menu definitions that the RT WAD attempts to
replace, so the RT WAD's old direct main-menu link is not usable there. UE's
custom ListMenu drawer also paints `TextItem.mText` itself, which bypasses
`TextItem_RT.Draw()` and produced the raw `RTMNU_*` screen in
`screen/messedUpRayTracingMenu.png`. The late-loading `d64ue-rt-menu.pk3`, built
by `tools/make_unseenevil_rtmenu.py`, preserves UE's main-menu class and routes
its Options item to a compact RT page with the stock ListMenu drawer. **Other**
links onward to base GZDoom Options, matching the Retribution hierarchy.

The normal UE launcher now uses Retribution's HUD instead of imitating it.
`tools/make_unseenevil_hud.py` copies `d64r-mugshot.pk3` wholesale, including
its SBARINFO, TEXTURES, FONTDEFS, and mugshot faces. It adds only the eight HUD
font glyphs, six key icons, `IsPlaying`, and three harmless automap inventory
token definitions that package normally receives from `D64RTR_v15.WAD`. The
result keeps BATTERY, HEALTH, and the mugshot on the left and keys, ARMOR, and
AMMO on the right.

The flashlight overlay was already authored for that same Retribution
ForceScaled SBARINFO. No UE-specific scale or placement calculation is needed:
the unchanged battery code follows the same integer clean factor as the copied
HEALTH, mugshot, ARMOR, and AMMO layout. The short capture confirmed the
requested arrangement and equal glyph scale.

### UE player sprite and close-wall green bounce - 2026-08-20

`screen/playerSpriteUE.png` identified the source rather than merely another
lighting symptom. UE does not store normal player art in its `PLAY*` sprite
files. It stores a flat colour mask there and reconstructs the visible sprite
with `shaders/d64ue/playercolor.fp`, using a second image under
`resources/player/`. For example, every one of the 1,439 visible pixels in UE's
`sprites/player/PLAYA1.png` is exactly `(119,255,111)`. The matching resource
image has 72 visible colours. RTGL1 does not run GZDoom fragment shaders, so it
traced the flat green mask as the player surface. That is the green rectangle in
the menu preview and a direct explanation for green indirect colour when the
player is pressed against a wall.

This is separate from the crossed sprite-shadow mechanism. A shadow proxy uses
the reserved shadow-only instance mask and cannot contribute albedo or indirect
light. It can duplicate the malformed player's silhouette, but it cannot create
the green bounce. Replacing the source sprite fixes both the bad surface and the
shape fed to the ordinary player shadow path without weakening other lights,
emissives, exposure, or the flashlight.

The shipping proxy gates also reject `FirstPerson` and `FirstPersonViewer`
before proxy submission, and `d64rt-pins.cfg` keeps
`rt_sprite_shadow_scope 1` (live monsters only). The UE player is therefore not
an eligible crossed-proxy actor in the normal configuration. No sprite-shadow
or AO cvar was changed for this repair.

`tools/make_unseenevil_player.py` builds the late-loaded
`d64ue-retribution-player.pk3` without modifying either mod:

- all 50 `PLAY*` entries are byte-for-byte copies of Retribution's PNG lumps;
- UE's 35 `PLYC*` crouch names alias the corresponding Retribution `PLAY*`
  frames, because Retribution has no separate crouch sprite set;
- the already-registered UE player shader is replaced by GZDoom's normal
  `ProcessTexel()` material path, so raster and RT select the same art.

The existing `d64ue-rt-menu.pk3` now owns the menu half. Its additive
`D64UE_RT_CustomizationMenu` subclass removes the tab named Player, recentres
the remaining Gameplay/Aesthetics/Music tabs, and is the destination of the
Customization main-menu item. This does not depend on replacing a script
included from inside UE's archive.

The package is loaded only by `launch-unseenevil-rt.cmd` and is part of the
launcher's `bare` exclusion. Retribution's launcher and content are untouched.
Static verification passed for all 50 exact frame copies, all 35 crouch aliases,
the Player-tab routing, and the normal shader. Runtime visual validation is
intentionally pending the next short-run allowance.

## Primary implementation references

- `tools/launch-unseenevil-rt.cmd`
- `tools/d64ue-lighting.cfg`
- `tools/make_unseenevil_texfix.py`
- `tools/make_unseenevil_keylights.py`
- `tools/make_unseenevil_hud.py`
- `tools/make_unseenevil_player.py`
- `tools/make_unseenevil_muzzleflash.py`
- `tools/make_unseenevil_barrel.py`
- `tools/arms/ue-barrel-probe.cfg`
- `tools/make_unseenevil_skies.py`
- `tools/tone_unseenevil_brightmaps.py`
- `sourcecode/gzdoom-rt/src/playsim/p_sectors.cpp`
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_draw.cpp`
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_lights_fx.cpp`
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_impacts.cpp`
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`
- `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_cvars.inc`
- `deps/RTGL/Source/Shaders/RaygenCommon.h`

## Lighting Unseen Evil's own fixture art (2026-08-27)

The launcher's autolights block states the cost plainly: DOOM 1/2 maps carry no
light things, so under RT they are dark, and both invented schemes (per-sector
PointLights, `rt_sector_emis`) were tried and rejected because they light a room
with no fixture anywhere near the light.  The rule that came out of it is *only
real emitters light these maps*.

This is the other half of that rule.  Unseen Evil paints plenty of real emitters
— lit ceiling panes, blinking door indicators, switch lamps, wall light strips —
and every one of them was dark, because **every fixture classifier in this
renderer keys off Doom 64 texture names and the Terraformer replaces DOOM's walls
with art that uses none of them**.

Two features, both gated on `RT_IsUnseenEvil()` (`rt_mod_compat 0` **and**
`rt_world_white`, the pair only this mod's launcher sets — the same identity
`RT_UnseenEvilMonitorHue` already used, now factored into one helper).

### SFLATAP as a ceiling pane — `rt_ue_grille_lamps`

`RT_IsCeilingInsetLampTexture` refuses SFLATAP, and **still does**: it is a
recessed grille, the base game does not light it, and Retribution's own maps use
it 33 times.  That refusal is about Retribution's content, not about the texture.

Under Unseen Evil the same flat is a different job.  The Terraformer sends
`CEIL3_4`, `CEIL1_2`, `CEIL1_3`, `TLITE6_1` and `TLITE6_4` onto it — and `FLAT2`
too, once `d64ue-texfix.pk3` is loaded — so it covers **445 ceiling/floor
placements across 37 maps**, of which **121 are DOOM's own `TLITE6_*` ceiling
LIGHT panels** arriving dark.  Counts from
`tools/export_unseenevil_textures_gallery.py`, which replays the Terraformer over
both IWADs.

It joins `SoloBulbTextures` with a `ueOnly` flag, at a **measured** offset: flood
the panel at 72% of peak luminance and its 248 texels centroid at (31.84, 31.87),
bbox 18..45 on both axes.  That is the tile centre, so the ceiling-flat Y flip is
a no-op here — luck, not licence; the next texture added there needs the flip
applied for real.

**Note the tension, and that it is deliberate.**  `d64ue-texfix.pk3` exists to
move `FLAT2` *off* a lamp flat, because an ordinary grey DOOM II ceiling acting as
a light is exactly the invented-light failure this project keeps rejecting.
Lighting SFLATAP puts light back on those 47 `FLAT2` placements — but as one small
solo bulb per 64-unit tile through a grille, not as an SFLATAS pane.  If that
still reads as too much, `rt_ue_grille_lamps 0` is the switch, and the texfix's
own decision is untouched either way.

### Door indicators, switch lamps and light strips — `rt_ue_fixture_lights`

`tools/gen_ue_fixture_lights.py` measures the mod's art and writes
`rt_ue_fixture_lights.h`; `RT_UploadSwitchLights` consults it beside Retribution's
own table.  A **separate** table, not extra rows in `rt_switch_lights.h`, because
`gen_switch_lights.py` rewrites that file wholesale and would destroy them.

**Nothing about the animation is modelled**, and that is the whole design.  The
walk already asks `TexMan.GetGameTexture(id, /*animate=*/true)` — the frame on the
wall this instant — so the table is keyed on that frame's own name and a frame
with no row emits nothing.  The door pulse (a 4-frame ANIMDEFS ping-pong,
`_0 _1 _2 _1` at 7 tics), a switch lighting only once thrown, and a strip's steady
burn are one lookup with no phase arithmetic and no state.

Masks come from **the mod's own GLDEFS brightmaps** wherever it ships one (22 of
27 measured textures), falling back to a colour heuristic otherwise; each row
records which.  Two traps the measurement catches, both of which invert a blink if
assumed:

- `d64_bigdoor`'s frames are **not** ordered by brightness — its ANIMDEFS is keyed
  on `_0` and runs `_0 -> _2 -> _1 -> _2`, with `_0` the brightest and `_1` dark.
- An **empty or absent** brightmap is an answer, not a miss: `d64_beigedoor_0`
  ships an all-black one and `d64_bigdoor_1` ships none, because both are the off
  frame.  Guessing from the albedo there invents a light on the one frame whose
  job is to be dark.

A switch earns its row by **getting brighter**: only the `on` half of a SWITCHES
pair is measured, and only where its lit energy beats the `off` half, so a lever
that changes pose rather than light gets nothing.  30 switches qualified;
`d64_skullswitch_on` is measured red, everything else green.

Intensity is normalised differently from Retribution's rows and has to be: those
are 7–70 lit texels because they are all switch faces, these are 17–3328 because a
full-height strip is a fixture too, and through the `/7` rule `d64_lite_wide` came
out at 21.8x — a corridor lamp brighter than the sun.  The UE family is measured
against a door indicator's ~64 texels and capped at 3x.

**Verified live**, not by compiling: MAP12 reports `solo 59 flat(s)` — matching the
export's static count of 59 SFLATAP placements on that map exactly — and
`D64_SILVER72SWITCH_ON` logs `LIT` while `*_OFF` switches log `no row`.  On MAP01
the exit door's indicator logs `x0.65`, then `x1.00`, then drops out entirely: the
blink, in the log.  `rt_switch_light_debug 1` prints placements;
`RT_UeFixtureLightFor` tags each distinct Unseen Evil texture once per session,
hit **or** miss, so "this map has no fixtures" and "every lookup missed" can never
again look identical.

### The lookup trap that made this look like it did nothing

First landing, the report was *"I see zero difference"* on MAP01 — and the table
was matching, just not much of it.

**GZDoom fills `FGameTexture::Name` only for a pk3 texture whose basename fits the
classic 8 characters.**  Unseen Evil's art mostly does not.  `C201` and `SPACEAU`
out of `textures/d64/` arrive named; `d64_metal7`, `d64_talldoor_2` and
`d64_greydoor_0` arrive with an **empty name** and are reachable only through the
file they came from.  Its `TEXTURES` composites are a third case again: the name is
the declared path, extension and all absent.

Keyed on the name alone, the table matched exactly the composites — every switch,
and the exit door — and silently missed every plain PNG, which is most of the
doors and **all fourteen light strips**.  On MAP03 that was 0 lights where there
should be 15; the walk reported seeing 12 distinct wall textures in a level that
has 42.

`RT_UeFixtureLightFor` now falls back to
`fileSystem.GetFileFullName( gtex->GetSourceLump(), false )`, which is what the
generated table's path rows match, cached per `FGameTexture*` because a filesystem
call three times per sidedef per frame is not free.

Two diagnostic lessons worth keeping, both of which delayed finding this:

- **A filtered census cannot answer "what does this arrive as."**  The first
  version only logged names that already looked like this mod's art, so a name the
  filter rejected was indistinguishable from a name the walk never saw.  Under
  `rt_switch_light_debug` the filter now comes off and every wall texture in the
  level is listed once.
- **A texture with no name is not a non-event.**  Skipping nameless textures
  before logging is what made an entire family invisible; they are now reported by
  their FILE.

After the fix, MAP01 goes from 32 distinct textures seen and 3 lights to 54 seen
and 6 wall lights (plus 34 grille lights), with `d64_lite_thin` and the blinking
`d64_widedoor` now lit; MAP03 goes from 0 to 15, `d64_metal7` (149 placements on
that map) among them.

**MAP01 is still a thin place to judge this.**  It carries only 13 lit fixture
placements in the whole level and its exit door is at the far end, while three
`SFLATAQ` ceilings already flood it with the bulb lattice's full 1024-light budget
(`rt_ceiling_edge: uploaded=1058 of 1072 wanted (cap 1024)`).  For a map where this
work dominates rather than competes, use E2M7 (194 lit placements), MAP03 (162,
mostly `d64_metal7` strips), E2M2 (95), MAP24 (91), MAP10 (90) or MAP12 (62, of
which 59 are SFLATAP).

### Second round: white lights, point lights, and half-dark fixtures

Three more defects, all found from play reports rather than from the log, and all
of them things the counters said were working.

**The green indicators rendered WHITE.**  The hue was a flat average over the lit
mask, normalised so the brightest channel hit 255.  But an LED is painted as a
blown-out near-white core inside a saturated rim, so the average came out
`#7eff7e` — 46% white — and at any intensity a path tracer draws that as a white
light.  Fixed in two steps, both in `hue_hex`: weight each texel by its own
saturation so the rim decides the hue and the core barely votes, then lift the
remaining achromatic component.  The lift is **gated on the measured saturation**
(≥ 0.25) so it cannot invent a colour: `d64_lite_thin` (0.15) and `d64_silver2`
(0.11) are genuinely warm whites and are left alone, while the doors go
`#7eff7e → #1dff1d` and `d64_lite_blue` goes `#7caeff → #186aff`.

This is the trap `RT_KeyTrimHue` already records — *"an averaged colour comes out
grey and defeats the entire purpose"* — reached from the art instead of from a
hand-written table, so it still tracks if the art changes.

**A light strip was one bright dot.**  Strips were being placed like a door
indicator: one sphere per texture repeat, capped at four, at
`rt_switch_light_radius`'s 0.06 (1.9 map units).  On a 16-texel-wide strip that
put all four lights inside the first 64 units of the wall and left the rest dark —
which reads exactly as somebody dropping a dynamic point light on the wall.

Strips now carry a `band` flag and are walked as a **chain**: a segment every
`rt_ue_strip_seglen` (48) along the whole sidedef, at `rt_ue_strip_radius` 0.35 —
wide and soft so the pools blend — and a flat `rt_ue_strip_intensity` per segment,
so a longer strip emits more total light.  The area scale is **not** applied to a
band, because on a chain the fixture's size is already expressed by how many
segments it emits.  This is the shape `RT_UploadWallStripLights` settled on and the
values are matched to it.

*Why not just make the texture emit light?*  Because it cannot.  Under RTGL1 an
emissive surface casts nothing — `rt_wall_strips` states it outright — and
`RgLightPolygonalEXT`, a real area light, is compiled out behind
`#if TRIANGLE_LIGHTS` and hard-errors on upload.  A chain of overlapping spheres is
the whole of what is available.

**Twelve fixtures were lighting only half of themselves.**  `d64_widedoor` has a
gem near the top *and* a bar near the floor; `d64_silver2` has two rows of
rectangles; `d64_d1liteblu1` has two lines; five switches have two lamp rows.  The
lookup used `unordered_map::emplace` per row, which keeps only the first — so the
second band of each went dark with no error anywhere.  That is what *"some door
green lights are ok, some not"* looks like from inside the game.  The map now holds
a vector per key and every band is placed.

Also this round: door and switch lamps got their own `rt_ue_fixture_radius` (0.14,
against the 0.06 tuned for Retribution's tiny SWXC eyes) and their intensity
dropped 70 → 45, and `rt_ue_fixture_max` (320) was added because a chain wants far
more slots than `rt_switch_light_max`'s 48 — the first corridor was eating the
whole budget.

**Tuning:** `tools/ab-ue-fixtures.cmd` — `off | on | soft | bright | strips |
doors | grille | marks`, followed by a map.  Every arm sets every cvar the feature
owns, so a stale ini line cannot decide an arm.  `marks` is the one that answers a
placement report: a cyan sphere at every light this system uploads, so a light
sitting below the lamp it belongs to is visible as a marker below the paint.

**Still open.**  A switch was reported with its light below the painted green
square.  Both of its bands are lit now, which may be the whole of it, but if not,
`marks` plus the texture name from `whatsthat` is what pins it down.  The most
likely candidates are the 18 of 66 rows measured from the colour heuristic rather
than from one of the mod's own brightmaps — `d64_metal7`, `d64_silver2`,
`d64_bronzewall_lit` and the four lever switches.

### Third round: one light per lamp, not one per fixture

The remaining play report was a switch whose light sat **below** its green square,
on bare plate.  It was not a pegging error.  Every lever switch here paints its
lower element as **two small wedges, one at each side of the housing** — and a
single centroid over both lands in the dark gap between them.  Same defect on
`d64_beigedoor` (two groups of ticks), `d64_talldoor` (two bars — the "2 bottom
blinking" door), and `d64_bigdoor` (two triangles).

This is the failure the ceiling lattice already records for SFLATC: *"perimeter
lights land between bulbs, in the middle of blank plate, and read as light coming
from nowhere."*

`bands()` now splits **horizontally as well as vertically**, but only where it has
to.  Cutting at every column gap was tried first and was worse: it turned
`d64_beigedoor`'s six ticks into six lights, which then hit the per-texture cap and
dropped one at random.  The rule that works is centroid-driven — measure the
centroid; if it lands on lit paint the group is one lamp and stays whole; if it
lands in a gap, cut at the **widest** gap and re-ask of each half, bounded at two
cuts.  A regular row of evenly spaced cells (`d64_exitdoor`'s lower strip) cannot
be helped by cutting — every gap is the same width — so it stays one bar and its
centroid is snapped to the nearest lit texel.

**The generator now asserts the invariant it exists to maintain**: every lamp's
position is checked against the mask it came from, and the run prints
`83 lamps, 83 of them centred on lit paint`.  Two tests of that property
disagreed at first — the splitter asked "is anything in this column lit" while the
report asked "is the centroid point lit" — and a small centre element a few rows
above `d64_brickwarn`'s wedges was enough to vouch for a point that plainly was
not on paint.  They ask the same question now.

Strips are exempt from all of it: a chain is stepped along the sidedef at a fixed
interval and never consults `cx`, so a band whose horizontal centre falls between
two lit runs is not a defect there.

Counts: 33 fixtures → 83 lamps.  `d64_talldoor_2` went from one light in the gap to
one on each bar; `d64_brown1lever_on` from one to three (bar plus both wedges).

### Fourth round: strips lit along their long axis, and the pane that would not glow

Three reports, three separate causes, and this time all three were found from the
map data and the log without launching anything.

**"Wall strips show nothing."**  Both `d64_lite_thin` sidedefs on MAP01 are
**16 units long** (lines 191 and 195, one-sided).  The chain started half a
segment in — 24 units — and looped `while d <= lineLen`, which on a 16-unit line
is zero iterations.  Strips that had one light each before the chain had none
after it; "nothing" was exact.  And the tube is *vertical* (16×128): a chain along
the wall was the wrong axis regardless.

The generator now emits each lamp's texel **extent** beside its centroid, and the
engine lights a strip along its long axis: rows up the wall = height over the
segment length, at least one; along the wall, a band spanning ≥ 75% of the
texture's width is a continuous chain spread evenly over the line, at least one,
while a narrower band sits at its own column once per texture repeat.  Checked
offline against MAP01's real lines: `lite_thin` gets a column of three, `metal7` a
row every 51 units on a 256-unit wall, `lite_wide` a column of three.

**"Doors and switches barely emit."**  Splitting each fixture into its real lamps
(round three) halved every lamp's `lit` count, and `areaScale = sqrt(lit/64)`
halved with it — on top of the 70→45 drop that came with the wider source.
`d64_talldoor` went from one lamp at ~107 to two at ~49.  `rt_ue_fixture_intensity`
is now **120**, which puts a typical split lamp back near Retribution's switch gem
(~150 through its own scale).

**"Zero light for SFLATAP."**  The analytic bulb was there — 34 on MAP01, 96 on
MAP12 — but `SFLATAS`, the reference the request named, also carries
`emissiveMult 20` from `SFLATAS_e` and its pane visibly *glows*.  `SFLATAP` has no
`_e` at all, deliberately, because in Retribution it is a grille the base game
never lights.  A pane that only casts reads as dead even while it lights the room.

The shared materials cannot carry the fix without lighting Retribution's 33
placements too, so it rides the overlay path instead: `d64ue-grille-emis.pk3`
supplies a GZDoom brightmap cut from the mod's own art (72% of peak luminance, the
248 slat texels) plus one GLDEFS line, and `rt_draw.cpp`'s Unseen-Evil-only
brightmap fallback — the same path the key trims use — turns it into RT emission
at `rt_ue_grille_emis` (6; SFLATAS's 20 is for four small bulbs, this is a 28×28
panel).  Retribution never loads the overlay and sees none of it.

**Still not verified by eye**, by request — everything above is from the WAD, the
art, the log of the user's own run, and an offline simulation of the placement
maths.  `.	oolsb-ue-fixtures.cmd marks 3` remains the arm that answers a
placement report.

## Materials for the mod's own art -- 2026-08-27

**Why Retribution "just worked" and UE did not: names.** Every RT material
(`rt/mat/<NAME>_e/_n/_h/_orm`, the `textures.json` rows) is keyed on the texture
name the engine sees. Retribution's textures are all named WAD lumps. Of UE's 442
wall targets, 80 are bare Doom 64 names (all pixel-identical to Retribution's, so
they get Retribution's materials for free), 246 are TEXTURES composites named by
their declared path, and 116 are plain PNGs whose basename exceeds 8 characters --
which GZDoom leaves **nameless**, so `MakeTextureName` (`rt_buffers.h`) fell to a
runtime image ID that nothing can match. 362 of 442 (82%) had no material at all.

**Engine:** `MakeTextureName` now keys a nameless texture on
`fileSystem.GetFileFullName` minus its extension -- `textures/pepy/d64_brown1` --
and RTGL1's `TextureOverrides::GetTexturePath` accepts `/`, so `rt/mat` gains
subfolders. Retribution never reaches that branch.

**Generated, automatically, from the mod's own data** by
`tools/gen_unseenevil_materials.py` into all four material dirs (the build stages
`Doom64-UnseenEvil/UnseenEvil-RT-Materials/rt` like Retribution's):

| map | source | count |
|---|---|---|
| `_e` | the mod's GLDEFS brightmaps (tone overlay wins), as albedo × mask -- the RAW ray-traced contract | 79 |
| `_n` | Sobel from luma over a 0.6 px blurred albedo, strength 1.2 | 540 |

The `_e` half matters more than it looks: the engine's UE brightmap fallback
(`l_hasWorldBrightmap`) only flags a primitive emissive with a **multiplier** --
the brightmap's pixels never reach RTGL1, which takes emission solely from an
`_e` override. A UE door indicator therefore glowed as its entire face, dimly and
unmasked. No `_h`, no `_orm`: an ORM needs a surface class per texture, and the
automatic way has none.

**Never under a bare name.** A bare name is shared with Retribution by
construction (`DTWMD25` carries a meta row and no file; a generated `_n` there
would dress Retribution too). Path-shaped subfolders cannot collide. Seventeen
UE PNGs that are byte-identical to Retribution `DTWMD*` lumps are instead
retargeted to those names by `make_unseenevil_texfix.py`, so they wear
Retribution's authored materials outright.
