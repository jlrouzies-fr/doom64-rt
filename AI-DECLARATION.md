---
version: "0.1.2"
level: copilot
processes:
  design: pair
  implementation: copilot
  testing: pair
  documentation: copilot
  review: pair
  deployment: assist
components:
  tools: copilot
  docs: copilot
  Doom64-Retribution/Retribution-RT-Materials: copilot
---

This format is based on [AI-DECLARATION.md](https://ai-declaration.md/en/0.1.2).

## Notes

This project is AI-written under human direction, and it would be misleading to
present it any other way.

The author is a software engineer by trade — .NET, not games. No graphics
programming, no renderer background, no experience with the Doom engine or with
path tracing before this project started. The path-traced renderer features, the
lighting-repair tooling, the material pipeline and every document in `docs/` were
written by Claude (via Claude Code), prompted, steered, corrected and accepted or
rejected by the author.

What that split looks like in practice:

- **The author owns every decision and all judgement of the result.** Whether a
  room reads right, whether a light belongs there, whether an effect is worth its
  cost, what to build next, what to abandon. Path tracing has to be *looked at*,
  and only a human at the screen can do that. A large share of this repo's
  documented findings begin with the author saying the render was wrong when the
  tooling said it was fine — and being right.
- **That direction is technical, not just aesthetic.** Missing renderer experience
  is not missing engineering judgement. Working from the rendered output and from a
  broad knowledge of how game graphics settings behave — denoisers, upscalers,
  light radii and falloff, fog and volumetrics, LOD and culling, what a given knob
  is *supposed* to do — the author has repeatedly redirected the AI to a better
  implementation than the one it proposed, and rejected changes that would have
  looked right in isolation while breaking something else.
- **Claude owns the writing.** Engine code in the `gzdoom-rt` fork, the Python and
  batch tooling, the generators, the scanners, the material metadata and the
  documentation. It also proposes designs, investigates faults and reports what it
  verified versus what it assumed.
- **Testing is genuinely shared.** The scanners, probes and QA scripts are Claude's;
  running the game, judging the image and catching regressions is the author's, and
  is the only thing that has reliably found the subtle faults.
- **`deployment: assist`** because there is no release yet — the build scripts are
  AI-written, the builds are run and verified by the author.

This is why several of the project's standing rules exist, and they are written
into `AGENTS.md` as instructions to the AI rather than as anecdotes:

> *A negative from a scanner you just wrote is weaker evidence than what the
> person watching the screen tells you. When they disagree, distrust the tool.*

Cases behind that rule: one of three identical-looking wall panels lit a room and
the other two did not — the author's "compare the things, not the textures" led to
`rt_dynlight_flicker` silently dropping 199 of the game's 205 monitor lights, which
no amount of material work would have found. A release build that "had the same
settings" looked wrong to the author; the configs were byte-identical and the real
cause was 236 KB of authored material metadata that had never been committed. An
A/B that showed no difference was accepted as a null result until the author
insisted the change could not be live — it wasn't. In each case the AI's own
instrumentation said everything was fine.

The two upstream forks this project depends on carry the same working
arrangement for the changes made *here*:
[`gzdoom-rt`](https://github.com/jlrouzies-fr/gzdoom-rt) and
[`RTGL`](https://github.com/jlrouzies-fr/RTGL). Everything they inherit from
upstream is the work of their original authors — see [CREDITS.md](CREDITS.md).

Nothing in the game's art, maps, music or sound is AI-generated. The base game is
Doom 64 by Midway and id Software, the total conversion is Doom 64: Retribution
by Nevander, and the renderer is RTGL1 by Sultim Tsyrendashiev and Vasilii
Shirokii. Where this project generates assets — emissive masks, ORM and normal
maps, the mugshot frames — they are derived programmatically from that existing
art by scripts in `tools/`, not synthesised by a generative image model, with one
exception: the AI PBR pilot (`tools/gen_ai_pbr.py`) uses Marigold to estimate
depth and normals from the original textures.
