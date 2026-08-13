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
- **Claude owns the writing.** Engine code in the `gzdoom-rt` fork, the Python and
  batch tooling, the generators, the scanners, the material metadata and the
  documentation. It also proposes designs, investigates faults and reports what it
  verified versus what it assumed.
- **Testing is genuinely shared.** The scanners, probes and QA scripts are Claude's;
  running the game, judging the image and catching regressions is the author's, and
  is the only thing that has reliably found the subtle faults.
- **`deployment: assist`** because there is no release yet — the build scripts are
  AI-written, the builds are run and verified by the author.

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
