@echo off
rem DelayedExpansion is needed to accumulate the "--" passthrough in a loop.
rem Safe here: no literal '!' appears anywhere else in this script.
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem Doom 64: Unseen Evil under the native RT renderer, with the brightmap tone
rem overlay applied.
rem
rem WHAT THE OVERLAY IS. D64UnseenEvil-v1.0.3.pk3 pins 18 of its 54 brightmap
rem masks at 255. A GZDoom brightmap is a mask meaning "ignore the room's light
rem here", and the mod's own brightermap_dynamic.fp then multiplies by 1.5 on
rem top, so those texels land near 380% of the raw texture and stick out of an
rem otherwise dark room. d64ue-brightmap-tone.pk3 rescales just those 18 to 192
rem -- the mod's OWN modal ceiling; 36 of its masks already sit between 40 and
rem 244. Nothing is removed and hue is exact, so key trims and door lights keep
rem their colour.
rem
rem IT MUST LOAD AFTER THE MOD. It replaces files at identical paths, so load
rem order is the entire mechanism -- put it first and it does nothing at all.
rem Rebuild it any time with:
rem     python tools\tone_unseenevil_brightmaps.py --write
rem
rem WHICH IWAD. Unseen Evil is an overhaul of DOOM/DOOM II, not a standalone TC:
rem its MAPINFO replaces exactly two levels -- 64UE_DIS carries e3m8special and
rem secretnext E3M9 (Ultimate Doom's E3M8) and 64UE_SIN is cluster 8 -> EndGameC
rem (DOOM II's MAP30). Everything else is the IWAD's own maps. Defaults to
rem doom2.wad; pass "doom1" as the first argument for the Ultimate Doom side.
rem ---------------------------------------------------------------------------
rem
rem   .\tools\launch-unseenevil-rt.cmd            -> doom2.wad, MAP01
rem   .\tools\launch-unseenevil-rt.cmd 7          -> doom2.wad, MAP07
rem   .\tools\launch-unseenevil-rt.cmd 30         -> MAP30, the custom Icon of Sin
rem   .\tools\launch-unseenevil-rt.cmd menu       -> title screen, no +map
rem   .\tools\launch-unseenevil-rt.cmd doom1      -> doom.wad, E1M1
rem   .\tools\launch-unseenevil-rt.cmd doom1 e3m8 -> doom.wad, the custom Dis
rem   .\tools\launch-unseenevil-rt.cmd bare       -> no Retribution patches at all
rem   .\tools\launch-unseenevil-rt.cmd min 2      -> MAP02, start minimized
rem   .\tools\launch-unseenevil-rt.cmd 5 -- +rt_sky 40      -> extra cvars win
rem
rem Anything that is not a number and not a keyword is passed to +map verbatim,
rem so 64UE_SIN / 64UE_DIS / TITLEMAP / e3m8 all work directly.

rem Project root, derived from this script's own location, so a clone can live
rem anywhere. Nothing below may hardcode an absolute path into the repo.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"

set "MOD=%PROJ%\Doom64-UnseenEvil\D64UnseenEvil-v1.0.3.pk3"
set "TONE=%PROJ%\Doom64-UnseenEvil\d64ue-brightmap-tone.pk3"
rem Liquid animation. The mod maps all four FWATER frames to one flat, so its
rem pools are frozen; this declares the A/B pairs it ships but never cycles.
rem Build/inspect: the pk3 holds a single ANIMDEFS lump and nothing else.
set "LIQANIM=%PROJ%\Doom64-UnseenEvil\d64ue-liquid-anim.pk3"
rem Baked skies. The mod's skybox_* are 32x32 stubs whose real look comes from
rem shaders/d64ue/sky_3d.fp; RTGL1 never runs GZDoom fragment shaders, so under RT
rem the sky renders blank. Rebuild: py -3 tools\make_unseenevil_skies.py --write
set "SKYRT=%PROJ%\Doom64-UnseenEvil\d64ue-sky-rt.pk3"
rem Pickup glows. The mod lights its keys and weapon projectiles but nothing else;
rem armour and the spheres define no light, so they sit unlit under RT.
set "PICKLT=%PROJ%\Doom64-UnseenEvil\d64ue-pickup-lights.pk3"
rem Routes UE's Options entry through the compact RT menu, whose Other entry
rem reaches base GZDoom. It uses the stock drawer only on that RT page because
rem UE's drawer bypasses TextItem_RT values. Its additive customization subclass
rem also removes only the Player tab and recentres Gameplay/Aesthetics/Music.
rem Rebuild with the script below.
set "RTMENU=%PROJ%\Doom64-UnseenEvil\d64ue-rt-menu.pk3"
rem FLAT2 retarget. The mod maps FLAT2 -- an ordinary grey DOOM II ceiling flat used
rem over huge areas -- onto Doom 64's inset-lamp flat SFLATAS, which this engine
rem treats as a FIXTURE (emissiveMult 20 in rt/data/textures.json, plus real analytic
rem lights from RT_IsCeilingInsetLampTexture). The result is an entire ceiling acting
rem as a light with nothing in the room producing it. Sends FLAT2 to SFLATAP instead --
rem same family, a grille rather than bulbs, deliberately excluded from the lamp list.
rem TLITE6_5/6 keep their SFLATAS mapping: those are real light flats.
rem Rebuild: py -3 tools\make_unseenevil_texfix.py --write
set "TEXFIX=%PROJ%\Doom64-UnseenEvil\d64ue-texfix.pk3"

rem ---- autolights -----------------------------------------------------------
rem WHY THIS IS NEEDED AT ALL. DOOM 1 and DOOM 2 maps contain no light things --
rem their rooms are lit purely by sector lightlevel, which is baked shading, not
rem a light source. Under a path tracer that leaves the world essentially black:
rem rt_sector_emis only makes a bright surface glow on itself, and the engine's
rem fixture walk keys off Doom 64 texture names this content does not use.
rem d64rt-autolights.pk3 spawns one PointLight per lit sector, which GZDoom
rem forwards into RTGL1 through the same path Retribution's 9800 things use.
rem
rem LOADED BUT OFF. d64ue-lighting.cfg pins rt_sector_lights 0, and this rig reads
rem that cvar every tic, so nothing is spawned unless you ask for it.
rem
rem WHY IT IS OFF. A PointLight parked at a sector's centre burns a round pool into
rem the flat above it -- a bright disc with no fixture anywhere near it. Lowering it
rem in the room only spreads the disc; nothing removes it, because the emitter is a
rem ball hanging in mid-air. Surface emission (rt_sector_emis) was tried as the
rem replacement and rejected on the same ground: no disc, but the same invented
rem light, just told more smoothly. Only real emitters light these maps now.
rem
rem THE COST IS REAL: DOOM 1/2 maps carry no light things at all, so they are DARK.
rem The flashlight (F) is the intended answer.
rem
rem rt_sector_lights IS ITS SWITCH -- the pk3 was changed to make that true, rather
rem than to explain why it was not. These are PointLight ACTORS, so no rt_* cvar gated
rem them at the engine level; rt_sector_lights controls only RTGL1's own stock
rem per-sector upload. From inside the game that distinction is invisible: you turn
rem "sector lights" off, they stay, and the only honest reading is that the cvar is
rem broken. So `rt_sector_lights 1` in the console brings them back live, and `0`
rem removes them again, with no map reload either way.
rem
rem Retribution never loads this pk3 -- it has real 9800/9801/9802 light things -- so
rem none of this reaches it.
set "AUTO=%PROJ%\Doom64-UnseenEvil\d64rt-autolights.pk3"

rem ---- Retribution patches carried over -------------------------------------
rem WHICH OF OURS TRANSFER, AND WHY MOST DO NOT. Every d64r-*.pk3 was checked for
rem what it inherits from and replaces. The great majority are Retribution-shaped
rem and cannot come here:
rem
rem   d64r-blood-persist.pk3  NO -- and this is the tempting one, because it is
rem       what DECLARES the nine rt_gore_* cvars the pins set, so the "Unknown
rem       command" lines at startup point straight at it. Its DECORATE is
rem       "ACTOR RTBloodPersist : 64Blood replaces 64Blood", plus 64Blood2,
rem       64InvisiBlood, 64Cacodemon, 64Arachnotron, 64NightmareImp,
rem       64PainElemental, 64SpiderMastermind. None of those actors exist here --
rem       DOOM's blood is `Blood` -- so loading it is a startup script error, not
rem       persistent blood. The nine unknown-command lines are the correct and
rem       harmless result of sharing one pins file across two mods.
rem   d64r-seqlight-fix.wad / d64r-ctel-fix.wad /
rem   d64r-bulb-textures.wad  NO -- map and texture replacements for Retribution's
rem       own MAP01-34. Nothing here has those maps.
rem   d64r-widescreen-gfx.pk3 / d64r-rt-titlelogo.pk3  NO -- they override
rem       TITLEPIC/title music and Unseen Evil ships its own custom TITLEMAP.
rem   d64r-mugshot.pk3  YES, through d64ue-retribution-hud.pk3. The compatibility
rem       package copies its SBARINFO/TEXTURES/FONTDEFS/mugface unchanged, then adds
rem       only the glyphs/key icons and IsPlaying token Retribution normally gets
rem       from D64RTR_v15.WAD. Because it loads after UE, GZDoom's existing
rem       last-definition rule selects that SBARINFO over D64UE_StatusBar.
rem   Retribution's player sprites  YES, through d64ue-retribution-player.pk3.
rem       UE's PLAY/PLYC sprite files are flat green colour masks whose real art is
rem       reconstructed by a GZDoom fragment shader. RTGL1 never runs that shader,
rem       so it traces the green mask itself. The compatibility package copies the
rem       exact Retribution PLAY PNGs over those masks, uses the same art for UE's
rem       crouch frames, and restores normal material sampling. The RT menu
rem       package above removes the obsolete Player page.
rem   Retribution's first-person weapons  YES, through d64ue-muzzleflash.pk3.
rem       The overlay retains UE's firing functions and ammo rules, but restores
rem       Retribution's original shotgun/SSG/chaingun/plasma/BFG/Unmaker frames
rem       and timing plus the A_Light triggers consumed by the shared RT flash
rem       path. UE-private UESG/UESF shotgun and UECF/UEMF flash aliases avoid
rem       UE NoTrim conflicts and global material lights. The engine composites
rem       only UE's actual Flash layer additively, the SSG offset changes only
rem       during Fire, and the visual Unmaker model retracts slowly enough to
rem       reach an RT frame. Retribution never loads this overlay.
rem   Retribution's exploding barrel path  YES, through d64ue-retribution-barrel.pk3.
rem       UE normally dies on BAR1 D and stops, bypassing the BEXP E edge used by
rem       both volumetric barrel smoke and the RT plate/scorch/ember system. The
rem       UE-only overlay keeps its class/gameplay but enters Retribution's frames.
rem   d64r-rt-sky.pk3  NO -- Unseen Evil has its own sky system, GLDEFS.skies plus
rem       the sky_3d.fp and skyfire.fp shaders.
rem
rem   d64r-rt-flashlight.pk3  YES. Self-contained and free of Doom 64 actor
rem       dependencies: one EventHandler, a KEYCONF binding F to the engine's
rem       rt_flsh_toggle, two sound cvars of its own, three wavs. AddEventHandlers
rem       is additive, so it sits alongside Unseen Evil's handlers rather than
rem       replacing them. Worth having precisely because this is a dark
rem       path-traced game.
rem
rem       The battery overlay was already authored against the Retribution
rem       ForceScaled+FullScreenOffsets SBARINFO copied by the HUD package, so
rem       it follows the exact same integer clean scale here without a UE-only
rem       placement branch. Launch with "bare" to drop every patch.
set "FLSH=%PROJ%\Doom64-Retribution\d64r-rt-flashlight.pk3"
set "HUD=%PROJ%\Doom64-UnseenEvil\d64ue-retribution-hud.pk3"
set "PLAYER=%PROJ%\Doom64-UnseenEvil\d64ue-retribution-player.pk3"
set "MUZZLE=%PROJ%\Doom64-UnseenEvil\d64ue-muzzleflash.pk3"
set "BARREL=%PROJ%\Doom64-UnseenEvil\d64ue-retribution-barrel.pk3"
rem The quotes live INSIDE the value: PROJ is derived from this script's path and
rem a clone can sit somewhere with a space in it, at which point an unquoted
rem expansion would split into two bogus -file arguments.
set "PATCHES="%FLSH%" "%HUD%" "%PLAYER%" "%MUZZLE%" "%BARREL%""
if not exist "%FLSH%" set "PATCHES="
if not exist "%HUD%" set "PATCHES="
if not exist "%PLAYER%" set "PATCHES="
if not exist "%MUZZLE%" set "PATCHES="
if not exist "%BARREL%" set "PATCHES="
rem Retribution lights each locked-door jamb with a vertical stack of three
rem ordinary 9800 PointLight map things. UE transforms IWAD maps at runtime, so
rem this late EventHandler finds the final key-trim faces and spawns those same
rem stacks after the Terraformer has finished.
set "KEYLIGHTS=%PROJ%\Doom64-UnseenEvil\d64ue-keytrim-lights.pk3"
if not exist "%KEYLIGHTS%" set "KEYLIGHTS="
if defined KEYLIGHTS set "KEYLIGHTS="%KEYLIGHTS%""
rem SFLATAP grille glow. The mod's Terraformer puts this flat on 445 ceilings and
rem floors (CEIL3_4, CEIL1_2, CEIL1_3, FLAT2 via the texfix, and DOOM's own TLITE6_1
rem and TLITE6_4 light panels), and the shared materials give it no emissive on
rem purpose -- in Retribution it is a grille. This overlay is a brightmap cut from
rem the mod's own art plus a GLDEFS line, which the engine's UE brightmap fallback
rem turns into screen glow at rt_ue_grille_emis. The analytic bulb under each pane
rem is rt_ue_grille_lamps, in the engine. Rebuild: py -3 tools\make_unseenevil_grille.py --write
set "GRILLE=%PROJ%\Doom64-UnseenEvil\d64ue-grille-emis.pk3"
if not exist "%GRILLE%" set "GRILLE="
if defined GRILLE set "GRILLE="%GRILLE%""
rem THE WALL MONITORS, same idea and the same reason. Retribution lights its SMON
rem panels with a 9802 PointLightFlicker thing a few units off the face -- SMONDA 25
rem of 27 -- and DOOM II carries NO 9800/9801/9802 thing in any map, so Unseen Evil
rem had only the engine's steady wall-strip substitute and the panels read as dead.
rem This spawns Retribution's own fixture on the SMOND faces the Terraformer makes,
rem which inherits the blink tuning (rt_dynlight_blink_floor) for free rather than
rem re-deriving it in the renderer. Toggle with d64ue_rt_monitorlights.
set "MONLIGHTS=%PROJ%\Doom64-UnseenEvil\d64ue-monitor-lights.pk3"
if not exist "%MONLIGHTS%" set "MONLIGHTS="
if defined MONLIGHTS set "MONLIGHTS="%MONLIGHTS%""
rem THE LIQUIDS, RETRIBUTION'S WAY. UE's own WATERA/SLIMEB/SLUDGE/BLOOD flats reach
rem the liquid shader by name and nothing else -- no per-frame relief (rt/mat has
rem 64 x _h/_n/_orm for D64B*/D64S* and none for UE's names), no lava emissive or
rem lights (RT_IsLavaFlat is HLAVA*/D64LAVA*), no poison bubbles (D64N prefix). So
rem d64ue-texfix retargets the mod's liquid mapping onto Retribution's names and
rem this overlay ships Retribution's construction for them. ORDER MATTERS, exactly
rem as in launch-retribution-rt.cmd: the liquid-art wad redefines the blood/poison/
rem sludge frames and must load AFTER the overlay; the fx pk3s are self-contained.
set "LIQUIDS=%PROJ%\Doom64-UnseenEvil\d64ue-retribution-liquids.pk3"
if not exist "%LIQUIDS%" set "LIQUIDS="
if defined LIQUIDS set "LIQUIDS="%LIQUIDS%""
set "LIQUIDART=%PROJ%\Doom64-Retribution\d64r-liquid-art.wad"
if not exist "%LIQUIDART%" set "LIQUIDART="
if defined LIQUIDART set "LIQUIDART="%LIQUIDART%""
set "POISONFX=%PROJ%\Doom64-Retribution\d64r-poison-fx.pk3"
if not exist "%POISONFX%" set "POISONFX="
if defined POISONFX set "POISONFX="%POISONFX%""
set "LAVAFX=%PROJ%\Doom64-Retribution\d64r-lava-fx.pk3"
if not exist "%LAVAFX%" set "LAVAFX="
if defined LAVAFX set "LAVAFX="%LAVAFX%""
set "PINS=%PROJ%\tools\d64rt-pins.cfg"
rem World lighting for DOOM 1/2 maps. Exec'd AFTER the pins so it wins. Both invented
rem light schemes -- the per-sector PointLight rig and sector self-emission -- are
rem turned OFF there; only real emitters light these maps. See the file.
set "LIGHTCFG=%PROJ%\tools\d64ue-lighting.cfg"
rem A separate log from rt-console.log on purpose: that one is the Retribution
rem transcript and gets read after a session, so this must not clobber it.
set "LOGF=%PROJ%\rt-console-unseenevil.log"

rem ---- leading keywords -----------------------------------------------------
rem ONE loop for all of them, deliberately, so they compose in ANY order. Written
rem first as two separate "if ... shift" blocks, which worked for "bare doom1" and
rem quietly broke "doom1 bare": the second keyword had already slid into %1 by the
rem time its own test was reached, so it fell through to the map parser and became
rem "+map bare". Consuming them in a loop removes the ordering entirely.
set "WANT=doom2.wad"
set "STARTMODE="
:flags
if /i "%~1"=="bare"  ( set "PATCHES=" & set "KEYLIGHTS=" & set "GRILLE=" & set "MONLIGHTS=" & set "LIQUIDS=" & set "LIQUIDART=" & set "POISONFX=" & set "LAVAFX=" & set "AUTO=" & shift & goto :flags )
if /i "%~1"=="doom1" ( set "WANT=doom.wad" & shift & goto :flags )
if /i "%~1"=="nolights" ( set "AUTO=" & shift & goto :flags )
if /i "%~1"=="min" ( set "STARTMODE=/min" & shift & goto :flags )

rem Steam's modern "Ultimate Doom" depot is a BUNDLE: one app folder holds every
rem classic IWAD, with DOOM.WAD at base\ and the rest one level down in
rem base\doom2\, base\tnt\, base\plutonia\. Both layouts are searched.
rem
rem base\ IS PREFERRED OVER rerelease\ ON PURPOSE, and the order below is the
rem whole of that decision. The 2024 KEX re-release ships its own doom.wad and
rem doom2.wad next to the classic ones with DIFFERENT contents and sizes
rem (doom2: 14951361 vs the classic 14604584). AGENTS.md pins 14604584 as the
rem known-good size for this project and warns against a differently-sized copy,
rem so rerelease\ is never listed here -- if it were found first, everything
rem downstream would silently be running against a different game.
if not defined D64RT_UE_IWAD (
  for %%W in (
    "D:\Games\GZDoom\%WANT%"
    "G:\SteamLibrary\steamapps\common\Ultimate Doom\base\%WANT%"
    "G:\SteamLibrary\steamapps\common\Ultimate Doom\base\doom2\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\base\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\masterbase\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base\%WANT%"
    "%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base\doom2\%WANT%"
    "C:\Program Files (x86)\GOG Galaxy\Games\DOOM II\%WANT%"
    "%USERPROFILE%\Documents\GZDoom\%WANT%"
    "%PROJ%\%WANT%"
  ) do if not defined D64RT_UE_IWAD if exist %%W set "D64RT_UE_IWAD=%%~W"
)
set "IWAD=%D64RT_UE_IWAD%"
if not exist "%IWAD%" (
  echo ERROR: no %WANT% found.
  echo        Unseen Evil is an overhaul mod -- it needs a DOOM IWAD you own.
  echo        Set D64RT_UE_IWAD to its full path, e.g.
  echo          set "D64RT_UE_IWAD=C:\Path\To\%WANT%"
  exit /b 1
)

rem ---- files ----------------------------------------------------------------
if not exist "%MOD%" (
  echo ERROR: missing %MOD%
  exit /b 1
)
if not exist "%TONE%" (
  echo ERROR: missing %TONE%
  echo        Build it with: python tools\tone_unseenevil_brightmaps.py --write
  exit /b 1
)
rem Absent is not an error: it is gitignored, and "nolights" clears it on purpose.
if not exist "%TEXFIX%" set "TEXFIX="
if defined TEXFIX set "TEXFIX="%TEXFIX%""
if not exist "%PICKLT%" set "PICKLT="
if defined PICKLT set "PICKLT="%PICKLT%""
if not exist "%RTMENU%" set "RTMENU="
if defined RTMENU set "RTMENU="%RTMENU%""
if not exist "%SKYRT%" set "SKYRT="
if defined SKYRT set "SKYRT="%SKYRT%""
if not exist "%LIQANIM%" set "LIQANIM="
if defined LIQANIM set "LIQANIM="%LIQANIM%""
if not exist "%AUTO%" set "AUTO="
if defined AUTO set "AUTO="%AUTO%""

rem ---- passthrough ----------------------------------------------------------
rem Collect the post-"--" passthrough without disturbing %1 parsing above.
set "EXTRA="
set "SEEN_SEP="
for %%A in (%*) do (
  if defined SEEN_SEP (
    set "EXTRA=!EXTRA! %%~A"
  ) else (
    if "%%~A"=="--" set "SEEN_SEP=1"
  )
)

rem ---- map ------------------------------------------------------------------
rem "menu" boots to the title screen with the identical file list and pins.
rem +map jumps straight into play, so the title and intermission screens are
rem otherwise unreachable from here -- and Unseen Evil has a custom TITLEMAP.
set "MAPARG=+map"
set "MAPNUM=%~1"
rem THE SEPARATOR IS NOT A MAP NAME. After the keyword loop has consumed e.g.
rem "doom1", %1 can be the "--" that introduces the passthrough, and it fell
rem straight through to the lump-name branch as "+map --" -- which boots to a
rem dead start screen with an almost empty log, looking like a crash rather than
rem a bad argument. Blank it and the default map logic below takes over.
if "%MAPNUM%"=="--" set "MAPNUM="
if /i "%MAPNUM%"=="menu" (
  set "MAPARG="
  set "MAPLUMP="
  goto :launch
)
if "%MAPNUM%"=="" set "MAPNUM=1"
if /i "%WANT%"=="doom.wad" if "%MAPNUM%"=="1" set "MAPNUM=e1m1"

rem A number means a DOOM II map slot; anything else is a lump name and goes
rem through untouched, which is what makes e3m8 / 64UE_SIN / TITLEMAP work.
set /a "N=MAPNUM" 2>nul
if errorlevel 1 goto :byname
if %N% LSS 1 goto :byname
if %N% GTR 32 goto :byname
if %N% LSS 10 (set "MAPLUMP=map0%N%") else (set "MAPLUMP=map%N%")
goto :launch

:byname
set "MAPLUMP=%MAPNUM%"

:launch
cd /d "%ENGINE%" || (
  echo ERROR: engine build not found at %ENGINE%
  echo        Build it with: tools\build-gzdoom-rt.cmd
  exit /b 1
)

echo Unseen Evil ^(RT^)
echo   iwad    %IWAD%
echo   mod     %MOD%
echo   tone    %TONE%   ^(18 brightmaps 255 -^> 192^)
if defined PATCHES (echo   patches %PATCHES%) else (echo   patches none ^("bare"^))
if defined AUTO (echo   lights  autolights ON) else (echo   lights  none ^("nolights"^))
echo   map     %MAPLUMP%
echo   log     %LOGF%
echo.
echo   Nine "Unknown command rt_gore_*" lines at startup are EXPECTED here: those
echo   cvars are declared by Retribution's blood pk3, which cannot load on DOOM.
echo.

rem The tone overlay is listed LAST so it wins the load order. The pins run
rem before +map, and %EXTRA% runs last so a one-off cvar still beats a pin --
rem the same ordering contract as launch-retribution-rt.cmd.
rem
rem -nostartup IS LOAD-BEARING, not tidiness. Unseen Evil's GAMEINFO sets
rem STARTUPTYPE = "Hexen", so GetGameStartScreen() builds a Hexen start screen.
rem d_main.cpp then takes its OTHER branch -- V_Init2() EARLY, under the start
rem screen, followed by StartScreen->Render() -- and that Render draws through a
rem just-created RTGL1 renderer and dies with an access violation. The dialog it
rem raises is "GZDoom Very Fatal Error", which MASKS whatever the real error was,
rem so this also hid a ZScript failure underneath it for the whole investigation.
rem -nostartup makes GetGameStartScreen return nullptr, which is the LATE path --
rem the one Retribution has always used, because it is GAME_Doom and never
rem matched the Hexen/Heretic/Strife branches in the first place.
rem
rem rt_mod_compat 0 IS WHAT MAKES THE MOD'S ART APPEAR, and it goes AFTER +exec
rem so it beats the pins file (which sets 1).
rem
rem     src/playsim/p_sectors.cpp:1432
rem         void FLevelLocals::ReplaceTextures(...) { if( rt_mod_compat ) return; }
rem
rem Unseen Evil retextures DOOM 1/2 maps at runtime: its D64UE_Terraformer_Event
rem reads resources/d64ue_textures.* (285 mappings in the root table alone,
rem BROWN1 -> textures/pepy/d64_brown1 and so on) and applies them through
rem level.ReplaceTextures in WorldLoaded. With rt_mod_compat non-zero every one
rem of those calls returns immediately, in silence -- no warning, no log line --
rem so the mod appears to load correctly while showing stock DOOM II walls with
rem Doom 64 sprites in front of them.
rem
rem Measured on doom2 MAP01 with a ZScript census of every sidedef:
rem     rt_mod_compat 1 -> walls mod=3   stock=387, flats mod=0
rem     rt_mod_compat 0 -> walls mod=334 stock=56,  flats mod=17
rem
rem THE MOON GOES OFF, and this is a content decision rather than a taste one.
rem d64rt-pins.cfg turns it on (rt_sun 1, intensity 90, aimed 25/135) because
rem Retribution's maps were BUILT around a moonlit sky -- their openings are placed
rem where that bearing can honestly reach. DOOM 1/2 maps were not: they are full of
rem F_SKY1 ceilings over rooms with no opening the light could arrive through, so a
rem directional at a fixed bearing rakes straight into sealed interiors and the
rem whole level reads as leaking. rt_sun_require_sky trims some of it, not enough.
rem
rem The four *_presets 0 go with it for the reason rt_presets.cpp now enforces
rem engine-side: those tables are keyed on BARE map names measured on Retribution,
rem so DOOM II's MAP22/23/24/25/26/28/31/32 collide with Retribution rows by name
rem alone. The engine guard makes these redundant on IWAD maps; they are kept
rem because Unseen Evil's own 64UE_* maps are PWAD maps and so remain eligible.
rem
rem Keep this command line SHORT. The Retribution launcher once spelled every
rem pin out here, hit cmd.exe's 8191-character limit, and silently dropped the
rem trailing passthrough while still printing the values it believed it had set.
rem That is why the pins live in a cfg and arrive via +exec.
rem WINDOWED 960x540, PINNED TOP-LEFT. -width/-height set the RENDER size and do
rem not size the window at all; only vid_defwidth/vid_defheight do, which is why
rem the old line above them still opened a full-desktop window.
start "" %STARTMODE% gzdoom.exe ^
  -iwad "%IWAD%" -file "%MOD%" %PATCHES% "%TONE%" %TEXFIX% %LIQANIM% %SKYRT% %PICKLT% %RTMENU% %KEYLIGHTS% %GRILLE% %MONLIGHTS% %LIQUIDS% %LIQUIDART% %POISONFX% %LAVAFX% %AUTO% -rtnolauncher -nostartup ^
  +vid_fullscreen 0 +vid_defwidth 960 +vid_defheight 540 +win_x 0 +win_y 0 ^
  +logfile "%LOGF%" ^
  +exec "%PINS%" ^
  +exec "%LIGHTCFG%" ^
  +rt_mod_compat 0 ^
  +rt_sun 0 +rt_sky 25 +rt_moon_geo 0 +rt_moon_presets 0 +rt_clouds_presets 0 +rt_fog_presets 0 ^
  +rt_volume_shaft_mult 0.1 ^
  +rt_keytrim_lights 0 ^
  +rt_ue_keytrim_emis 0.5 ^
  %MAPARG% %MAPLUMP% %EXTRA%
exit /b 0
