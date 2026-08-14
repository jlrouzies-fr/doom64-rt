# `rt_verbose` — keeping the renderer off the screen

`rt_verbose` decides whether RT/RTGL1 **diagnostics** paint the on-screen notify
area or stay in the console and the logfile. It is `0` by default, and that is
the release setting.

    rt_verbose 0   (default)   console + rt-console.log only    <- shippable
    rt_verbose 1               ... and the notify overlay too   <- pre-2026-08-13 behaviour

It never touches **game** messages. Pickups, level names, "You got the shotgun!"
are unaffected in either position.

## What it was for

Before this, a normal level load put four to seven lines of engine text across
the picture, and the flashlight key added one per press:

    Can't find a file, no static scene will be present: rt/scenes\d64rtr_v15_map01\...
    RT upscale/RR decision: DLSS2=yes DLSS3FG=yes nvDlss=2 wantNativeRr=no -> ...
    Setup(): params.upscaleTechnique=3 params.rayReconstruction=0 | dlss2=yes ...
    No camera provided via API, nor through .gltf
    Denoiser path: A-SVGF (Denoise) (DLSS-RR object=present, DLSS upscaler=on, ...)
    ReSTIR: initialSamples=32 (stock 8), spatialSamples=8 (stock 8), ...
    RT_BOOT: first frame presented 635 ms after V_Init2 returned ...
    D64RtSkyFix: MAP01 sky -> MOONSKY
    "rt_flsh" = "true"

Useful while developing. Not shippable, and `screen/errorStartingMaps.png` is
what it looked like.

## The mechanism — it is the print LEVEL, not the call site

`PRINT_NONOTIFY` (1024, `common/engine/printf.h`) is a **flag** on the print
level, not a level of its own. In `PrintString` (`common/console/c_console.cpp`)
it skips exactly one thing — `NotifyStrings->AddString` — while `I_PrintStr`,
the console buffer and `WriteLineToLog` all still run:

```cpp
if (printlevel != PRINT_LOG)
{
    I_PrintStr(outline);
    conbuffer->AddText(printlevel, outline);
    if (vidactive && screen && !(iprintlevel & PRINT_NONOTIFY) && NotifyStrings)
        ...AddString(iprintlevel, outline);      // <- the only part skipped
}
if (Logfile != nullptr && !(iprintlevel & PRINT_NOLOG))
    WriteLineToLog(Logfile, outline);
```

**That is why quiet is the default rather than a release-only flag: it costs
nothing.** `~` and `rt-console.log` still carry every line, so nothing becomes
harder to diagnose. `rt_verbose 1` passes plain `PRINT_HIGH`, which is literally
the argument these calls had before.

Two helpers select it:

| Helper | Where | For |
|---|---|---|
| `RT_DiagPrintLevel()` | `rendering/rt/rt_internal.h` | every RT translation unit |
| `RT_BootPrintLevel()` | `d_main.cpp`, `static` | the `RT_BOOT` timings — `d_main.cpp` must not include the private RT header, so this is a deliberate two-line mirror |

ZScript in the pk3s has its own copy, reading the cvar by name:

```
static int DiagLevel()
{
    let cv = CVar.FindCVar("rt_verbose");
    return (cv && cv.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY;
}
```

and calls `Console.PrintfEx(DiagLevel(), ...)` instead of `Console.Printf`.

## What is covered

| Source | Site |
|---|---|
| **Everything RTGL1 prints** — missing scene, `Setup()`, `No camera provided`, `Denoiser path`, `ReSTIR` | one line: the `RG_MESSAGE_SEVERITY_WARNING` branch of `RT_Print`, `rt_main.cpp` |
| `RT_BOOT:` ×4 (V_Init2 early/late, first frame, TITLEMAP load) | `d_main.cpp` |
| `RT upscale/RR decision:` + the DLSS2-unavailable reason | `rt_main.cpp` |
| `RT_Title:` | `rt_titles.cpp` |
| `RT water: tagging ...`, `RT lava: tagging ...` | `rt_draw.cpp` |
| `RT lava: N lava sector(s) found, but NO light placed` | `rt_lights_fx.cpp` |
| `rt_flsh: on/off` | `rt_weapon.cpp`, the new `rt_flsh_toggle` CCMD |
| `D64RtSkyFix:` ×3 | `tools/d64r-rt-sky/ZSCRIPT` |
| `D64LavaFx:` ×2 | emitted by `tools/gen_lava_fx.py` |

The RTGL1 row is the whole point of the design: `RT_Print` is the single funnel
for every message the renderer library emits, so one argument covers all of it
and any future RTGL1 message inherits the behaviour for free.

## What is deliberately NOT covered

- **Replies to a CCMD you typed** — `whatsthat`, `moon`, `clouds`, `fog`,
  `smoke`, `thunder`, `rt_dump_lightthinkers`, `rt_dump_dynlights`, the RR
  status dump. An answer has to appear where the question was asked.
- **Anything already behind a `*_debug` cvar** — `rt_dynlight_debug`,
  `rt_lightlevel_watch`, `rt_tex_probe`, `rt_ceiling_lamp_debug`,
  `rt_smoke B/spawn`, `rt_lightning_debug`, and the rest. Turning that cvar on
  *is* the request to see them, and they are off by default anyway.
- **The `rt_upscale_dlss` + `rt_upscale_fsr2` conflict warning**
  (`rt_main.cpp`). It fires once per session and only on a broken config, and
  it tells you to fix something.
- **Game messages.** Nothing here goes near them.

## Adding a new print

Ask one question: *did the user ask for this line?*

- **No** — the renderer is reporting on its own initiative:
  `Printf( RT_DiagPrintLevel(), ... )`, or `Console.PrintfEx(DiagLevel(), ...)`
  from a pk3.
- **Yes** — it answers a CCMD or a `*_debug` cvar the user set: plain `Printf`.

## Four traps

- **`PRINT_LOG` is the wrong flag.** It writes the logfile *only*; the message
  vanishes from the in-game console as well. The pair you want is
  `PRINT_HIGH | PRINT_NONOTIFY`.
- **A toggle *message* does not silence a key.** `CCMD(toggle)` in `c_cvars.cpp`
  reports unconditionally, and `SetToggleMessages` only swaps one on-screen line
  (`Printf(PRINT_NOTIFY, ...)`) for another. The flashlight key had to stop
  calling `toggle` at all — hence `rt_flsh_toggle`. Do not put
  `alias d64rt_flashlight "toggle rt_flsh"` back in the KEYCONF.
- **`con_notifylines 0` is not a substitute.** It empties the notify area
  wholesale and takes pickups and level names with it.
- **An absent optional file is not a warning.** RTGL1's `GltfImporter.cpp`
  logged `cgltf_result_file_not_found` at `debug::Warning`, and `RT_Print`
  routes warnings to `Printf` on purpose, so the one condition true of *every*
  Retribution map printed on every load. It is `debug::Info` now; genuine
  parse / load / validate failures still warn. That tree is **gitignored** —
  after a fresh `deps/RTGL` checkout the edit must be reapplied and
  `tools/build-rtgl.cmd` re-run, or the line comes back.

## Related

- `compat-patches.md` (2026-08-13) — the changelog entry.
- `AGENTS.md` — the cvar in the launch-cvar list.
