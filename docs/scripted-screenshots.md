# Scripted screenshots

`tools\shot.ps1` launches the game, lets it settle, takes a screenshot and
quits — no keyboard, no window focus, no user present. It exists because
eyeballing a HUD change from a described symptom is guesswork, and a captured
frame can be *measured*.

```
.\tools\shot.ps1                       # map01, ~8.6s settle
.\tools\shot.ps1 -Map map05 -Tics 420
.\tools\shot.ps1 -Extra '+rt_flsh 1'
```

Output goes to `screen\shots\` by default and the path of the new file is
printed. It kills any running gzdoom first.

---

## 1. The one thing that makes it work

**`wait` only defers the remainder of the same command string**
(`c_dispatch.cpp:376` — "The remainder of the command will be executed later").

That single fact is the whole trick. Passing

```
+wait 300 +screenshot +quit
```

as separate arguments does **not** wait: each `+arg` is its own command string,
so `wait` has nothing after it to defer, and `screenshot` and `quit` both fire
*immediately at startup* — before a single frame has been presented. The process
exits with code 0 in a couple of seconds and produces no file, which looks
exactly like the screenshot command silently failing.

An `exec`'d cfg fails the same way, one command per line.

It has to be one semicolon-separated string:

```
+"wait 300; screenshot; wait 40; quit"
```

## 2. Why nothing appeared to happen

`screenshot` is `G_ScreenShot()`, which only **sets a flag**. The capture happens
when a frame is next presented (`m_misc.cpp`). Fire it before the renderer has
produced anything and the flag is set, never consumed, and no error is printed.

Two smaller traps behind it:

- `screenshot` is an `UNSAFE_CCMD`, refused in an untrusted execution context
  with `Cannot execute unsafe command screenshot` in red. From the command line
  it is fine, so this is not usually the problem — but it looks like it might be.
- Destination precedence is `-shotdir` → `screenshot_dir` cvar →
  `M_GetScreenshotsPath()` (`m_misc.cpp:583`). This project's config has
  `screenshot_dir` pointed at a smoke-lab folder, so unqualified screenshots land
  somewhere non-obvious. `openscreenshots` opens whichever directory is winning.

## 3. What does not work from a background process

Recorded so the next session does not spend an hour on it:

- **`SetForegroundWindow`** — returns without raising the window.
- **COM `WScript.Shell.AppActivate`** — returns `True`, but
  `GetForegroundWindow()` still is not the game.
- **`Graphics.CopyFromScreen`** of the window rect — captures whatever is
  actually in front, which is the terminal.

The game itself launches fine and creates a window titled `Doom: Ray Traced`;
the problem is purely that a background shell cannot bring it to the front. Use
the in-game `screenshot` command, not a desktop capture.

## 4. Measuring a capture

The screenshots include the window frame, so the game area is inset by the
border and title bar. For HUD work, useful anchors:

- **HUD labels** are light neutral grey: `max(rgb) > 120 && (max-min) < 34`.
  Find the label row band by row density, then segment words by column gaps.
- **Values** are red: `r > 90 && r-g > 45 && r-b > 40`.
- **Scale** comes free from a known label: `D64HUDFONT` glyphs are 7px wide
  (`L` is 5), so HEALTH is 42 units — its measured width in pixels divided by 42
  is px-per-HUD-unit. Everything else can then be expressed in HUD units and
  compared directly against the SBARINFO coordinates.

That is how `HUD_ASPECT` in `docs/hud-mugshot.md` §9 was pinned down: render,
measure the battery label against HEALTH, correct, re-render, confirm.

**Watch for stale builds.** A screenshot whose measured geometry does not match
the current source is a screenshot from an older build — check that before
concluding a coordinate change did not take effect.
