NOTE: For best reading, make sure Word Wrap is off!

  ________________________________________________________________________________________________
 |                                                                                                |
 |                                      Doom 64: Retribution                                      |
 |                                       README AND CREDITS                                       |
 |________________________________________________________________________________________________|


/* --- TABLE OF CONTENTS ----------------------------------------------------------------------- */

Refer to line numbers to jump to a section.
 _________________________________________________________________________________
|      |                                                              |           |
|  01  |  OVERVIEW                                                    |  Ln 35    |
|  02  |  CONTENTS OF ZIP FILE                                        |  Ln 54    |
|  03  |  FEATURES OF THE TOTAL CONVERSION                            |  Ln 96    |
|  04  |  SUGGESTED SETTINGS                                          |  Ln 211   |
|  05  |  MOD SPECIFIC CVARS                                          |  Ln 253   |
|  06  |  BUG REPORTING                                               |  Ln 428   |
|  07  |  MAKING THE MOD WORK ON SOME OLDER VERSIONS OF GZDOOM        |  Ln 705   |
|  08  |  INTENDED CHANGES FROM THE ORIGINAL                          |  Ln 745   |
|  09  |  CHANGES ON THE ABSOLUTION TC'S EXCLUSIVE MAPS AND FEATURES  |  Ln 780   |
|  10  |  THE UNFINISHED OUTCAST LEVELS                               |  Ln 866   |
|  11  |  CHANGES ON THE REDEMPTION DENIED MAPS                       |  Ln 899   |
|  12  |  DOOMSLAYER DIFFICULTY INFORMATION                           |  Ln 988   |
|  13  |  USING THE 20TH ANNIVERSARY SOUNDTRACK                       |  Ln 1063  |
|  14  |  CREDITS                                                     |  Ln 1194  |
|  15  |  MAKING NEW MAPS FOR THE MOD                                 |  Ln 1301  |
|  16  |  FINAL REMARKS                                               |  Ln 1309  |
|______|______________________________________________________________|___________|



/* --- OVERVIEW -------------------------------------------------------------------------------- */

This project is a full re-make and "port" of Doom 64 for the Nintendo 64 to the GZDoom engine. The
goal of the project is be mostly accurate to the original game as well as add very minor improvements
for that extra bit of polish. Think of this mod as being a remastered or updated version of Doom 64
for GZDoom. We have Doom 64 EX, Doom 64 Absolution TC, GZDoom64, and Brutal Doom 64. Why you ask? I
was personally dissatisfied with the quality of the GZDoom64 project, and Brutal Doom 64 (while it
is a great improvement) is along the same lines but changes too much and deviates from the original
Doom 64 experience. And thus, this project was born.

NOTICE: The minimum required version of GZDoom is 2.4.0 for the mod to run with no errors!
Zandronum 3.0 is NOT supported! Future versions of Zandronum may be able to run the mod.

DISCLAIMER: This project will NEVER be completely faithful or accurate to the original game. If you
absolutely must have accuracy, use Doom 64 EX instead. The point of this TC is specifically to be
a remade version of Doom 64 for GZDoom.



/* --- CONTENTS OF ZIP FILE -------------------------------------------------------------------- */

There should be nine (9) files and one (1) folder included inside the ZIP file you downloaded:

  1) d64rtr.ico
     An icon that you can use for a shortcut to launch the mod (safe to delete).

  2) D64RTR[v1.5].WAD
     This is the main mod file. This is the only file you need to actually run the mod.

  3) D64RTR_BRIGHTMAPS.PK3
     Brightmaps in a separate file, the same way with GZDoom's brightmaps.pk3 file.

  4) D64RTR_CHANGELOG.TXT
     A text file for keeping up with changes across future versions of the mod (safe to delete).

  5) D64RTR_INSTRUCTIONS.TXT
     An important text file for explaining how to set up the MIDI playback and run the mod (safe to delete).

  6) D64RTR_README.TXT
     A text file you are currently reading, which has all the mod's info and credits (safe to delete).

  7) DOOMSND.SF2
     The Doom 64 soundfont which is required for the MIDI playback to sound right.

The following two files will only be needed depending on which version of GZDoom you are using.

  8/9) libfluidsynth.dll / libfluidsynth64.dll
         A DLL file which allows gzdoom.exe to use fluidsynth for MIDI playback.
         NOTE: If you are on 64-bit version of GZDoom, use "libfluidsynth64.dll" instead.

If you are on a newer version of GZDoom where fluidsynth is already included by default since
the removal of FMOD, you can delete the two DLLs included in this ZIP and just set the fluid
patchset and you are done. Otherwise, you will need one of the two DLLs for the music to work.

Also, the one folder included named "D64RTRDEV." This folder contains porting guides for
converting maps to the TC and the D64FADES.PK3 ACS file needed to use the spawning
functions for fade spawning (used for making maps only). Refer to the text file inside
of this folder that goes into greater detail.



/* --- FEATURES OF THE TC ------------------------------------------------------------------------------------------ */

> All original Doom 64 maps converted directly from the source files into UDMF

> Recreated the Doom 64 lighting effects with standard sector colors (PSX style) and dynamic lights
  (this is mainly due to engine limitations, but as GZDoom adds better support this will be fixed)

> Converted the six exclusive maps from the Absolution TC and put them into their own episode
  (accessible from the episode selection screen as a standalone episode)

> Converted the "Outcast Levels" expansion from the Absolution TC (by Kaiser)
  (original 8 maps and 3 new maps, accessible from the episode selection screen)

> Converted the "Redemption Denied" expansion from the Absolution TC (by AgentSpork and Steven Searle)
  (original 8 maps, accessible from the episode selection screen)

> Remade Doom 64's MAP33 title sequence into a TITLEMAP for the menu screen

> Emulated intermission text screens with the fading and scrolling text lines using dummy maps

> Recreated Doom 64's method of "fading in" monsters and items with custom ACS spawning functions

> Transformed the "Features" menu from the original into a menu for the mod-specifc CVARs

> New introduction text screen which tells "the story so far" from the game manual
  which can be skipped at any time or turned off completely in the features menu

> Fixed any obvious bugs or mismatched and misaligned textures present on all levels

> Minor fixes made to maps (small things to improve the overall experience visually or
  otherwise; maps will never deviate from the original gameplay design)

> Map order is identical to the original map flow from the original N64 game

> Intermission stat screens properly show before entering the secret levels

> The original "bonus fun maps" were added into a simple hub style selection map

> The TITLEMAP level is also a playable fun map accessible from the hub as well

> Testing map included where every monster, weapon, item, pickup and prop can be
  seen as well as an arena where you can pit monsters against each other (12v12)

> Since a locked cheat menu is not feasible in GZDoom, the reward for completing Hectic
  is now a Megasphere (what you would get from the traps) and some early cell ammo

> Recreated special Doom 64 effects, like fake 3D architecture, with proper 3D floors

> For now, the lighting system is emulated with basic GZDoom sector light colors

> Doom 64's unique "center-split" doors recreated using scripts and sound sequences

> Changed Breakdown's (MAP20) "sliding door" effect into polyobjects

> Redid the scrolling cloud sky effects with actual skyboxes, cloud textures and
  translucent 3D floors with floor and ceiling scrolling actions

> Matched up the original skies with the right color clouds from the original game

> Fresh hand-written scripts for each map which accurately recreate the original
  events and puzzles

> All weapons have the original recoil and push-back effects on them

> Unmaker recreated as accurately as possible in GZDoom and still uses cells for ammo

> Unmaker upgrades recreated and correctly upgrade the weapon's number of beams

> The upgrades the player has will appear at the top of the automap screen

> Doom 64's unique HUD recreated and is used to replace the normal status bar as
  well as GZDoom's standard HUD

> GZDoom's alt-hud is left unchanged and is still available for use if preferred

> Player view height and size modified to match with Doom 64's larger map and sprite scale

> Player speed and gravity slightly adjusted to behave more like Doom 64 which takes
  the game speed and tic-to-seconds ratio into account

> Recreated and remade every Doom 64 monster, item, pickup, and static map prop

> Included special versions of some things for map scripting effects (like an unlit
  candle, dummy keys, and more)

> No additional enemies, gore effects, or over the top map effects or lights

> Simple usage of dynamic lights (such as around key bars or monitors) to enhance
  the atmosphere

> Recreated the original reverb effects on every map with custom reverb definitions
  (reverbs can be turned off in the Doom 64 Features Menu)

> Level names and the authors of the maps will fade in when each map loads
  (can be turned off seperately in the Doom 64 Features Menu)

> Completely remastered weapon animations which are smoother and have new frames
  (can be changed to the classic Doom 64 animations in the Doom 64 Features Menu)
  Credit and thanks goes to Cage and Almonds for the awesome new animations!

> All weapons are more responsive to use, better synced with their sounds, and swap faster

> Bullet and shell casings can be turned on so they are ejected from their respective weapons
  (can be changed in the Doom 64 Features Menu)

> All levels fade in from black and freeze then fade out to red and black like the originals
  (can be turned off seperately in the Doom 64 Features Menu)

> Added the option to turn off the auto switch to Fists when taking Berserk packs
  (can be changed in the Doom 64 Features Menu)

> Many more other small things that I can't think of or list by themselves!



/* --- SUGGESTED SETTINGS ---------------------------------------------------------------------- */

I suggest playing with the following settings set for maximum quality of play:

  - Texture filtering set to "none (linear mipmap)"
  - Anisotropy set to 8X (or 16X, but 16X looks the same as 8X to me)
  - No high quality resizing mode set
  - Sector light mode set to "dark" (maps default to this anyway)
  - Fog mode set to "radial"
  - Sound channels set to 64 or more
  - No jumping or crouching, many maps could potentially break if you do (both disabled by default)
  - Freelook / Mouselook is your choice, I personally use it
  - Autoaim is also up to you, but I prefer not to use it
  - Make sure always run is on so all gaps are clearable
  - Show ammo for "available weapons" only
  - Sprite clipping set to "smart" or "smarter"
  - Sprite billboarding set to Y-axis (if using freelook / mouselook)
  - Screen wipe type set to "none"
  - Enhanced night vision mode enabled (normal mode kills sector colors, green is better than nothing)
  - Load the brightmaps PK3

If you want to experience the TC in a more retro way (closer to the N64 with CRT TV) you can try these settings:

  - Resolution set to 640x480 (lowest you can go in GZDoom options)
  - Lens distortion and Hejl Dawson tonemap enabled (requires gl_renderbuffers 1)
  - No forced aspect ratio (or 4:3 if forced)
  - Texture filtering set to Linear
  - No anisotropy
  - No high quality resizing
  - Dynamic lights disabled completely
  - Jump and crouch disabled
  - Free look disabled
  - Autoaim enabled (how much is up to you)
  - No crosshair
  - Keep the Doom 64 HUD in use at all times
  - Classic animations enabled
  - Classic pickup sprites enabled
  - Drop casings disabled
  - Do not load the brightmaps PK3



/* --- MOD SPECIFIC CVARS ---------------------------------------------------------------------- */

This mod adds a handful of new console variables to modify and alter the gameplay and also gives
the players a lot more options and customization of their experience. Note that all of these are
server CVARs. This was done to always ensure that a desync will never happen due to differences.

These settings can be changed in three ways:

  1) Through the menu by going into Options and then to Doom 64 Features at the very bottom
  2) Through the console by typing the CVAR name and changing them here
  3) Manually edit them in the "gzdoom-NAME.ini" config file that GZDoom creates


Here is a list of all new CVARs and what they control, along with their default values.


  "d64_gametimer"   0|1   (default = 0)

    This setting is mainly meant to control which delay duration gets used on the TITLEMAP
    and MAP33: Titlemap so that the music change happens at the right time across all
    versions of GZDoom. Essentially, in older versions of GZDoom, the game ran at 35.5
    FPS versus the exact 35 FPS. This resulted in a slightly accelerated "playsim."

    To keep things simple, if you are using newer versions of GZDoom, you never need to
    change this setting. However, if you are on say, version 2.2.0 (like me), then you
    will need to make sure this is set to Legacy (or 1). The only effect this setting
    has is in determining how long certain non-critical delays will last for.


  "d64_flashtrans"   0|1   (default = 0)

    This determines if the weapon flashes for supported weapons are translucent (like in
    the original game) or opaque. As of version 1.5, only the Rocket Launcher is currently
    supported (it uses the frames from the Absolution TC).


  "d64_plasrendstyle"   0|1   (default = 0)

    Determines if the classic animation for the Plasma Rifle fires classic style opaque
    plasma projectiles or additive like the modern animations. Just a simple aesthetic
    choice for that extra touch of "classic-ness."


  "d64_invulstyle"   0|1|2|3|4|5   (default = 0)

    Controls the type of screen effect when picking up an Invulnerability Sphere. If set to 0, the
    default Doom 64 style of making the screen blend white is used. If set to 1, the classic Doom
    effect of making the entire screen white and black (or inverted map) will be used. If set to
    the other settings, other modes such as GoldMap or GreenMap will be used.


  "d64_exitfade"   0|1   (default = 1)

    Controls whether or not the screen should fade and melt into red then black and freeze the
    player when ending a level. If set to 0, the map will not do the above effects. If set to 1,
    ending a level will fade the screen and freeze the player and sounds like the original game.


  "d64_enterfade"   0|1   (default = 1)

    Controls whether or not the screen should fade in from black when starting a new level. If
    set to 0, the screen will not fade in and will instead instantly be fully visible. If set
    to 1, the screen will fade in from black upon beginning a new level like the original game.


  "d64_noberserkswitch"   0|1   (default = 0)

    Controls whether or not picking up a Berserk Pack should automatically switch to the fists
    when taking it. Sometimes the auto switch to fists is bothersome so this allows you to
    disable it and switch to fists manually when you are ready to use the fists.


  "d64_authornames"   0|1   (default = 1)

    Controls whether or not the name(s) of the author of the current map fades in along the top
    center of the screen with the name of the level above it. This was added in 1.5 so that the
    original authors of the maps can have their names paired with their maps, much like what was
    done in the original Absolution TC. These can be turned off separately from the map names,
    however the author names require the level names to be on for them to appear.


  "d64_levelnames"   0|1   (default = 1)

    Controls whether or not the name of the current level fades in along the top center of the
    screen when loading that level. The purpose was to give a cool introduction to each map
    but it can be turned off for the sake of originality.


  "d64_reverbs"   0|1   (default = 1)

    Controls the activation of reverb effects on every map. Turning this off will cause the
    sound environment things placed on the map to be removed. Leaving it on will instead
    activate them to produce the original reverb effects. Changing this value requires a
    restart of the current level to see any effect. Restarting the game is required to
    fully remove the reverb effects, since menu sound popping may remain until restarted.


  "d64_skiptitlemap"   0|1   (default = 0)

    If set to 1, the TITLEMAP sequence will not play and the game will go to the static
    background image right away after showing the credit image. If set to 0, the TITLEMAP
    sequence will play out as normal. The sequence is cool but eventually it may get old
    to always see it play out every time you run the mod.


  "d64_skipintro"   0|1   (default = 0)

    This allows you to always skip the Story so Far introduction story sequence. Think
    of this setting as a shortcut to skipping it when it loads up normally. This is so
    that you always get right into Staging Area when starting a new game.


  "d64_dropcasings"   0|1   (default = 0)

    This determines if casings should be ejected from the Pistol, Shotgun, Super Shotgun,
    and Chaingun. If set to 0, no casings will be ejected. If set to 1, the weapons in
    this list will eject casings like in reality. Casings will also vanish if they hit
    sky and plop into water if they hit a liquid (however this only works on surfaces
    that are liquid BEFORE any casings hit them).


  "d64_classicdrops"   0|1   (default = 0)

    Since version 1.0 of the mod, the pickup sprites for the Shotgun and Super Shotgun
    were altered to appear more realistic and also to appeal to the modern animations
    to be improved and modernized as well. Now in 1.5 onwards, you can set this option
    to classic to get the original Doom 64 versions of these pickup sprites. This can
    be changed and used separately from the animations. The only thing that doesn't
    change is the inventory sprites on the alt-hud. They always use the improved
    versions, simply because it's not possible to change those with a CVAR setting.


  "d64_classicanims"   0|1   (default = 0)

    The most important CVAR: controls which animation set the player's arsenal will use.
    If set to 0, the weapon animations will be the newer and enhanced versions from
    various authors. If set to 1, the animations will be the original Doom 64 style
    versions used in the original game.


  "d64_worldsounds"   0|1   (default = 0)

    Controls the activation of extra ambient world sounds on some maps in specific places.
    Turning this off will cause the ambient sound things placed on the maps to be removed.
    Leaving it on will instead activate them to enable some extra sound effects. Changing
    this value requires a restart of the current level to see any effect.

    NOTE: Currently hardly any maps have extra sounds. They may or may not be removed in
          future versions of the mod. In my opinion, it begins to reach into "feature
          bloat" territory. Staying as a lightweight and simple TC was and still is one
          of my goals. I didn't have much time to add many, so it may be a good thing.


Here is what a typical list of them (defaults) will look like inside your INI file:

   [Doom.LocalServerInfo.Mod]
   d64_worldsounds=0
   d64_skiptitlemap=0
   d64_skipintro=0
   d64_reverbs=1
   d64_plasrendstyle=0
   d64_noberserkswitch=0
   d64_levelnames=1
   d64_invulstyle=0
   d64_gametimer=0
   d64_flashtrans=0
   d64_exitfade=1
   d64_enterfade=1
   d64_dropcasings=0
   d64_classicdrops=0
   d64_classicanims=0
   d64_authornames=1



/* --- BUG REPORTING --------------------------------------------------------------------------- */

The versions of GZDoom which are used for the mod's development:

  > 2.4.0 is the MINIMUM required version for the mod to start up and provide the intended experience
  > The mod is designed and developed on 2.2.0 due to my own issues with modern versions of GZDoom
  > Versions older than 2.2.0 may or may not work, but they will all require the MENUDEF fix (see below)
  > Future versions should be safe and should work; if not, report the error(s) on the ZDoom Forums!
  > The mod may or may not work on other source ports (Zandronum 3.0 and older is not supported)


Some things are different between various versions of GZDoom. For example, sound effects that use the auto
sound channel may work differently resulting in a different combined sound. The Chaingun and Plasma Rifle
sound much better when rapidly fired on older versions; 2.2.0 produces the intended sounds.

Please report any bugs at the project's thread on the ZDoom forums, the thread on DoomWorld forums,
or in the Bug Reporting forum section on the project's ModDB page. The links are below:

      MODDB: http://www.moddb.com/mods/doom-64-retribution/forum
      ZDOOM: https://forum.zdoom.org/viewtopic.php?f=19&t=55039
  DOOMWORLD: https://www.doomworld.com/vb/wads-mods/91854-wip-doom-64-retribution/


The following are either NOT bugs or already known so please do not report them:

(!) THE SECRET MESSAGE IS WRONG!
You are probably on an older version of GZDoom before the secret message cvar was moved to the
LANGUAGE lump. The way to fix this is to edit the "secretmessage" cvar in your INI file. Change
it so that it reads: "secretmessage=You found a secret area!" This will match up to what the
message is supposed to be from Doom 64.

(!) ON MAPS WITH FOG, THE WEAPON SPRITES ARE FULLBRIGHT AND NOT BEING COLORED!
This seems to be a bug present in 2.0.05 that I don't know how to fix. It works and looks fine
in version 2.2.0 so there's most likely nothing I can do about that. I have no idea what is
actually causing it.

(!) I HEAR EARTHQUAKES, BUT THERE'S NO SHAKING!
Once again this seems to be a problem in 2.0.05 and possibly older. Basically what is happening
is the Radius_Quake that is called seems to have no effect on the map when called via an OPEN
or ENTER script on a MapSpot thing. Only fix for this is to rewrite the scripts to run the
quake via a void or ENTER script when needed, but this bug is only in a couple spots.

(!) I CAN ACTIVATE SHOOTABLE SWITCHES BY FIRING OVER THEM!
This isn't actually a bug I don't think, it's just the way the Doom engine works. If a shootable
switch is recessed into a wall then there is no problem. This also isn't a problem if you play
without mouselook. Fortunately there are not any switches that can be shot over to provide any
kind of early advantage or cheat of any kind, so the impact is minimal.

(!) THE LEVELS THAT SHOULD HAVE FOG HAVE NO FOG!
You most likely have fog turned off. Make sure "Fog Mode" is set to Standard or Radial (I prefer
Radial) in OpenGL Preferences. If you are on a different engine such as QZDoom the fog will not
work either due to the fact that QZDoom is still a software renderer. Fog only has effect in
hardware renderers.

(!) MONSTERS RANDOMLY GLOW BRIGHTER AT SOME SPOTS OF THEIR SPRITES!
You may be loading a brightmaps mod alongside this, such as SBrightmaps.pk3. Make sure
nothing like this is being autoloaded in your INI.

(!) I GET RED WARNINGS DURING STARTUP FOR "PIXELRATIO" AND "NOINFIGHTING!"
This is normal if you are on an older version of GZDoom which does not support these
properties in their respective MAPINFO blocks. The game is still perfectly playable
but may have missing effects or actions.

(!) I HEAR SOUND POPPING OR CRACKLING WHEN PICKING UP ITEMS AND WITH OTHER SOUNDS AS WELL!
This is the biggest pain in the ass problem that I've had to deal with while making the TC. The
bad news is I don't know how to fix it. It either has to do with the sudden amplitude shifts
of the sound playing agian or the fact that the item pickup sound is always played on the same
sound channel for the player actor. One way to possibly fix it is to recode every single item
pickup to play the item pickup sound on CHAN_AUTO when being taken and nullify the actual
pickup sound. It may also not happen while using the OpenAL sound backend but I am unsure.

(!) I HEAR STATIC SOUNDS WHILE USING CERTAIN GUNS!
This is due to sound channels and using the automatic channel for lots of things. Unfortunately
this can have a side effect of becoming somewhat obnoxious at times. The reason this was even done
was to achieve the proper sound of weapons to match the original game as close as possible and to
reduce popping from the above point.

(!) THE MUSIC STARTS MAKING STATIC SOUNDS OR MAKES THE AUDIO MUFFLED!
This is about as big of a pain as the other point above. This is something that is not easily
fixed because the problems lie in the MIDI files themselves and possibly the soundfont. The
main reasons I decided to use the MIDIs for the music is because they had the best and clearest
sound compared to recordings, because they save a LOT in the file size, and also because they
are right from the source. If it becomes unbearable for you, there is an OGG PK3 music pack that
is uploaded to the ModDB page for the mod under "files" that can be loaded after the main mod
file and all the MIDIs will be replaced by OGGs, meaning those problems will be gone. You may
also try reducing the FluidSynth gain to 0.5 in advanced sound options.

(!) I HEAR A POPPING SOUND WHEN CHANGING HUD SIZE OR OPTIONS IN THE MENU!
This is a side effect of non-zero sound environment things being activated. Odds are, you have
Map Reverbs enabled in the Doom 64 Features Menu. This is unavoidable, and is also one of the
major reasons for making the reverbs into an option to begin with. The only way to get rid of
this popping is to not use reverbs. Make sure you have restarted the game after disabling them
to fully stop the popping.

(!) I SEE THE HUD DURING INTERMISSION TEXT SCREENS AND THE INTRO!
If you are using the alternative HUD with G/ZDoom, it will still appear. The same goes for the
automap. I don't think it's possible to hide the alternative HUD or automap like the others
during these moments. Using the normal G/ZDoom HUD or Status Bar (which is replaced with Doom
64's) will make it be hidden as expected. This will also occur with custom HUD mods because
the HUD doesn't do a specific check to see if it should be hidden. Custom HUDs will need to
be patched to include this check.

(!) THE UNMAKER UPGRADES HAVE THE WRONG PICKUP MESSAGES!
I decided to change which artifacts give which message. It made more sense to me to change
it so the first artifact found in a UAC base says that it doesn't belong in that world
(which is true, it doesn't), the second artifact simply makes you wonder what they do,
and finally the third one on the In the Void map gives the message about feeling like
it wasn't to be touched. This is because a quake happens and monsters spawn right after.
Almost makes you wonder if Midway themselves got them wrong.

(!) MAPS ARE TOO BRIGHT WHEN THEY SHOULD LOOK DARKER!
Make sure your sector light mode is Dark, Doom, or Software. I personally recommend Dark
so you don't get that radial glow around you. The maps should automatically default to this,
so if they are still too bright, check your brightness, gamma, and contrast settings.

(!) WEAPON CASINGS DON'T EJECT WHEN I POINT MY GUN STRAIGHT UP OR DOWN!
This is due to using A_SpawnItemEx instead of something else that can preserve player aim
pitch. I tried using another way that would, but could not for the life of me figure out
how to set up the angle and pitch to look the same as A_SpawnItemEx does. It's not that
noticable unless you are firing straight up or down with mouselook on.

(!) UNMAKER LASER NOT SHOWING UP WHEN FIRING CLOSE RANGE!
Why this happens I'm not exactly sure, but it probably is caused by there not being enough
room in front of the player to spawn all the trail sprites in that small space, and thus the
laser goes straight to the wall or monster and dies as usual without showing up. I am not sure
if there's any way to change this behavior without changing the entire projectile code.

(!) MUSIC CUTS OFF EARLY DURING STORY SO FAR AND FINALE!
This is an apparent problem in the MIDI itself. In different versions of GZDoom it will actually
behave differently. In older versions the MIDI will cut off and stop for a couple seconds, then
restart on it's own. In 2.2.0 and newer it should loop without cutting off but still will not
loop quite correctly.

(!) LIGHT AMP GOGGLES TURN THE WHOLE MAP GREEN OR WHITE!
Yes, this is due to the way GZDoom or the Doom engine in general handles the powerup and
lighting the sectors. Every sector will get 255 brightness and fullbright white. Even dynamic
lights are ignored. There's no way to change this behavior currently, so I have reduced the
duration of the goggles to 30 seconds instead of 2 minutes. In the future when proper Doom 64
style lighting is introduced, it will no longer do this since those colors are material colors
applied to the geometry instead of a single color for the whole sector. For the time being I
recommend using the enhanced mode. Green looks better than white in Doom 64.

(!) LIGHT AMP GOGGLE DURATION IS VERY SHORT!
Due to the above problem of them not being able to preserve sector colors, I decided to cut
their duration from two minutes to thirty seconds. The goggles only even appear in two maps
in the original game anyway.

(!) CASINGS FROM WEAPONS GLIDE OR FLOP AROUND ON LIFTS!
This is due to the game not recognizing that the casing actor has hit a solid floor. Somehow
and for some reason the casing thinks it's still flying through the air and so it will glide
on the floor until it reaches its max bouncecount amount, then it stops. No clue how to fix
this one, but it doesn't cause issues. It just looks bad.

(!) THE SPLIT DOOR BREAKS AND ONE HALF STAYS OPEN!
This seems to be an extremely rare circumstance where you managed to hit your head on the
bottom of the door before the floor of the bottom half pushed your body up to hit your head
from that and made both sections re-open. It's very rare to have happen unless you are trying
to do it on purpose. I don't think there is any fix for this but luckily it doesn't actually
break the door but instead just looks bad if it does manage to occur.

(!) THERE IS A MISSING ROW OF PIXELS AT THE BOTTOM OF THE GUN SPRITES!
This is happening because many of the first person sprites were resized manually using the
TEXTURES lump so that they appear as they should with a 1:1 pixel ratio as Doom 64 did. I
tried to get them right at the edge of the screen and they should be when in full view, but
if your screen is shrunk down (screenblocks set to 7 in 4:3 aspect ratio) then you may see
this line of missing pixels. Changing your view size will fix it.

(!) ARACHNOTRONS FAIL HARD AT INFIGHTING, THEY ARE JUST SHOOTING WALLS!
Yes. Unfortunately due to moving the origin of their attack projectiles and the upscaled
map sizes, this causes them to simply shoot walls or the ground when aiming down at an
enemy they may be fighting with and sometimes the player. This can be easily observed in
the outside area on MAP15 Dark Entries. There is really no way that this can be fixed
that I know of.

(!) BARRELS SINK INTO THE GROUND AND MONSTERS FLOAT ABOVE THE GROUND!
This is a side effect of loading the mod as an IWAD using the -iwad parameter instead of
the preferred -file along with choosing DOOM2.WAD as the IWAD (should auto load DOOM2.WAD
regardless, if it's found). It is always suggested to load the mod with Doom 2 using the
-file method. As of version 1.5, the mod no longer runs as an IWAD to prevent this issue
in the future and to require the presense of a DOOM2 or Final Doom IWAD.

(!) IMP DEATH ANIMATION FREEZES MID-DEATH!
This is most likely the result of loading a mod designed for use with vanilla Doom with
this mod. A good example is the Ketchup blood mod. That particular mod was designed with
the classic Doom actors in mind. The Doom 64 Imp death animation is actually a couple
frames longer, so the mod in quesiton might be redefining the Imp actor to use the
normal (and shorter) Doom 2 animation. It is highly recommended not to load other mods
with Retribution that were not designed for it. The mods themselves will need to be
patched to work with Retribution's modified actors.

(!) THE DOOM 64 FEATURES MENU IS MISSING!
This is due to using MENUDEF features and coding that was required in older versions of
GZDoom, most notably version 2.2.0 since that is the version in which the mod was (and
still is) developed on. This issue was resolved in version 1.4a of the mod by adding the
required MENUDEF changes. If you are on an older version of GZDoom, refer to the section
below on how to make it work. You can still change all of the CVARs through the INI file
or console on any version of the mod!

(!) THE TITLEMAP MUSIC CUTS OFF TOO LATE AND IT STARTS OVER!
This only happens on newer versions of GZDoom due to a change to the internal game timer.
In older versions, it ran slightly faster which required slightly longer delays for things
like music timings. This change has the side effect of throwing off the original delays
so that music might end up repeating before it gets changed. If it's cutting off late or
early for you, change the Internal Game Timer setting to Legacy or Normal and try again.

(!) SKYBOXES ARE PITCH BLACK AND FLICKER IN AT TIMES
So far I've only seen this happen in one stream. The cause in that stream was apparently
being using game capture instead of window capture in OBS. This may have been the case
for this particular streamer's setup only and doesn't happen with others.

(!) THE SKY IS THE GREEN "I SUCK AT MAKING MAPS" TEXTURE, BUT BACKWARDS!
This will happen if you are using an old enough version of GZDoom or ZDoom before support
for SkyViewpoint things was added to the software renderer. I mainly set it up this way
on purpose so the user would immediately know something is wrong and will read this.

(!) THERE ARE NO REVERB EFFECTS EVEN THOUGH THE SETTING IN THE FEATURES MENU IS ON!
I just recently discovered while testing for 1.5 that "Enable EFX" needs to be on in
the OpenAL options in the Sound Options menu. Without this setting on, there are no
reverbs in versions of GZDoom with OpenAL. This is not a problem if you are on an
older version that still uses FMOD, like me. This drove me crazy while testing in
a newer version to make sure it works good for you guys. Ended up deleting my INI
and making a new one, then I was able to find the cause was EFX being off!


The following are bugs that I know about and have tried to remove all instances of. If you
run across either of these, please DO report them:

(!) THIS SECTOR IS DAMAGING ME WHEN IT CLEARLY SHOULDN'T BE!
This is happening because of pre-set sector damage through a sector effect in the UDMF format,
and then setting the sector's damage later through ACS. In old versions of GZDoom, the sector
damage would stay regardless of changing it with ACS. I tried to find and fix all spots where
this was an issue, but if you locate one please report it.

(!) CERTAIN EFFECTS ARE MISSING OR PART OF THE MAP LOOKS WRONG!
Odds are you may be on an older version of GZDoom before sectors with multiple tags were
supported. I tried to find and fix all instances of this so that all sectors and actions
only use a single tag at all times, so if there is one you are seeing please do report
it (but they should all be gone).

(!) MONSTER TELEPORTS IN INSTEAD OF FADING IN LIKE THE ORIGINAL GAME!
In version 1.2, I tried to make sure they all faded in instead of teleported. There should
only be one place where they do teleport even in the original game, and that is the final
area in MAP28 The Absolution. The monsters are forced into teleporter lines instead of
being spawned in by macros. If there happens to be a spot outside of this that you find,
please report it and it will be fixed in future updates.

(!) A LARGE CLOUD OR SPACE TEXTURE SHOWS UP IN THE AUTOMAP!
This is the skybox for the map you are currently on. The reason it appears is because you are
most likely using the textured automap and are currently standing in a sector which is at the
same level as the skybox outside of the map. In version 1.2, I tried to find and hide all
instances of this, so if you manage to find one not hidden please report it.

(!) I CAN GRAB THINGS FROM BELOW BEFORE I AM MEANT TO!
These are known as item grabs, and pretty much unfixable without doing item swaps (meaning place
a dummy version of said item, then remove the dummy and spawn the real one in the same tic to
give the effect the item never changed). Many places where you can actually do this have been
fixed using this method, if you find more please report them.

(!) MIDTEXTURES EXTEND INTO THE SKY INFINITELY
Apparently if a midtexture is set to wrap, it is supposed to wrap into the sky forever
as far as the eye can see. However, this didn't happen on older versions of GZDoom and
thus means any map in which it happens on is not meant to do so. Please report where
and on which map it's happening. This is a classic example of a case where a bug ends
up being and looking better than the fixed result.


Lastly, these are bugs that I've seen happen or have had reported but I have no idea what
is causing them or if there is even a fix. The only suggestion I can think of to try is
to delete your INI file and have GZDoom create a completely fresh one, or change versions.

(!) LOADING SCREEN THUMBNAIL IS ALL GLITCHY AND MESSED UP
I've seen this happen to several people in videos and streams but I have no idea what is
causing the save game thumbnails to corrupt or glitch out. It's never happened to me in
my own games so I'm clueless on this matter.



/* --- MAKING THE MOD WORK ON SOME OLDER VERSIONS OF GZDOOM ------------------------------------ */

Many users may still be using older versions of their source port of choice due to various reasons.
I myself am one of them, since anything higher than GZDoom 2.2.0 gives me problems. Below are
guides on how to make the mod work on older versions of GZDoom. I don't know the exact range of
versions that this fix will work on, but it for sure works for 2.2.0 and everything else works
as intended with no other modifications required.


      FIX FOR OLDER GZDOOM (at least on version 2.2.0, the one I use)

If you cannot run the mod on GZDoom, you are most likely getting the following error:

     Script error, "D64RTR[v1.5].WAD:MENUDEF" line 25:
     Unknown keyword 'AddOptionMenu'

Thanks to the MENUDEF overhaul and "scriptification" of status bars, this means you cannot
simply redefine entire menus anymore and must "add" to existing menus. This has two cons:

   1) Any mods made before this change with modified menus will no longer load up
   2) Any new menus you add are always forced to the bottom of the options menu

Fortunately, I have made it easy to fix this yourself. Open the mod in SLADE and then
open the MENUDEFS lump. Scroll down a tad and you will see a lot of commented out code.

In this code, you are given instructions but just to reiterate:

   Step 1 - Add a comment block around the AddOptionMenu code block, commenting it out
   Step 2 - Remove the comment block around the OptionMenu "OptionsMenu" code block

Basically, you want to "switch them out." Alternatively, you could just delete all the
comment stuff as well as the AddOptionMenu block if you never plan to use newer GZDoom.

For older GZDoom versions, you need to redefine the menu as you see, and for newer
GZDoom you need to add a menu to an existing one instead.

Save the mod, and it should load up fine on 2.2.0. I know because it's the version I use. :)



/* --- INTENDED CHANGES FROM THE ORIGINAL ------------------------------------------------------ */

- Weapons switch twice as fast as usual. This was done to keep the speed of the game uniform and
  improve the responsiveness of weapon switching.

- Selecting the Chainsaw alerts non-deaf enemies. This was something that was added in the base
  mod for the weapons and monsters I used to build this TC. I decided to leave it in since it
  makes sense for the Chainsaw to do so, and inversely the fist will not alert monsters when
  you attack since fist punches should realistically be silent attacks.

- Lost Souls do not immediately infight. Instead, they will need to complete one missile state
  before they will infight. They also used to not damage the player if they died upon being
  spawned. In the 1.4 update, they were fixed so that they would. Sometimes it may not happen
  due to the player being between them when spawned.

- Unmaker upgrade messages switched around to make more sense to which map they were obtained
  on. Now, the orange artifact will tell you it doesn't belong in this world (which is true,
  why would it be on a Mars base). The purple one will simply tell you it must do something.
  Finally, the cyan one will tell you that it wasn't meant to be touched (which is also
  true since an ambush happens after taking it).

- Colors and lighting is not identical due to the way sector coloring works in the GZDoom
  engine. I plan and hope to remedy this and be more true to the original in the future as
  the lighting system in GZDoom becomes more advanced over time.

- The Demon Key gates in The Absolution raise up instead of lower down. This was pretty much
  unavoidable because I had to use 3D floors to create the portal structures, and when moving
  a 3D floor's control sector down, the in-map 3D floor side textures act as if they are upper
  unpegged. I don't believe there is a way to change this, so instead the floors will raise up
  to lock the gates. Same concept, different style is all. I also had to damage the floor in
  front of the gates so demons couldn't potentially block the gate. They MAY still block it, in
  which case please report it to me if they happen to in your game.



/* --- CHANGES ON THE ABSOLUTION TC'S EXCLUSIVE MAPS AND FEATURES ------------------------------ */

The original Doom 64 TC from the 2000s brought a number of changes to Doom 64's arsenal and
bestiary. This is a list of some of the major changes from the Absolution specific components
and and maps and how they were modified for Retribution.

- Generally speaking, many minor improvements were made to the maps including better texture
  alignments, better texture choices and improved scripting thanks to UDMF and ACS. The
  original maps were built with Boom format and relied on some special Doomsday features
  for many of its effects. The maps now are much more editable and modifiable.

- Death Labs was converted into a fully playable and scripted map, much like Even Simpler
  from the original Doom 64 mapset. The map starts out with simple enemies and then quickly
  moves through the original monsters that spawned from the four staircases in the original
  map. The Plasma Rifle and BFG areas open up during the final waves. The teleporter which
  leads to Doom 64 Museum is still there, but is now a secret exit to get there.

- Both Death Labs and Doom 64 Museum needed to be balanced for normal play since they are
  no longer "demo maps" and are now real maps. Since Retribution's own Test Facility map
  is essentially an upgraded Doom 64 Museum, it was pointless to treat them the same way.
  Here's what this means for each map:

        Death Labs:
     The Unmaker and the upgrades in the corners were replaced with standard powerups.

        Doom 64 Museum:
     You will not retain the Unmaker upgrades when leaving the map and should instead
     make sure you have fun and experiment with them before leaving the map. However,
     if you managed to obtain the first Unmaker upgrade from Crisis, you will NOT lose
     that one when leaving the map. You will be warned of this when trying to leave.
     You will not lose any ammo you expend when playing in single player.

- The Unmaker upgrade in Crisis now has cleaner movement down the conveyor and doors will
  open so that it looks more realistic and believable. A camera was also added in the same
  room so you can watch it travel to the room it ends up in. The doors also allow you to
  travel through the conveyor area for even more map accessibility.

- The biggest change of all: for the time being the exclusive monsters and items added
  by the Absolution TC have been removed entirely and replaced with standard Doom 64
  matching counterparts. It is not set in stone forever that they will not be added,
  but I wanted to get the maps done first before I decided what to do about these
  new actors. This choice was mostly an opinionated decision.

  These exclusive items and monsters are still planned to be made and built for use
  in Retribution at some point but for now they are not to be included. For example,
  they may be converted and built into a WAD which can randomly replace the actors
  that they would match to which could be loaded as an addon to Retribution.


Some detailed and specific changes to the maps include:

ABSOLUTION EXCLUSIVE MAPS TO RETRIBUTION:
- Death Labs is now a fully playable normal level with a secret exit to Doom 64 Museum
- Shadows Watching now comes before Forbidden Deeper in the map order
- Nightmare Cacodemons are now regular Cacodemons
- Nightmare Spectres are now regular Spectres

OUTCAST LEVELS TO RETRIBUTION:
- Unfinished maps are included as all new finished maps (Control, Forge, Derelict)
- Nightmare Cacodemons are now regular Cacodemons
- Nightmare Spectres are now regular Spectres
- Stalkers are now Lost Souls
- Acid Demons are now regular Demons or Spectres
- Nightcrawlers are now Arachnotrons
- Chaingunner zombiemen are now Shotgun Guys
- Hell Potions replaced with regular Health Bonuses
- Radar computer area maps replaced with normal computer area maps
- Levitation upgrade on Radiant is now a normal Unmaker upgrade
- Unmaker in the final area of Portal is now a Plasma Rifle
- Hell Time upgrade at the end of Portal was removed completely
- Added exit signs to the end of Portal to signify it is the exit
- Changed fake exit sign textures on Darkened to something else
- Unmaker upgrade in Darkened is now a trapped Soulsphere
- Moved yellow key on Darkened to where the Megasphere was
- Megasphere is now a secret that requires the red key (which was somewhat redundant before)
- Added exit signs to the real exit on Darkened to prevent accidental early exits
- Added an obvious clue that something happens at the end of Traps for the floating Unmaker upgrade
- Translucent Hell Knights in Nebula are now regular Hell Knights (no more Shadow Knights)
- Added some new special effects to Nebula and tweaked the second wave of enemies for the red key
- Made many minor geometry tweaks to Nebula to keep everything on the 8 unit grid
- Hell Time upgrade at the end of Nebula was removed completely (was already redundant anyway)
- Cyberdemon and Mother Demon at the end of Nebula are able to traverse the arena much better
- Nightcrawler and medkit behind the final door of Nebula were removed since they were pointless already



/* --- THE UNFINISHED OUTCAST LEVELS ----------------------------------------------------------- */

You may also be wondering about the three maps which are not part of the original Outcast Levels,
with those maps being Control, Forge and Derelict. Here is a short explanation of their origins
and why they are in the set:

When you download the Outcast Levels expansion for the Absolution TC, included is a folder simply
called "unfinished." Inside this folder are three WAD files: OUTCAST07.wad, OUTCAST08.wad, and
test.wad. Each one is the beginnings of one of the three new maps now finished.

According to the readme included alongside the files written by Kaiser: "these are unfinished
levels that never made it to outcast, you can do whatever you want with these." So, that's
what I did. It would have been a shame to convert the Outcast Levels and forget about these
unfinished ones that deserved to finally be finished.

The majority of each map was built from basically nothing. Only Control is mostly the same. In fact,
if you run that WAD with the TC, you will immediately recognize the layout. The layout of that map
was already pretty much done, but was all at the same height and everything had the same texture.
It was a cookie cutter layout which wasn't refined or even playable.

The other two maps were old or original versions of a couple other maps. Forge was an old version of
Destroy and Derelict was an old version of Darkened. It's obvious they were early versions.

When I converted and finished these, I deleted the sectors which were identical between the maps and
altered anything that I wanted to keep. Then for the remaining areas, I drew all new sectors and made
the maps essentially from only a starting base or a shell of a level.

The unique bits to each map was all me, I came up with unique ideas for each map, in fact I doubt
Doomsday could even do any of this stuff, at least not as easily as UDMF. So they were mostly from
scratch and only had the starting areas and basic stuff done but none of them were finished.



/* --- CHANGES ON THE REDEMPTION DENIED MAPS --------------------------------------------------- */

• Tons of better texturing choices and better texture alignments all around
• Improved some areas by changing heights and making minor geometry changes
• Joined and merged tons of like-sectors to reduce the overall sector and sidedef counts
• Swapped some Cacodemon spawns with Hell Knights due to Cacodemon size being too large
• Removed or changed many lamp posts that overcrowded the original maps
• Moved many things out of the walls so they are all fully within the map bounds
• Made all freelook-required shoot switches and secrets no longer require freelook
• Slightly changed progression on some maps to include all map areas in the path
• Absolution and Outcast enemies replaced with their normal Doom 64 counterparts
• Re-balanced each map by adding needed ammo, weapons and health

  _____________________________________________________________________________ 
 |                                                                             |
 |   VLSST Info Comparisons / Optimizations for Redemption Denied Expansion    |
 |_____________________________________________________________________________|
 |        |            |                        |                              |
 |  MAP   | STATISTIC  |  Absolution TC (Boom)  |  Doom 64 Retribution (UDMF)  |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  4155                  |  3768                        |
 |        | Linedefs   |  5004                  |  4511                        |
 | RDM01  | Sidedefs   |  8080                  |  7259                        |
 |        | Sectors    |  526                   |  299                         |
 |        | Things     |  268                   |  346                         |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  3903                  |  3486                        |
 |        | Linedefs   |  5257                  |  4489                        |
 | RDM02  | Sidedefs   |  8716                  |  6993                        |
 |        | Sectors    |  1251                  |  748                         |
 |        | Things     |  362                   |  451                         |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  5414                  |  5252                        |
 |        | Linedefs   |  6741                  |  6366                        |
 | RDM03  | Sidedefs   |  10946                 |  9902                        |
 |        | Sectors    |  1323                  |  922                         |
 |        | Things     |  505                   |  621                         |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  5443                  |  5148                        |
 |        | Linedefs   |  7099                  |  6285                        |
 | RDM04  | Sidedefs   |  11752                 |  9754                        |
 |        | Sectors    |  1555                  |  836                         |
 |        | Things     |  607                   |  796                         |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  5308                  |  5096                        |
 |        | Linedefs   |  6823                  |  6185                        |
 | RDM05  | Sidedefs   |  11022                 |  9348                        |
 |        | Sectors    |  1456                  |  978                         |
 |        | Things     |  621                   |  768                         |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  6542                  |  6388                        |
 |        | Linedefs   |  7941                  |  7552                        |
 | RDM06  | Sidedefs   |  12508                 |  11408                       |
 |        | Sectors    |  1546                  |  938                         |
 |        | Things     |  886                   |  1038                        |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  5749                  |  5783                        |
 |        | Linedefs   |  7022                  |  6852                        |
 | RDM07  | Sidedefs   |  11268                 |  10423                       |
 |        | Sectors    |  1443                  |  942                         |
 |        | Things     |  914                   |  1126                        |
 |________|____________|________________________|______________________________|
 |        |            |                        |                              |
 |        | Vertices   |  7077                  |  7417                        |
 |        | Linedefs   |  8238                  |  8641                        |
 | RDM08  | Sidedefs   |  12781                 |  12514                       |
 |        | Sectors    |  1317                  |  929                         |
 |        | Things     |  823                   |  947                         |
 |________|____________|________________________|______________________________|
 |-----------------------------------------------------------------------------|
 |=============================================================================|
 |        | Vertices   |  43591                 |  42338      DIFF: 1253 less  |
 |        | Linedefs   |  54125                 |  50881      DIFF: 3244 less  |
 | TOTALS:| Sidedefs   |  87073                 |  77601      DIFF: 9472 less  |
 |        | Sectors    |  10417                 |  6592       DIFF: 3825 less  |
 |        | Things     |  4986                  |  6093       DIFF: 1107 more  |
 |=============================================================================|
 |_____________________________________________________________________________|
   NOTE: Things are higher due to using GZDoom specific actors and features!



/* --- DOOMSLAYER DIFFICULTY INFORMATION ------------------------------------------------------- */

When I was first developing the mod, I was reading about skill settings and custom skills. I was
curious about the idea of adding my own new mode much like games often have a super hard mode or
some other kind of cool extra mode or difficulty setting.

At first I wanted to do a one hit kill mode, but with hitscanners... good luck with that. So I
started messing with settings and properties to try and come up with something harder than
Watch Me Die but that wasn't like Nightmare.

When the TC first came out, I didn't really think much about the mode I had created nor did I
write any information about it. I guess I wanted people to "discover" the mode. That's when
I was checking ModDB and noticed someone asking about the mode.

In my own words, "It's like Nightmare without respawning, harder monster swaps but increased
damage from both sides. It's like the super hard mode but I don't even know how possible it
is since I just made it for fun."

Turns out, it's not only possible, but it's damn fun and quite good in my opinion.


So, to introduce it proper... ahem *clears throat*

"Welcome to Doomslayer Difficulty! The forces of Hell stand before you, stronger
and fueled by hate... can you defeat them?"

What is Doomslayer, really? Well, let's break it down.

   • Uses the spawn settings from Hardcore (or Nightmare if you prefer)
   • Three times the normal ammo amounts given, but all ammo pickups are their smallest version
   • 20% more damage towards monsters, as well as back to the player
   • All monsters have 80% of their normal health
   • Many monsters swapped to their harder versions (Hell Knights become Barons, etc.)
   • Full aggressiveness level
   • Cheats disabled unless sv_cheats is set to 1
   • Monsters will never enter their pain states
   • Monsters will never infight

Now, what gets swapped with what exactly?

                MONSTERS
         Zombiemen -> Shotgunner
               Imp -> Nightmare Imp
           Spectre -> Hell Knight
       Hell Knight -> Baron of Hell
             Demon -> Spectre

                  AMMO
         Shell Box -> Shells
          Clip Box -> Clip
        Rocket Box -> Rocket
         Cell Pack -> Cell

           HEALTH AND POWERUPS
           Medikit -> Stimpack
        Blursphere -> Medikit
   Invulnerability -> Soulsphere


As you can see, it's a mode that pushes everything to the extremes while somehow still
staying very possible. Speed, aim, and reflexes matter more than ever before. This is
a mode that rewards aggressive play, and where the SSG is king (if it wasn't already).

At first it was a mode I didn't know was possible. Now it's a mode I will always test
when new maps are considered to be added. Thankfully, you can balance maps for Doomslayer
without affecting the original balance by placing new things on Skill 6 only.

So you may be asking yourself, can I beat maps on this mode? I say as long as you are
able to beat maps in classic Doom on UV and Doom 64 on WMD, you can handle it.

Big thanks to TheWolfArokh for proving the original state of the mode was possible and
inspiring me to improve it further!



/* --- USING THE 20TH ANNIVERSARY SOUNDTRACK --------------------------------------------------- */

Due to several reasons, I have decided to not include nor create a PK3 of the newer versions of
the soundtrack known as the 20th Anniversary Soundtrack which can be found and bought on BandCamp.
The reasons include file size concerns and the fact that this version of the soundtrack is not
free and is still very new.

However, thanks to the way that I have set up the music in this game, replacing the soundtrack
is very easy to do and does not require you to have SLADE or any other WAD management program.
It can be done directly in your OS of choice.


Step 1 - Acquire the soundtrack is the first step, you will need the music files on your PC.

Step 2 - Copy them into a new folder somewhere and name the folder "MUSIC".

   Optional Step - Convert them to a smaller format, such as OGG. Using MP3 is fine, but OGG is best.

Step 3 - Rename them as follows (exactly as seen to the left of the equals, plus file extension):

      Example: The Madness MP3 would be renamed to "D_MUS01.mp3" or "D_MUS01.ogg"

   D_D64END = Finale
   D_D64INT = Stats
   D_D64MENU = Menu
   D_D64TTL = Theme or Theme Extended

   D_MUS01 = The Madness
   D_MUS02 = Warped Hive
   D_MUS03 = Tortured Transmission
   D_MUS04 = Spaces Between
   D_MUS05 = Hellistatic
   D_MUS06 = Bleep Spawn
   D_MUS07 = Relentless Coil
   D_MUS08 = The Damned
   D_MUS09 = Other Side of Madness
   D_MUS10 = Dark Echo
   D_MUS11 = Aspects of the Vile
   D_MUS12 = Lamentation of the Forgotten
   D_MUS13 = Voices in the Blood
   D_MUS14 = Chrystalline Chaos
   D_MUS15 = Wait for It
   D_MUS16 = Blood Red Shadows
   D_MUS17 = Warped
   D_MUS18 = Collision Course
   D_MUS19 = The Rotted Foul
   D_MUS20 = Perfect Hate

   D_NEW01 = Overloaded (from the original soundtrack version)
   D_NEW02 = Tainted Brood (from the original soundtrack version)
   D_NEW03 = Breaking Point (from the original soundtrack version)
   D_NEW04 = The Glitch Rot
   D_NEW05 = Metal Mites
   D_NEW06 = Unwound and Unhinged
   D_NEW07 = The Revelation Hour
   D_NEW08 = Sawteeth Smiles
   D_NEW09 = Clawing the Terminal
   D_NEW10 = Infestation Dissonance
   D_NEW11 = Transmission Desperation

Step 4 - Once renamed, create a text file called SNDINFO.txt beside the MUSIC folder (not inside it).

Step 5 - Paste these lines into the created SNDINFO.txt exactly as you see here:

$mididevice D_D64TTL default
$mididevice D_D64MNU default
$mididevice D_D64INT default
$mididevice D_D64END default
$mididevice D_MUS01 default
$mididevice D_MUS02 default
$mididevice D_MUS03 default
$mididevice D_MUS04 default
$mididevice D_MUS05 default
$mididevice D_MUS06 default
$mididevice D_MUS07 default
$mididevice D_MUS08 default
$mididevice D_MUS09 default
$mididevice D_MUS10 default
$mididevice D_MUS11 default
$mididevice D_MUS12 default
$mididevice D_MUS13 default
$mididevice D_MUS14 default
$mididevice D_MUS15 default
$mididevice D_MUS16 default
$mididevice D_MUS17 default
$mididevice D_MUS18 default
$mididevice D_MUS19 default
$mididevice D_MUS20 default

Step 6 - Save the file, then close it.

Step 7 - Select both the MUSIC folder and SNDINFO.txt and then right-click and click "Send to" and
         then click "Compressed (zipped) folder". If you are not on Windows, refer to the method
         used by that OS to compress files.

Step 8 - Wait for it to be compressed and then rename the file to D64RTR_MUSIC_20TH.PK3 or something
         similar, but it must have the PK3 or ZIP extension.

Step 9 - Move the compiled file beside Doom 64 Retribution and then load it up! Enjoy the new music.


If you would like to use the new bonus tracks to replace some of the repeated music tracks, it's also
easy to do. All that has to be done is to change the LANGUAGE strings that assign music tracks names
to the strings that MAPINFO references.

Step 1 - Create a text file called LANGUAGE.txt anywhere.

Step 2 - Start off the file by typing "[enu default]" at the top, without quotes.

Step 3 - Write out a LANGUAGE string re-assignment to one of the new tracks, for example:

      MUS_MAP01 = "NEW01";

   This will re-assign the music track to be used in Staging Area to be Overloaded instead
   of the normal track, The Madness. So, your full file should look like this:

      [enu default]
      MUS_MAP01 = "NEW01";

Step 4 - Save the LANGUAGE.txt file.

Step 5 - Right-click the file and and click "Send to" and then click "Compressed (zipped)
         folder". If you are not on Windows, refer to the method used by that OS to compress files.

Step 6 - Wait for it to be compressed and then rename the file to something like D64RTR_NEWMUS.PK3.

Step 7 - Load the file as you would any other file, but make sure you are loading it AFTER you load
         the main WAD file. Don't forget to also load the D64RTR_MUSIC_20TH.PK3 music pack you made!



/* --- CREDITS --------------------------------------------------------------------------------- */


   WEAPONS, MONSTERS, ITEMS

Based off "Doom 64 WMI Redux" by Dreadflame (@ ZDoom Forums)
or GuitarDeity (@ YouTube) and Footman

A good 90% of the DECORATE and GLDEFS came from "Doom 64 WMI Redux"
The rest from individual tweaks from Nevander and concepts from HazeBandicoot

Midway for all base Doom 64 sprites
(Sukru Gilman, Francisco Gracia, Laurent Bezault and Andy Wilson)

Sound effects by Aubrey Hodges, original sound system by Scott Patterson

osjclatchford and chronoteeth for the base of the new pistol pickup
sprite, recolored and edited by Nevander to match the D64 Desert Eagle

Shotgun pickup sprites edited from "Doom 64: Unabsolved" mod
for Zandronum by AEnima (@ ZDoom and Zandronum Forums)

Cage and Almonds for the smoother animations of Fist, Shotgun, Super Shotgun,
Chaingun, Plasma Rifle and BFG (maybe the Pistol too?)

Additional edits to various frames from Shotgun and Super Shotgun
by Nevander and Skelegant

Casing sounds and liquid hit sounds taken from "Smooth PSX Doom"


   TEXTURES AND GRAPHICS

All base Doom 64 textures created by Midway

"Doom the Way Midway Did" textures created by Cage (named DTWMDxx in-wad)

PSX unique textures from Williams Entertainment and the PSX TC crew

Absolution TC Outcast texture set created by NMN

DOOM 2016 style textures created by Emerson Tung and id Software (named DSLRTXxx in-wad)
Ripped for use in classic Doom by Dragonfly

Edited Doom 64 logo picture used for INTERPIC and more by CoTeCiO

Beta Doom 64 textures originally created by Midway, ripped by Nevander


   MAPS

All original map geometry created by the Midway level design team
(including Randy Estrella, Tim Heydelaar and Danny Lewis)

All stock Doom 64 maps converted fresh into Doom engine readable UDMF format by Nevander

All map scripts and events re-written by hand by Nevander

Original Absolution TC exclusive maps by Samuel A. Villarreal AKA Kaiser and Elbryan42

Original Absolution TC Outcast Levels by Kaiser, Elbryan42, and AgentSpork

Unfinished maps from Outcast Levels started by Kaiser and finished by Nevander

Original Absolution TC Redemption Denied levels by Steven Searle and AgentSpork


   MUSIC

Original soundtrack composed by Aubrey Hodges


   OTHER CREDITS

Lost Souls exploding damage method by snackerfork

Triangular automap arrow method taken from "PSX Doom TC"

Doom 64 style thing fade in code originally written by Kaiser and AgentSpork,
fade out code written by Nevander, improved code written and modified by
KeksDose and Nevander


   SPECIAL THANKS

Everyone at Midway responsible for the development of Doom 64

id Software for the Doom franchise as a whole

HUGE thanks to Kaiser for Doom 64 EX and the WadGen tool
Without these, this project would not have been possible

ZDoom and DoomWorld Forums for help and encouragement throughout
and for being extremely patient waiting for updates :)

TheDoctor45 at DeviantArt for the Doom 64 M_DOOM logo base

86232and for finding the real name for RDM01 The Metacenter

Big thanks to TheWolfArokh for proving the original state
of Doomslayer difficulty was possible and inspiring me
to improve it further!

And of course, thanks to all of you who play my TC! Thank you!



/* --- MAKING NEW MAPS FOR THE MOD ------------------------------------------------------------- */

There are files and porting guides inside the "D64RTRDEV" folder that will help you in creating
new maps and intermission sequences if you so desire. Please refer to the readme inside that
folder for more information and a full breakdown on all the files for map development.



/* --- FINAL REMARKS --------------------------------------------------------------------------- */

Thank you for downloading my fan made TC of Doom 64. I had a lot of fun making it and it
was the first time I used UDMF and ACS.

I learned a lot over the months using the format and I believe it made me a better mapper
as well as a better weapon designer. I learned a lot more about DECORATE as well.

I hope you have as much fun playing it as I did making it!

Rock on, Doomslayers!

