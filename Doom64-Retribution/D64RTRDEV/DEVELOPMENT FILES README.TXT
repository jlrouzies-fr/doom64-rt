NOTE: For best reading, make sure Word Wrap is off!

  ____________________________________________________________________________
 |                                                                            |
 |                            Doom 64: Retribution                            |
 |                             DEVELOPMENT FILES                              |
 |____________________________________________________________________________|


This is just a simple list of files and things you can use to make your own levels for
the total conversion. If you do not intend to make maps or are not a mapper, please
feel free to delete the "D64RTRDEV" folder. It is not required in any way to run or
play the mod.

With that said, here's a run-down:

   1) D64FADES.PK3
      This file is required if you want to make use of the new custom fade-in spawning
      functions that were found and improved for use in Doom 64 Retribution. Please
      refer to D64FADES_DOCUMENTATION.TXT on how to use the functions.

   2) interxx_template_ending.wad
      This is a basic outline of an ending screen intermission sequence. Copy this WAD
      and then open it in GZDoom Builder to have an easy and quick head start on creating
      new intermissions at the end of an episode. The script editor (SCRIPTS file) has
      instructions on creating them and guides you step-by-step.

   3) interxx_template_normal.wad
      Same as above, only for use between levels and not as an ending. It can be used as
      as ending though, in the event you don't want the Doom 64 ending image.

   4) PORTING GUIDE - BOOM TO D64RTR.TXT
      A guide you can follow that explains how to convert a Boom formatted Absolution TC
      map or any Boom format map to Doom 64 Retribution UDMF format.

   5) PORTING GUIDE - EX TO D64RTR.TXT
      Same as above, only for conversion from Doom 64 EX to Doom 64 Retribution.


I strongly encourage mappers to make new maps in Doom 64 style using my mod as the base. Also if
you are a previous Doom 64 mapper for either the Absolution TC or Doom 64 EX, I too encourage you
to port your map to my mod as well if you so desire.

You can use the WAD itself as a resource in GZDB. Simply add it as a WAD resource underneath
DOOM2.WAD or your Doom 2 style IWAD and get mapping! If you wish to take advantage of the fade
spawning functions for spawning monsters the way Doom 64 did, you should also include "D64FADES.PK3"
as a resource so you can use #import to make the various functions available to GZDB.

Make sure you add this line at the top of your map script files:

   #import "ACS\D64FADES.ACS"

For best results, add this directly underneath the usual #include "zcommon.acs" line.

If you are unsure of how I did things and want to make your map consistent with the rest of the
ported maps that I myself have done, do not hesistate to open the maps in GZDB and check out
the scripts and the map itself to see how it was designed. You can also contact me on ZDoom
and Doomworld forums with your questions.

For ease of map development and testing, I have created a weapon called "mdkgun" which does
exactly what it sounds like: a rapid firing hitscan weapon that behaves just like the mdk
console command. By default, the code to make it usable is commented out. To use it when
mapping, edit the DECORATE lump and remove the comments.

Happy mapping!
