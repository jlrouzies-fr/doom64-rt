# Credits

**Doom 64 — Ray Traced** is a fan project. It renders someone else's game, in someone
else's engine, with someone else's path tracer. Almost nothing here would exist without
the work listed below.

Everything on this page was taken from the licences and credit files that ship with each
project — `deps/RTGL/LICENSE`, `sourcecode/gzdoom-rt/README.md` and `LICENSE`,
`Doom64-Retribution/D64RTR_README.TXT`, `sourcecode/Duke-RT/AUTHORS.md` — not from memory.
If an attribution here is wrong or incomplete, that is a bug; please open an issue.

---

## The path tracer — RTGL1 / RayTracedGL1

The renderer that makes this project possible. MIT licensed.

- **Sultim Tsyrendashiev** — original author (© 2020–2023)
- **Vasilii Shirokii** — continued development (© 2024)

Sultim Tsyrendashiev is also the author of **Doom: Ray Traced** (`prboom-plus-rt`) and the
earlier RTGL1 game integrations that this project's material and lighting conventions are
modelled on.

<https://github.com/sultim-t/RayTracedGL1> · <https://github.com/vs-shirokii/RTGL>

## The engine — GZDoom: Ray Traced

- **Vasilii Shirokii** (`vs-shirokii`) — the ray-traced GZDoom fork this project builds on,
  and the author of essentially all of the `src/common/rendering/rt/` renderer that our
  own engine work extends.

<https://github.com/vs-shirokii/gzdoom-rt>

### GZDoom itself

Copyright © 1998–2023 the **ZDoom** and **GZDoom** teams and contributors, GPLv3.
By commit volume in the tree we build, the largest contributors are:

- **Christoph Oelckers** (Graf Zahl)
- **Magnus Norddahl** (dpJudas)
- **Randy Heit** — ZDoom's original author
- **Alexey Lysiuk**
- **Rachael Alexanderson**
- **Braden Obrzut**, **MajorCooke**, and many more — see the ZDoom repository history.

Doom source code © 1997 **id Software**, **Raven Software**, and contributors.

<https://zdoom.org/>

## The game — Doom 64: Retribution v1.5

- **Nevander** — author of the total conversion: every stock Doom 64 map converted fresh to
  UDMF, all map scripts and events rewritten by hand, and the weapon/monster/item work.

Retribution's own credits, in full (from `D64RTR_README.TXT`):

- Weapons, monsters and items based on **Doom 64 WMI Redux** by **Dreadflame** (GuitarDeity)
  and **Footman**, with tweaks by Nevander and concepts from **HazeBandicoot**
- Absolution TC exclusive maps by **Samuel "Kaiser" Villarreal** and **Elbryan42**;
  Outcast Levels by Kaiser, Elbryan42 and **AgentSpork**; Redemption Denied by
  **Steven Searle** and AgentSpork; unfinished Outcast maps completed by Nevander
- **Kaiser**, again, for **Doom 64 EX** and **WadGen** — without which the TC could not exist
- Textures by **Cage** ("Doom the Way Midway Did"), **NMN** (Outcast set),
  **Emerson Tung** & id Software (DOOM 2016 style, ripped by **Dragonfly**),
  the **PSX TC crew** / Williams Entertainment, and **CoTeCiO** (logo art)
- Smoother weapon animations by **Cage** and **Almonds**; further frame edits by
  Nevander and **Skelegant**; pistol pickup base by **osjclatchford** and **chronoteeth**;
  shotgun pickup from *Doom 64: Unabsolved* by **AEnima**
- Thing fade-in code by **Kaiser** and **AgentSpork**, improved by **KeksDose** and Nevander;
  Lost Soul explosion method by **snackerfork**; automap arrow from *PSX Doom TC*
- **TheDoctor45** (M_DOOM logo base), **86232and**, **TheWolfArokh**

## The original — Doom 64 (1997)

**Midway Games** and **id Software**.

- Level design team, including **Randy Estrella**, **Tim Heydelaar** and **Danny Lewis**
- Sprites and art by **Sukru Gilman**, **Francisco Gracia**, **Laurent Bezault** and
  **Andy Wilson**
- Music and sound effects by **Aubrey Hodges**; original sound system by **Scott Patterson**

*Doom* and *Doom 64* are trademarks of id Software.

## Also drawn on

- **NVIDIA** — DLSS 2 and DLSS Ray Reconstruction, used for upscaling and denoising.
- The **A-SVGF** denoiser, after Schied, Peters and Dachsbacher's adaptive temporal
  filtering work — the default denoising path here.
- **Duke-RT** (`sourcecode/Duke-RT`) — consulted as a material- and lighting-authoring
  reference. A fork of **Raze** (**Christoph Oelckers**, **Mitchell Richters**), itself
  built on **EDuke32** (TerminX, Hendricks266, pogokeen, Plagman, Helixhorned),
  **JFDuke3D** (JonoF) and **Ken Silverman**'s BUILD engine.
- **Doom 64 CE** — PBR material source for the AI PBR pilot (local, not redistributed).

## This project

Path-tracing integration, RT material authoring, the lighting-repair tooling and the
engine features documented in `docs/` — **Jean-Laurent Rouziès**.

Non-commercial, and not affiliated with id Software, Bethesda, Midway or NVIDIA.
