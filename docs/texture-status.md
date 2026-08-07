# Retribution RT texture status

Last regenerated: **2026-08-02**

Gallery map: load `Doom64-Retribution/d64rtexg.wad` then `map map99` (or use `tools/launch-texture-gallery-rt.cmd`).

Scene materials: `rt/data/scenes/d64rtexg_map99/textures.json` + `rt/mat/<TEX>_orm.png`.

Regenerate inventory / gallery / auto-PBR:

```bat
python tools\build_texture_gallery.py
```

## Status legend

| status | meaning |
|---|---|
| `unreviewed` | auto stub only; not visually checked |
| `auto` | heuristic PBR applied; looks plausible |
| `tuned` | hand-adjusted meta / ORM / emissive |
| `done` | approved for shipping |
| `blocked` | needs engine/art fix before tuning |
| `skip` | intentionally ignored (sky dummy, etc.) |

## Summary

- Unique textures in maps: **738**
- Maps scanned: **35** (MAP00, MAP01, MAP02, MAP03, MAP04, MAP05, MAP06, MAP07, MAP08, MAP09, MAP10, MAP11, MAP12, MAP13, MAP14, MAP15, MAP16, MAP17, MAP18, MAP19, MAP20, MAP21, MAP22, MAP23, MAP24, MAP25, MAP26, MAP27, MAP28, MAP29, MAP30, MAP31, MAP32, MAP33, MAP34)
- Brightmap-ish names available: **198**

| status | count |
|---|---|
| `unreviewed` | 666 |
| `done` | 71 |
| `##` | 1 |
| `skip` | 1 |

## Tracker

| texture | category | status | notes | uses | maps |
|---|---|---|---|---|---|
| `SPACEBE` | metal | done | gallery bulk (metal); ok mean=57.4 var=1925 | 12556 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SFLATBF` | floor | done | gallery bulk (floor); ok mean=54.8 var=1552 | 9729 | MAP01,MAP05,MAP06,MAP07,MAP25,MAP29… |
| `SPACEBD` | metal | done | gallery bulk (metal); ok mean=56.8 var=1840 | 5149 | MAP01,MAP02,MAP04,MAP05,MAP06,MAP07… |
| `C53` | industrial | done | gallery bulk (industrial); ok mean=45.1 var=1282 | 4120 | MAP10,MAP11,MAP12,MAP13,MAP14,MAP15… |
| `C65` | industrial | done | gallery bulk (industrial); ok mean=39.6 var=1447 | 2924 | MAP12,MAP16,MAP18,MAP20,MAP21,MAP22… |
| `SPACEBO1` | metal | done | gallery bulk (metal); ok mean=52.6 var=1694 | 2639 | MAP34 |
| `SPACEAA` | metal | done | gallery bulk (metal); ok mean=59.9 var=2361 | 2566 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `C35` | industrial | done | gallery bulk (industrial); ok mean=43.2 var=1262 | 2279 | MAP09,MAP12,MAP13,MAP15,MAP16,MAP17… |
| `SPACEART` | metal | done | gallery bulk (metal); ok mean=59.0 var=2250 | 2003 | MAP34 |
| `C52` | industrial | done | gallery bulk (industrial); ok mean=43.8 var=1350 | 1998 | MAP09,MAP12,MAP13,MAP15,MAP16,MAP18… |
| `C10` | industrial | done | gallery bulk (industrial); ok mean=74.7 var=206 | 1959 | MAP09,MAP10,MAP12,MAP14,MAP15,MAP16… |
| `SFLATAQ` | floor | done | gallery bulk (floor); ok mean=76.4 var=95 | 1950 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `C50` | industrial | done | gallery bulk (industrial); ok mean=79.5 var=141 | 1924 | MAP10,MAP14,MAP15,MAP16,MAP22,MAP30… |
| `C44` | industrial | done | gallery bulk (industrial); ok mean=76.4 var=76 | 1876 | MAP10,MAP12,MAP13,MAP14,MAP15,MAP16… |
| `C54` | industrial | done | gallery bulk (industrial); ok mean=76.6 var=122 | 1735 | MAP17,MAP31,MAP34 |
| `HELLAB` | industrial | done | gallery bulk (hell); ok mean=73.7 var=233 | 1674 | MAP11,MAP15,MAP17,MAP20,MAP24,MAP28… |
| `SPACECN` | metal | done | gallery bulk (metal); ok mean=78.1 var=96 | 1614 | MAP01,MAP02,MAP03,MAP05,MAP06,MAP07… |
| `HELLAAA` | industrial | done | gallery bulk (hell); ok mean=78.1 var=86 | 1613 | MAP11,MAP17,MAP20,MAP23,MAP24,MAP28… |
| `ISUCK` | industrial | skip | sky dummy / non-material | 1602 | MAP01,MAP02,MAP04,MAP05,MAP07,MAP08… |
| `STRACA` | industrial | done | gallery bulk (industrial); ok mean=75.9 var=143 | 1498 | MAP01,MAP02,MAP04,MAP05,MAP07,MAP08… |
| `C401` | industrial | done | gallery bulk (industrial); ok mean=74.5 var=222 | 1497 | MAP12,MAP15,MAP22,MAP31,MAP34 |
| `SPACEAGS` | metal | done | gallery bulk (metal); ok mean=75.7 var=187 | 1486 | MAP34 |
| `SPACECM` | metal | done | gallery bulk (metal); ok mean=77.2 var=182 | 1392 | MAP01,MAP02,MAP04,MAP05,MAP06,MAP07… |
| `SDFLTA` | ceiling | done | gallery bulk (ceiling); ok mean=75.6 var=153 | 1383 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SPACEAD` | metal | done | gallery bulk (metal); ok mean=74.7 var=142 | 1372 | MAP01,MAP03,MAP05,MAP25,MAP34 |
| `SPACEAI` | metal | done | gallery bulk (metal); ok mean=75.2 var=127 | 1361 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SPACEBC` | metal | done | gallery bulk (metal); ok mean=78.9 var=78 | 1357 | MAP01,MAP02,MAP03,MAP04,MAP07,MAP08… |
| `CASFL22` | industrial | done | gallery bulk (industrial); ok mean=78.8 var=76 | 1339 | MAP09,MAP10,MAP12,MAP13,MAP14,MAP16… |
| `SPACEAL` | metal | done | gallery bulk (metal); ok mean=78.6 var=53 | 1339 | MAP01,MAP02,MAP04,MAP08,MAP34 |
| `SPACEAG` | metal | done | gallery bulk (metal); ok mean=79.9 var=83 | 1324 | MAP01,MAP02,MAP04,MAP05,MAP08,MAP29… |
| `SFLATA` | floor | done | gallery bulk (floor); ok mean=64.2 var=376 | 1303 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `C88` | industrial | done | gallery bulk (industrial); ok mean=64.2 var=376 | 1257 | MAP10,MAP11,MAP12,MAP13,MAP14,MAP15… |
| `SFLATCD` | floor | done | gallery bulk (floor); ok mean=64.2 var=374 | 1241 | MAP01,MAP03,MAP05,MAP06,MAP07,MAP29… |
| `SFLATBE` | floor | done | gallery bulk (floor); ok mean=63.9 var=365 | 1234 | MAP01,MAP05,MAP06,MAP07,MAP25,MAP29… |
| `C99` | industrial | done | gallery bulk (industrial); ok mean=63.9 var=365 | 1212 | MAP17,MAP30,MAP34 |
| `SPACEAQ1` | metal | done | gallery bulk (metal); ok mean=64.3 var=375 | 1207 | MAP03,MAP05,MAP06,MAP33,MAP34 |
| `SPACEAB` | metal | done | gallery bulk (metal); ok mean=64.1 var=372 | 1135 | MAP01,MAP02,MAP04,MAP08,MAP34 |
| `SPACEAO1` | metal | done | gallery bulk (metal); ok mean=64.1 var=372 | 1135 | MAP01,MAP05,MAP07,MAP08,MAP34 |
| `SPACEAP1` | metal | done | gallery bulk (metal); ok mean=65.0 var=359 | 1130 | MAP03,MAP05,MAP06,MAP08,MAP29,MAP33… |
| `SPACEAP` | metal | done | gallery bulk (metal); ok mean=63.6 var=372 | 1093 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SPACECD` | metal | done | gallery bulk (metal); ok mean=66.4 var=572 | 1093 | MAP01,MAP02,MAP04,MAP05,MAP06,MAP08… |
| `SPACEAF` | metal | unreviewed | pending re-capture | 1085 | MAP01,MAP02,MAP04,MAP08,MAP34 |
| `SPACECI1` | metal | unreviewed | pending re-capture | 1075 | MAP29,MAP34 |
| `C37` | industrial | unreviewed | pending re-capture | 1047 | MAP09,MAP14,MAP15,MAP16,MAP17,MAP18… |
| `SPACEAJ` | metal | unreviewed | pending re-capture | 1024 | MAP02,MAP03,MAP04,MAP07,MAP08,MAP25… |
| `C56` | industrial | unreviewed | pending re-capture | 1006 | MAP09,MAP21,MAP34 |
| `C35T` | industrial | unreviewed | pending re-capture | 971 | MAP20,MAP34 |
| `SFLATAK` | floor | unreviewed | pending re-capture | 915 | MAP02,MAP04,MAP07,MAP08,MAP25,MAP32… |
| `SPACEAC` | metal | done | gallery bulk (metal); ok mean=52.8 var=377 | 912 | MAP01,MAP02,MAP03,MAP05,MAP08,MAP34 |
| `STRACB` | industrial | done | gallery bulk (industrial); ok mean=64.4 var=374 | 912 | MAP01,MAP03,MAP04,MAP05,MAP06,MAP07… |
| `SFLATBB` | floor | done | gallery bulk (floor); ok mean=64.1 var=364 | 894 | MAP01,MAP02,MAP04,MAP05,MAP08,MAP29… |
| `CASFL21` | industrial | done | gallery bulk (industrial); ok mean=64.1 var=364 | 860 | MAP09,MAP14,MAP16,MAP18,MAP21,MAP22… |
| `C44B` | industrial | done | gallery bulk (industrial); ok mean=63.6 var=354 | 836 | MAP13,MAP15,MAP16,MAP17,MAP21,MAP23… |
| `H52` | industrial | done | gallery bulk (industrial); ok mean=63.6 var=354 | 835 | MAP13,MAP15,MAP17,MAP18,MAP20,MAP23… |
| `SPACECG` | metal | done | gallery bulk (metal); ok mean=63.6 var=354 | 835 | MAP01,MAP04,MAP05,MAP06,MAP07,MAP25… |
| `SPACECI` | metal | done | gallery bulk (metal); ok mean=63.6 var=354 | 819 | MAP01,MAP05,MAP06,MAP07,MAP25,MAP34 |
| `SPACAMM` | industrial | done | gallery bulk (industrial); ok mean=63.6 var=354 | 816 | MAP01,MAP02,MAP04,MAP05,MAP07,MAP08… |
| `CASFL94` | industrial | unreviewed | pending re-capture | 800 | MAP10,MAP13,MAP17,MAP19,MAP20,MAP21… |
| `SPACEC` | metal | unreviewed | pending re-capture | 795 | MAP01,MAP02,MAP03,MAP05,MAP06,MAP07… |
| `C23` | industrial | unreviewed | pending re-capture | 793 | MAP09,MAP13,MAP14,MAP16,MAP18,MAP21… |
| `C201` | industrial | unreviewed | pending re-capture | 782 | MAP12,MAP15,MAP18,MAP20,MAP22,MAP31… |
| `SFLATB` | floor | unreviewed | pending re-capture | 765 | MAP01,MAP02,MAP05,MAP07,MAP25,MAP32… |
| `SFLATAL` | floor | unreviewed | pending re-capture | 718 | MAP02,MAP04,MAP05,MAP06,MAP08,MAP34 |
| `SFLATAC` | floor | unreviewed | pending re-capture | 717 | MAP01,MAP02,MAP03,MAP04,MAP06,MAP08… |
| `C102B` | industrial | unreviewed | pending re-capture | 714 | MAP10,MAP13,MAP14,MAP15,MAP16,MAP20… |
| `CASFL10` | industrial | unreviewed | pending re-capture | 714 | MAP10,MAP12,MAP16,MAP18,MAP20,MAP21… |
| `SPACEAJT` | metal | unreviewed | pending re-capture | 713 | MAP25,MAP34 |
| `SFLATDG` | floor | unreviewed | pending re-capture | 691 | MAP01,MAP03,MAP06,MAP07,MAP08,MAP10… |
| `SPACECC` | metal | unreviewed | pending re-capture | 691 | MAP02,MAP03,MAP04,MAP05,MAP06,MAP07… |
| `SPACEAM` | metal | unreviewed | pending re-capture | 687 | MAP01,MAP02,MAP07,MAP08,MAP34 |
| `C8` | industrial | unreviewed | pending re-capture | 669 | MAP09,MAP12,MAP15,MAP16,MAP18,MAP22… |
| `H95` | industrial | unreviewed | pending re-capture | 663 | MAP11,MAP14,MAP17,MAP20,MAP23,MAP24… |
| `SPACEAI1` | metal | unreviewed | pending re-capture | 661 | MAP03,MAP29,MAP34 |
| `C66` | industrial | unreviewed | pending re-capture | 658 | MAP10,MAP14,MAP15,MAP16,MAP18,MAP20… |
| `SPACEAGT` | metal | unreviewed | pending re-capture | 654 | MAP34 |
| `CASFL96` | industrial | unreviewed | pending re-capture | 653 | MAP10,MAP12,MAP13,MAP17,MAP19,MAP20… |
| `SDFLTAB` | ceiling | unreviewed | pending re-capture | 646 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP08… |
| `SPACEAQ` | metal | unreviewed | pending re-capture | 646 | MAP02,MAP03,MAP05,MAP07,MAP25,MAP26… |
| `SDFLTAC` | ceiling | unreviewed | pending re-capture | 630 | MAP01,MAP04,MAP05,MAP06,MAP07,MAP34 |
| `CASFL27` | industrial | unreviewed | pending re-capture | 613 | MAP12,MAP13,MAP14,MAP15,MAP16,MAP19… |
| `SPACEAR` | metal | unreviewed | pending re-capture | 604 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP08… |
| `H127` | industrial | unreviewed | pending re-capture | 602 | MAP15,MAP17,MAP23,MAP24,MAP28,MAP34 |
| `C4` | industrial | unreviewed | pending re-capture | 598 | MAP14,MAP15,MAP22,MAP34 |
| `HELLAA` | industrial | unreviewed | pending re-capture | 594 | MAP11,MAP15,MAP17,MAP20,MAP23,MAP24… |
| `H56` | industrial | unreviewed | pending re-capture | 593 | MAP12,MAP21,MAP34 |
| `SPACEBQ` | metal | unreviewed | pending re-capture | 581 | MAP05,MAP06,MAP07,MAP29,MAP34 |
| `SFLATAS` | floor | unreviewed | pending re-capture | 575 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SPACECIH` | metal | unreviewed | pending re-capture | 572 | MAP34 |
| `SPACEBG` | metal | unreviewed | pending re-capture | 563 | MAP02,MAP03,MAP04,MAP05,MAP07,MAP34 |
| `C87` | industrial | unreviewed | pending re-capture | 557 | MAP17,MAP21,MAP34 |
| `CASFL20` | industrial | unreviewed | pending re-capture | 557 | MAP10,MAP12,MAP13,MAP14,MAP15,MAP16… |
| `SPACEBM` | metal | unreviewed | pending re-capture | 555 | MAP01,MAP02,MAP04,MAP08,MAP33,MAP34 |
| `CASFL97` | industrial | unreviewed | pending re-capture | 552 | MAP10,MAP12,MAP13,MAP14,MAP18,MAP19… |
| `SPACAMM1` | industrial | unreviewed | pending re-capture | 551 | MAP08,MAP33,MAP34 |
| `SFLATDF` | floor | unreviewed | pending re-capture | 547 | MAP01,MAP03,MAP06,MAP10,MAP11,MAP28… |
| `SPACEBL` | metal | unreviewed | pending re-capture | 544 | MAP02,MAP04,MAP06,MAP07,MAP08,MAP25… |
| `C3` | industrial | done | gallery bulk (industrial); ok mean=63.5 var=368 | 542 | MAP14,MAP15,MAP16,MAP22,MAP30,MAP34 |
| `C12` | industrial | unreviewed | pending re-capture | 540 | MAP10,MAP14,MAP15,MAP16,MAP30,MAP34 |
| `SMONAA` | industrial | unreviewed | pending re-capture | 536 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SDFLTAD` | ceiling | unreviewed | pending re-capture | 526 | MAP01,MAP02,MAP07,MAP08,MAP29,MAP34 |
| `SFLATBC` | floor | unreviewed | pending re-capture | 526 | MAP01,MAP02,MAP04,MAP05,MAP08,MAP34 |
| `SFLATCE` | floor | unreviewed | pending re-capture | 508 | MAP02,MAP03,MAP06,MAP08,MAP29,MAP32… |
| `SFLATAD` | floor | unreviewed | pending re-capture | 495 | MAP01,MAP02,MAP04,MAP25,MAP34 |
| `H131` | industrial | unreviewed | pending re-capture | 480 | MAP17,MAP23,MAP34 |
| `C72` | industrial | unreviewed | pending re-capture | 477 | MAP16,MAP17,MAP30,MAP34 |
| `C83` | industrial | unreviewed | pending re-capture | 477 | MAP14,MAP34 |
| `SFLATCB` | floor | unreviewed | pending re-capture | 468 | MAP02,MAP03,MAP04,MAP05,MAP06,MAP07… |
| `SPACECL` | metal | unreviewed | pending re-capture | 463 | MAP02,MAP05,MAP06,MAP08,MAP34 |
| `H11` | industrial | unreviewed | pending re-capture | 462 | MAP13,MAP15,MAP20,MAP23,MAP24,MAP32… |
| `C89` | industrial | unreviewed | pending re-capture | 449 | MAP10,MAP17,MAP18,MAP22,MAP30,MAP34 |
| `SFLATAM` | floor | unreviewed | pending re-capture | 445 | MAP02,MAP03,MAP06,MAP08,MAP25,MAP29… |
| `SFLATAJ` | floor | unreviewed | pending re-capture | 422 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `CASFL4` | industrial | unreviewed | pending re-capture | 412 | MAP10,MAP12,MAP13,MAP14,MAP15,MAP16… |
| `C301` | industrial | unreviewed | pending re-capture | 407 | MAP10,MAP34 |
| `C102` | industrial | unreviewed | pending re-capture | 396 | MAP10,MAP16,MAP17,MAP18,MAP21,MAP22… |
| `C35B` | industrial | unreviewed | pending re-capture | 395 | MAP14,MAP15,MAP16,MAP17,MAP23,MAP31… |
| `SPACECJ` | metal | unreviewed | pending re-capture | 395 | MAP02,MAP05,MAP07,MAP25,MAP34 |
| `SPACECB` | metal | unreviewed | pending re-capture | 394 | MAP05,MAP06,MAP07,MAP25,MAP26,MAP34 |
| `C14` | industrial | unreviewed | pending re-capture | 392 | MAP09,MAP14,MAP30,MAP34 |
| `SFLATAB` | floor | unreviewed | pending re-capture | 391 | MAP01,MAP02,MAP04,MAP08,MAP29 |
| `H531` | industrial | unreviewed | pending re-capture | 390 | MAP17,MAP23,MAP28,MAP34 |
| `C38` | industrial | unreviewed | pending re-capture | 380 | MAP16,MAP34 |
| `HELLAE1` | industrial | unreviewed | pending re-capture | 380 | MAP11,MAP34 |
| `SPACECNT` | metal | unreviewed | pending re-capture | 368 | MAP34 |
| `SPACEAJ1` | metal | unreviewed | pending re-capture | 366 | MAP06,MAP33,MAP34 |
| `SPACECJ1` | metal | unreviewed | pending re-capture | 362 | MAP05,MAP34 |
| `C402` | industrial | unreviewed | pending re-capture | 358 | MAP12,MAP21,MAP31,MAP34 |
| `SPACEAR1` | metal | unreviewed | pending re-capture | 349 | MAP34 |
| `SPACEAK` | metal | unreviewed | pending re-capture | 347 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP08… |
| `SPACEB` | metal | unreviewed | pending re-capture | 347 | MAP02,MAP05,MAP06,MAP07,MAP08,MAP23… |
| `SPACECDT` | metal | unreviewed | pending re-capture | 341 | MAP34 |
| `C311` | industrial | unreviewed | pending re-capture | 339 | MAP12,MAP20,MAP34 |
| `SPACEAJ2` | metal | unreviewed | pending re-capture | 339 | MAP34 |
| `CASFL25` | industrial | unreviewed | pending re-capture | 330 | MAP12,MAP18,MAP20,MAP21,MAP34 |
| `SDOOR6` | door | unreviewed | pending re-capture | 329 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `C57` | industrial | unreviewed | pending re-capture | 328 | MAP12,MAP16,MAP17,MAP18,MAP20,MAP21… |
| `C5` | industrial | unreviewed | pending re-capture | 325 | MAP18,MAP22,MAP30,MAP34 |
| `CASF11` | industrial | unreviewed | pending re-capture | 323 | MAP13,MAP14,MAP17,MAP21,MAP23,MAP30… |
| `C33` | industrial | unreviewed | pending re-capture | 321 | MAP12,MAP16,MAP18,MAP19,MAP22,MAP23… |
| `C43` | industrial | unreviewed | pending re-capture | 321 | MAP09,MAP10,MAP12,MAP18,MAP21 |
| `SPACECIT` | metal | unreviewed | pending re-capture | 319 | MAP34 |
| `SPACEBR` | metal | unreviewed | pending re-capture | 316 | MAP02,MAP05,MAP08,MAP29,MAP34 |
| `ALLBLACK` | industrial | unreviewed | pending re-capture | 315 | MAP00,MAP01,MAP02,MAP03,MAP04,MAP05… |
| `HELLAC` | industrial | unreviewed | pending re-capture | 312 | MAP11,MAP13,MAP15,MAP20,MAP24,MAP28… |
| `C34` | industrial | done | gallery bulk (industrial); ok mean=63.5 var=357 | 308 | MAP09,MAP14,MAP16,MAP21,MAP22,MAP30… |
| `SFLATC` | floor | done | gallery bulk (floor); ok mean=78.6 var=476 | 302 | MAP01,MAP03,MAP04,MAP05,MAP06,MAP07… |
| `SPACEAC2` | metal | done | gallery bulk (metal); ok mean=125.3 var=1045 | 301 | MAP34 |
| `SPACECL1` | metal | done | gallery bulk (metal); ok mean=123.9 var=1040 | 301 | MAP02,MAP03,MAP25,MAP34 |
| `C17` | industrial | done | gallery bulk (industrial); ok mean=123.6 var=1031 | 294 | MAP09,MAP12,MAP16,MAP34 |
| `HTRAC1` | industrial | done | gallery bulk (industrial); ok mean=124.9 var=1042 | 279 | MAP13,MAP15,MAP23,MAP34 |
| `SMONBA` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 279 | MAP01,MAP03,MAP05,MAP06,MAP07,MAP08… |
| `CASF12` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 277 | MAP17,MAP21,MAP22,MAP34 |
| `SHWN1_LG` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 276 | MAP33,MAP34 |
| `SPACEAF1` | metal | done | gallery bulk (metal); ok mean=126.5 var=1007 | 273 | MAP06,MAP34 |
| `C108` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 272 | MAP10,MAP18,MAP21,MAP31,MAP34 |
| `SPACEBL1` | metal | done | gallery bulk (metal); ok mean=126.5 var=1007 | 271 | MAP06,MAP29,MAP34 |
| `SDFLTC` | ceiling | done | gallery bulk (ceiling); ok mean=126.5 var=1007 | 270 | MAP05,MAP07,MAP10,MAP34 |
| `SPACEAO2` | metal | done | gallery bulk (metal); ok mean=126.5 var=1007 | 269 | MAP34 |
| `CASF87` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 264 | MAP09,MAP14,MAP15,MAP16,MAP21,MAP22… |
| `SPACEAB1` | metal | done | gallery bulk (metal); ok mean=126.5 var=1007 | 264 | MAP34 |
| `SPACEBK` | metal | done | gallery bulk (metal); ok mean=126.5 var=1007 | 264 | MAP01,MAP02,MAP03,MAP05,MAP07,MAP08… |
| `HELLAH` | industrial | done | gallery bulk (hell); ok mean=126.5 var=1007 | 259 | MAP11,MAP15,MAP24,MAP34 |
| `C29` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 256 | MAP09,MAP12,MAP17,MAP34 |
| `C45` | industrial | done | gallery bulk (industrial); ok mean=126.5 var=1007 | 249 | MAP09,MAP10,MAP12,MAP13,MAP16,MAP17… |
| `SPACEAK1` | metal | done | gallery bulk (metal); ok mean=126.5 var=1007 | 249 | MAP03,MAP04,MAP05,MAP06,MAP34 |
| `C3F` | industrial | unreviewed | pending re-capture | 244 | MAP22,MAP34 |
| `C64` | industrial | unreviewed | pending re-capture | 241 | MAP14,MAP32,MAP33,MAP34 |
| `HFL15` | industrial | unreviewed | pending re-capture | 237 | MAP13,MAP19,MAP23,MAP24 |
| `HFLATA` | industrial | unreviewed | pending re-capture | 232 | MAP11,MAP17,MAP20,MAP23,MAP24,MAP34 |
| `HTRAC3` | industrial | unreviewed | pending re-capture | 226 | MAP12,MAP13,MAP15,MAP23,MAP24,MAP34 |
| `C67` | industrial | unreviewed | pending re-capture | 225 | MAP16,MAP34 |
| `SPACEAPT` | metal | unreviewed | pending re-capture | 222 | MAP34 |
| `HFLATD` | industrial | unreviewed | pending re-capture | 219 | MAP11,MAP17,MAP28,MAP34 |
| `SPACECA1` | metal | unreviewed | pending re-capture | 219 | MAP29,MAP33,MAP34 |
| `C31` | industrial | unreviewed | pending re-capture | 215 | MAP12,MAP17,MAP21,MAP34 |
| `CTEL1` | industrial | unreviewed | pending re-capture | 214 | MAP10,MAP11,MAP12,MAP13,MAP14,MAP15… |
| `SPACECH1` | metal | unreviewed | pending re-capture | 213 | MAP01,MAP02,MAP08,MAP33,MAP34 |
| `C47` | industrial | unreviewed | pending re-capture | 211 | MAP09,MAP10,MAP14,MAP16,MAP34 |
| `C13` | industrial | unreviewed | pending re-capture | 210 | MAP14,MAP16,MAP22,MAP31,MAP34 |
| `H124` | industrial | unreviewed | pending re-capture | 210 | MAP11,MAP12,MAP15,MAP17,MAP19,MAP20… |
| `SFLATAKR` | floor | unreviewed | pending re-capture | 203 | MAP34 |
| `HELLAMT` | industrial | unreviewed | pending re-capture | 202 | MAP34 |
| `SPACECCB` | metal | unreviewed | pending re-capture | 202 | MAP29,MAP34 |
| `STRAKB1` | industrial | unreviewed | pending re-capture | 202 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `CASF30` | industrial | unreviewed | pending re-capture | 201 | MAP15,MAP34 |
| `SPORT1` | industrial | unreviewed | pending re-capture | 200 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP07… |
| `SFLATAF` | floor | unreviewed | pending re-capture | 199 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `SPACEAW` | metal | unreviewed | pending re-capture | 197 | MAP02,MAP06,MAP34 |
| `H93` | industrial | unreviewed | pending re-capture | 195 | MAP13,MAP20,MAP23 |
| `CDOR5` | industrial | unreviewed | pending re-capture | 192 | MAP18,MAP21,MAP22 |
| `SEXIT` | industrial | unreviewed | pending re-capture | 192 | MAP01,MAP02,MAP03,MAP04,MAP05,MAP06… |
| `CASF104` | industrial | unreviewed | pending re-capture | 190 | MAP09,MAP18,MAP21,MAP22,MAP33,MAP34 |
| `CTRAK1` | industrial | unreviewed | r=0.7, m=0.25 | 190 | MAP15,MAP16,MAP18,MAP19,MAP21,MAP22… |
| `SPACEAO` | metal | unreviewed | r=0.35, m=0.75 | 190 | MAP01,MAP02,MAP05,MAP07,MAP08,MAP29… |
| `C921` | industrial | unreviewed | r=0.7, m=0.25 | 188 | MAP12,MAP13,MAP15,MAP16,MAP18,MAP21… |
| `CASF80` | industrial | unreviewed | r=0.7, m=0.25 | 188 | MAP09,MAP12,MAP14,MAP15,MAP16,MAP18… |
| `H49` | industrial | unreviewed | r=0.7, m=0.25 | 186 | MAP15,MAP17,MAP20,MAP23,MAP24,MAP28… |
| `C74` | industrial | unreviewed | r=0.7, m=0.25 | 184 | MAP13,MAP14,MAP16,MAP21,MAP22,MAP34 |
| `C18` | industrial | unreviewed | r=0.7, m=0.25 | 183 | MAP16,MAP22,MAP34 |
| `H26` | industrial | unreviewed | r=0.7, m=0.25 | 181 | MAP11,MAP13,MAP21,MAP23,MAP24,MAP34 |
| `SPACEBT` | metal | unreviewed | r=0.35, m=0.75 | 181 | MAP05,MAP06,MAP07,MAP29,MAP34 |
| `SPACECG1` | metal | unreviewed | r=0.35, m=0.75 | 181 | MAP03,MAP32,MAP33,MAP34 |
| `HELLAM` | industrial | unreviewed | r=0.7, m=0.25 | 180 | MAP11,MAP21,MAP34 |
| `CBTRAKA` | industrial | unreviewed | r=0.7, m=0.25 | 176 | MAP11,MAP12,MAP13,MAP14,MAP15,MAP16… |
| `SPACEBJ` | metal | unreviewed | r=0.35, m=0.75 | 175 | MAP01,MAP05,MAP06,MAP07,MAP34 |
| `C46` | industrial | unreviewed | r=0.7, m=0.25 | 174 | MAP10,MAP12,MAP21,MAP30,MAP34 |
| `C90` | industrial | unreviewed | r=0.7, m=0.25 | 173 | MAP12,MAP30 |
| `H119` | industrial | unreviewed | r=0.7, m=0.25 | 172 | MAP13,MAP23,MAP31,MAP34 |
| `H97` | industrial | unreviewed | r=0.7, m=0.25 | 171 | MAP15,MAP18,MAP20,MAP24 |
| `SPACAMMT` | industrial | unreviewed | r=0.7, m=0.25 | 171 | MAP34 |
| `SFLATDC` | floor | unreviewed | r=0.9, m=0.05 | 170 | MAP02,MAP04,MAP34 |
| `C2001` | industrial | unreviewed | r=0.7, m=0.25 | 169 | MAP13,MAP18,MAP20,MAP34 |
| `CASFL24` | industrial | unreviewed | r=0.7, m=0.25 | 166 | MAP12,MAP16,MAP21,MAP34 |
| `H18` | industrial | unreviewed | r=0.7, m=0.25 | 165 | MAP19,MAP20,MAP21,MAP23 |
| `HFLATO` | industrial | unreviewed | r=0.7, m=0.25 | 165 | MAP11,MAP17,MAP20,MAP23,MAP34 |
| `SPACEAN` | metal | unreviewed | r=0.35, m=0.75 | 165 | MAP01,MAP02,MAP04,MAP07,MAP08,MAP29… |
| `SPACEBG1` | metal | unreviewed | r=0.35, m=0.75 | 163 | MAP03,MAP34 |
| `H41` | industrial | unreviewed | r=0.7, m=0.25 | 160 | MAP11,MAP15,MAP20,MAP24 |
| `C20` | industrial | unreviewed | r=0.7, m=0.25 | 158 | MAP09,MAP14,MAP15,MAP16,MAP22,MAP34 |
| `HELLAE` | industrial | unreviewed | r=0.7, m=0.25 | 158 | MAP11,MAP24,MAP34 |
| `C35L` | industrial | unreviewed | r=0.7, m=0.25 | 157 | MAP34 |
| `CASF109` | industrial | unreviewed | r=0.7, m=0.25 | 156 | MAP15,MAP18,MAP22,MAP23,MAP34 |
| `SUPPORT6` | industrial | unreviewed | r=0.7, m=0.25 | 156 | MAP34 |
| `SPACEAL1` | metal | unreviewed | r=0.35, m=0.75 | 155 | MAP08,MAP33,MAP34 |
| `SPACEALT` | metal | unreviewed | r=0.35, m=0.75 | 153 | MAP34 |
| `HFLATK` | industrial | unreviewed | r=0.7, m=0.25 | 151 | MAP13,MAP21,MAP23,MAP34 |
| `SPACECO1` | metal | unreviewed | r=0.35, m=0.75 | 151 | MAP25,MAP29,MAP34 |
| `C405` | industrial | unreviewed | r=0.7, m=0.25 | 150 | MAP31,MAP34 |
| `SPACEAV1` | metal | unreviewed | r=0.35, m=0.75 | 150 | MAP06,MAP29,MAP34 |
| `WFALL01` | industrial | unreviewed | r=0.7, m=0.25 | 148 | MAP10,MAP22,MAP34 |
| `CASFL26` | industrial | unreviewed | r=0.7, m=0.25 | 147 | MAP09,MAP15,MAP16,MAP17,MAP18,MAP22… |
| `HELLAHT` | industrial | unreviewed | r=0.7, m=0.25 | 147 | MAP20,MAP34 |
| `SPACEBN` | metal | unreviewed | r=0.35, m=0.75 | 147 | MAP05,MAP07,MAP12,MAP34 |
| `STRAKR1` | industrial | unreviewed | r=0.7, m=0.25 | 146 | MAP02,MAP03,MAP04,MAP05,MAP07,MAP08… |
| `HELLAK` | industrial | unreviewed | r=0.7, m=0.25 | 143 | MAP11,MAP15,MAP23,MAP34 |
| `C911` | industrial | unreviewed | r=0.7, m=0.25 | 142 | MAP12,MAP13,MAP16,MAP18,MAP22,MAP30… |
| `D64N1_01` | industrial | unreviewed | r=0.7, m=0.25 | 142 | MAP07,MAP16,MAP18,MAP22,MAP24,MAP25… |
| `H10` | industrial | unreviewed | r=0.7, m=0.25 | 142 | MAP13,MAP20,MAP23,MAP24,MAP31,MAP34 |
| `SFLATCF` | floor | unreviewed | r=0.9, m=0.05 | 142 | MAP02,MAP06,MAP08,MAP29,MAP34 |
| `SPACECA` | metal | unreviewed | r=0.35, m=0.75 | 142 | MAP01,MAP05,MAP06,MAP07,MAP29,MAP34 |
| `C50C` | industrial | unreviewed | r=0.7, m=0.25 | 141 | MAP34 |
| `SDFLTCB` | ceiling | unreviewed | r=0.8, m=0.15 | 141 | MAP03,MAP14,MAP34 |
| `C48` | industrial | unreviewed | r=0.7, m=0.25 | 140 | MAP10,MAP16,MAP23,MAP34 |
| `H51` | industrial | unreviewed | r=0.7, m=0.25 | 140 | MAP15,MAP20,MAP32 |
| `C14F` | industrial | unreviewed | r=0.7, m=0.25 | 139 | MAP34 |
| `HELLAF` | industrial | unreviewed | r=0.7, m=0.25 | 139 | MAP11,MAP20,MAP24,MAP34 |
| `CASF20B` | industrial | unreviewed | r=0.7, m=0.25 | 138 | MAP14,MAP15,MAP19,MAP34 |
| `H113` | industrial | unreviewed | r=0.7, m=0.25 | 137 | MAP24 |
| `SPACEBO` | metal | unreviewed | r=0.35, m=0.75 | 136 | MAP05,MAP07,MAP25,MAP29,MAP34 |
| `CRTRAKA` | industrial | unreviewed | r=0.7, m=0.25 | 135 | MAP11,MAP12,MAP13,MAP16,MAP18,MAP19… |
| `C22` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 132 | MAP12,MAP13,MAP16,MAP18,MAP19,MAP22… |
| `CYTRAKA` | industrial | unreviewed | r=0.7, m=0.25 | 132 | MAP10,MAP11,MAP12,MAP13,MAP16,MAP18… |
| `MOUNTA` | industrial | unreviewed | r=0.7, m=0.25 | 132 | MAP02,MAP04,MAP05,MAP34 |
| `SDOOR1` | door | unreviewed | r=0.45, m=0.65 | 132 | MAP01,MAP02,MAP04,MAP05,MAP07,MAP08… |
| `CASFL2` | industrial | unreviewed | r=0.7, m=0.25 | 131 | MAP09,MAP16,MAP18,MAP22,MAP23,MAP34 |
| `SFLATAI` | floor | unreviewed | r=0.9, m=0.05 | 130 | MAP02,MAP04,MAP08,MAP25,MAP32 |
| `H36` | industrial | unreviewed | r=0.7, m=0.25 | 127 | MAP10,MAP20,MAP24,MAP34 |
| `SDOOR2` | door | unreviewed | r=0.45, m=0.65 | 127 | MAP05,MAP06,MAP07,MAP08,MAP29,MAP34 |
| `SPACECF` | metal | unreviewed | r=0.35, m=0.75 | 125 | MAP05,MAP07,MAP34 |
| `CASF07` | industrial | unreviewed | r=0.7, m=0.25 | 124 | MAP14,MAP15,MAP16,MAP18,MAP22,MAP24… |
| `SPACEAG1` | metal | unreviewed | r=0.35, m=0.75 | 124 | MAP29,MAP34 |
| `C341` | industrial | unreviewed | r=0.7, m=0.25 | 123 | MAP12,MAP18,MAP34 |
| `H15` | industrial | unreviewed | r=0.7, m=0.25 | 121 | MAP13,MAP21,MAP23,MAP27,MAP31,MAP34 |
| `D64W2_01` | industrial | unreviewed | r=0.7, m=0.25 | 120 | MAP10,MAP11,MAP34 |
| `C331` | industrial | unreviewed | r=0.7, m=0.25 | 119 | MAP12,MAP19,MAP34 |
| `SPACEAH` | metal | unreviewed | r=0.35, m=0.75 | 117 | MAP01,MAP02,MAP05,MAP07,MAP34 |
| `CASFL1` | industrial | unreviewed | r=0.7, m=0.25 | 116 | MAP09,MAP12,MAP13,MAP16,MAP18,MAP22… |
| `H129` | industrial | unreviewed | r=0.7, m=0.25 | 116 | MAP15,MAP24 |
| `SMONLC1` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 116 | MAP03,MAP33,MAP34 |
| `CASFL23` | industrial | unreviewed | r=0.7, m=0.25 | 115 | MAP14,MAP16,MAP18,MAP21,MAP23,MAP30… |
| `OUTTEX58` | industrial | unreviewed | r=0.7, m=0.25 | 113 | MAP34 |
| `SMONF1` | industrial | unreviewed | r=0.7, m=0.25 | 113 | MAP06,MAP34 |
| `C21` | industrial | unreviewed | r=0.7, m=0.25 | 112 | MAP13,MAP16,MAP18,MAP20,MAP34 |
| `H112` | industrial | unreviewed | r=0.7, m=0.25 | 112 | MAP15,MAP23,MAP24,MAP34 |
| `STRAKY1` | industrial | unreviewed | r=0.7, m=0.25 | 111 | MAP02,MAP03,MAP05,MAP06,MAP07,MAP08… |
| `CTRAK0` | industrial | unreviewed | r=0.7, m=0.25 | 110 | MAP10,MAP14,MAP20,MAP21,MAP22,MAP30 |
| `C204` | industrial | unreviewed | r=0.7, m=0.25 | 107 | MAP10,MAP18,MAP34 |
| `CASF89` | industrial | unreviewed | r=0.7, m=0.25 | 106 | MAP12,MAP16,MAP21,MAP23,MAP34 |
| `CDOR3` | industrial | unreviewed | r=0.7, m=0.25 | 106 | MAP16,MAP18,MAP21,MAP22,MAP34 |
| `SFALL01` | industrial | unreviewed | r=0.7, m=0.25 | 105 | MAP34 |
| `H24` | industrial | unreviewed | r=0.7, m=0.25 | 104 | MAP20,MAP23,MAP24 |
| `CASF204` | industrial | unreviewed | r=0.7, m=0.25 | 103 | MAP15,MAP22,MAP30 |
| `CASF200` | industrial | unreviewed | r=0.7, m=0.25 | 101 | MAP18,MAP22,MAP34 |
| `H21` | industrial | unreviewed | r=0.7, m=0.25 | 101 | MAP13,MAP15,MAP20,MAP23,MAP24,MAP34 |
| `SMONDA` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 101 | MAP01,MAP02,MAP04,MAP05,MAP06,MAP08… |
| `SPACEE2` | metal | unreviewed | r=0.35, m=0.75 | 101 | MAP34 |
| `SPACEAC1` | metal | unreviewed | r=0.35, m=0.75 | 100 | MAP34 |
| `C78` | industrial | unreviewed | r=0.7, m=0.25 | 99 | MAP16,MAP18,MAP20,MAP22,MAP34 |
| `CASFL6` | industrial | unreviewed | r=0.7, m=0.25 | 99 | MAP16,MAP17,MAP21,MAP23,MAP31,MAP34 |
| `H991` | industrial | unreviewed | r=0.7, m=0.25 | 97 | MAP15,MAP23,MAP24,MAP34 |
| `SDOOR11` | door | unreviewed | r=0.45, m=0.65 | 97 | MAP07,MAP34 |
| `D64B2_01` | industrial | unreviewed | r=0.7, m=0.25 | 96 | MAP08,MAP18,MAP32,MAP34 |
| `H20` | industrial | unreviewed | r=0.7, m=0.25 | 96 | MAP15,MAP24,MAP34 |
| `SPACEADB` | metal | unreviewed | r=0.35, m=0.75 | 96 | MAP34 |
| `SPACEBB` | metal | unreviewed | r=0.35, m=0.75 | 94 | MAP01,MAP06,MAP07,MAP34 |
| `SPACEBI` | metal | unreviewed | r=0.35, m=0.75 | 93 | MAP05,MAP07,MAP33,MAP34 |
| `SDOOR3` | door | unreviewed | r=0.45, m=0.65 | 92 | MAP02,MAP05,MAP06,MAP07,MAP08,MAP34 |
| `C408` | industrial | unreviewed | r=0.7, m=0.25 | 90 | MAP12,MAP13,MAP18 |
| `H44` | industrial | unreviewed | r=0.7, m=0.25 | 90 | MAP11,MAP24,MAP34 |
| `SPACEC9` | metal | unreviewed | r=0.35, m=0.75 | 90 | MAP34 |
| `C42` | industrial | unreviewed | r=0.7, m=0.25 | 89 | MAP09,MAP16,MAP20,MAP21,MAP22,MAP34 |
| `CASFL99` | industrial | unreviewed | r=0.7, m=0.25 | 89 | MAP10,MAP12,MAP18,MAP21,MAP22,MAP34 |
| `H111` | industrial | unreviewed | r=0.7, m=0.25 | 87 | MAP20,MAP34 |
| `HFLATE` | industrial | unreviewed | r=0.7, m=0.25 | 87 | MAP11,MAP17,MAP34 |
| `C100` | industrial | unreviewed | r=0.7, m=0.25 | 86 | MAP17,MAP34 |
| `C332` | industrial | unreviewed | r=0.7, m=0.25 | 85 | MAP34 |
| `MOUNTC` | industrial | unreviewed | r=0.7, m=0.25 | 85 | MAP12,MAP14,MAP30,MAP34 |
| `SFLATCH` | floor | unreviewed | r=0.9, m=0.05 | 85 | MAP01,MAP02,MAP03,MAP08,MAP34 |
| `C63` | industrial | unreviewed | r=0.7, m=0.25 | 84 | MAP13,MAP14,MAP17,MAP31,MAP34 |
| `H53` | industrial | unreviewed | r=0.7, m=0.25 | 84 | MAP13,MAP23 |
| `H69` | industrial | unreviewed | r=0.7, m=0.25 | 84 | MAP20,MAP34 |
| `SDFLTAE` | ceiling | unreviewed | r=0.8, m=0.15 | 84 | MAP02,MAP03,MAP04,MAP07,MAP08,MAP34 |
| `H130` | industrial | unreviewed | r=0.7, m=0.25 | 83 | MAP23,MAP24,MAP31,MAP34 |
| `H57` | industrial | unreviewed | r=0.7, m=0.25 | 83 | MAP21,MAP23,MAP34 |
| `SPACEBM1` | metal | unreviewed | r=0.35, m=0.75 | 83 | MAP34 |
| `SPACECCT` | metal | unreviewed | r=0.35, m=0.75 | 83 | MAP29,MAP34 |
| `HDOR1` | industrial | unreviewed | r=0.7, m=0.25 | 82 | MAP11,MAP13,MAP20,MAP28,MAP34 |
| `HELLAD` | industrial | unreviewed | r=0.7, m=0.25 | 82 | MAP11,MAP15,MAP21,MAP34 |
| `MOUNTB` | industrial | unreviewed | r=0.7, m=0.25 | 81 | MAP10,MAP16,MAP34 |
| `SPACEAD1` | metal | unreviewed | r=0.35, m=0.75 | 80 | MAP02,MAP04,MAP34 |
| `SWXSAA` | industrial | unreviewed | r=0.7, m=0.25 | 80 | MAP01,MAP02,MAP04,MAP05,MAP06,MAP07… |
| `SWXSEA` | industrial | unreviewed | r=0.7, m=0.25 | 79 | MAP04,MAP05,MAP06,MAP29,MAP33,MAP34 |
| `SFLATCC` | floor | unreviewed | r=0.9, m=0.05 | 78 | MAP03,MAP04,MAP05,MAP06,MAP34 |
| `SPACECH` | metal | unreviewed | r=0.35, m=0.75 | 78 | MAP02,MAP06,MAP08,MAP25,MAP34 |
| `HFL13` | industrial | unreviewed | r=0.7, m=0.25 | 77 | MAP15,MAP24 |
| `HFLATB` | industrial | unreviewed | r=0.7, m=0.25 | 76 | MAP11,MAP17,MAP23,MAP28,MAP32,MAP34 |
| `SPACECN1` | metal | unreviewed | r=0.35, m=0.75 | 75 | MAP06,MAP34 |
| `H55` | industrial | unreviewed | r=0.7, m=0.25 | 74 | MAP15,MAP20,MAP23,MAP24,MAP34 |
| `HTRAC2` | industrial | unreviewed | r=0.7, m=0.25 | 74 | MAP13,MAP18,MAP21,MAP23,MAP24,MAP34 |
| `SWXCA` | industrial | unreviewed | r=0.7, m=0.25 | 74 | MAP10,MAP12,MAP13,MAP16,MAP18,MAP20… |
| `HFLATH` | industrial | unreviewed | r=0.7, m=0.25 | 73 | MAP11,MAP17,MAP20,MAP28,MAP34 |
| `SFLATAR` | floor | unreviewed | r=0.9, m=0.05 | 73 | MAP02,MAP08,MAP34 |
| `C1` | industrial | unreviewed | r=0.7, m=0.25 | 72 | MAP09,MAP13,MAP15,MAP16,MAP18,MAP22… |
| `C75` | industrial | unreviewed | r=0.7, m=0.25 | 72 | MAP10,MAP15,MAP16,MAP30,MAP34 |
| `CASFL58` | industrial | unreviewed | r=0.7, m=0.25 | 72 | MAP10 |
| `SDOOR8` | door | unreviewed | r=0.45, m=0.65 | 72 | MAP34 |
| `CDOR4` | industrial | unreviewed | r=0.7, m=0.25 | 71 | MAP10,MAP15,MAP21,MAP22,MAP34 |
| `H28` | industrial | unreviewed | r=0.7, m=0.25 | 69 | MAP20,MAP34 |
| `H541` | industrial | unreviewed | r=0.7, m=0.25 | 69 | MAP21,MAP23,MAP28 |
| `CDOR2` | industrial | unreviewed | r=0.7, m=0.25 | 68 | MAP10,MAP22,MAP34 |
| `H881` | industrial | unreviewed | r=0.7, m=0.25 | 68 | MAP20,MAP23,MAP24 |
| `CASFL57` | industrial | unreviewed | r=0.7, m=0.25 | 67 | MAP10,MAP16,MAP21,MAP31 |
| `H1221` | industrial | unreviewed | r=0.7, m=0.25 | 67 | MAP19,MAP23,MAP34 |
| `SDFLTB` | ceiling | unreviewed | r=0.8, m=0.15 | 67 | MAP02,MAP04,MAP05,MAP08,MAP34 |
| `C19` | industrial | unreviewed | r=0.7, m=0.25 | 66 | MAP09,MAP16,MAP18,MAP34 |
| `H53T` | industrial | unreviewed | r=0.7, m=0.25 | 66 | MAP34 |
| `SDOOR5` | door | unreviewed | r=0.45, m=0.65 | 66 | MAP03,MAP20,MAP34 |
| `SFLATCG` | floor | unreviewed | r=0.9, m=0.05 | 66 | MAP05,MAP07,MAP08,MAP34 |
| `SPACEAE` | metal | unreviewed | r=0.35, m=0.75 | 65 | MAP02,MAP03,MAP07 |
| `SPACEAV` | metal | unreviewed | r=0.35, m=0.75 | 65 | MAP01,MAP02,MAP06,MAP08,MAP29,MAP34 |
| `BFALL01` | industrial | unreviewed | r=0.7, m=0.25 | 64 | MAP18,MAP34 |
| `CASF102` | industrial | unreviewed | r=0.7, m=0.25 | 64 | MAP18,MAP22 |
| `SFLATAN` | floor | unreviewed | r=0.9, m=0.05 | 64 | MAP02,MAP05,MAP06,MAP08,MAP34 |
| `C62` | industrial | unreviewed | r=0.7, m=0.25 | 62 | MAP14,MAP16,MAP21,MAP22,MAP32,MAP34 |
| `SPACE` | metal | unreviewed | r=0.35, m=0.75 | 62 | MAP00,MAP01,MAP02,MAP04,MAP05,MAP07… |
| `D64W1_01` | industrial | unreviewed | r=0.7, m=0.25 | 61 | MAP08,MAP14,MAP15,MAP16,MAP22,MAP23… |
| `FRSKYNRM` | industrial | unreviewed | r=0.7, m=0.25 | 61 | MAP22,MAP24,MAP28,MAP34 |
| `HFL14` | industrial | unreviewed | r=0.7, m=0.25 | 61 | MAP13,MAP15,MAP23,MAP24 |
| `OUTTEX50` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 61 | MAP34 |
| `SPACECE` | metal | unreviewed | r=0.35, m=0.75 | 61 | MAP03,MAP05,MAP07 |
| `SWXSDA` | industrial | unreviewed | r=0.7, m=0.25 | 61 | MAP02,MAP05,MAP08,MAP29,MAP33,MAP34 |
| `C51` | industrial | unreviewed | r=0.7, m=0.25 | 60 | MAP09,MAP14,MAP16,MAP34 |
| `CASFL7` | industrial | unreviewed | r=0.7, m=0.25 | 60 | MAP09,MAP12,MAP14,MAP17,MAP22,MAP30… |
| `SPACEBS` | metal | unreviewed | r=0.35, m=0.75 | 59 | MAP02,MAP05,MAP06,MAP07,MAP34 |
| `C9` | industrial | unreviewed | r=0.7, m=0.25 | 58 | MAP22,MAP34 |
| `HTRAC6` | industrial | unreviewed | r=0.7, m=0.25 | 58 | MAP24,MAP34 |
| `OUTTEX67` | industrial | unreviewed | r=0.7, m=0.25 | 58 | MAP34 |
| `SPACEBH` | metal | unreviewed | r=0.35, m=0.75 | 58 | MAP07,MAP33,MAP34 |
| `H931` | industrial | unreviewed | r=0.7, m=0.25 | 57 | MAP20,MAP24,MAP34 |
| `OUTTEX23` | industrial | unreviewed | r=0.7, m=0.25 | 57 | MAP34 |
| `SPACEC7` | metal | unreviewed | r=0.35, m=0.75 | 57 | MAP34 |
| `D64B1_01` | industrial | unreviewed | r=0.7, m=0.25 | 56 | MAP17,MAP18,MAP21,MAP23,MAP24,MAP34 |
| `DTWMD20` | industrial | unreviewed | r=0.7, m=0.25 | 56 | MAP34 |
| `HELLAO` | industrial | unreviewed | r=0.7, m=0.25 | 55 | MAP11,MAP23,MAP34 |
| `C104` | industrial | unreviewed | r=0.7, m=0.25 | 54 | MAP12,MAP14,MAP18,MAP30,MAP34 |
| `H118` | industrial | unreviewed | r=0.7, m=0.25 | 54 | MAP13,MAP23,MAP24,MAP34 |
| `H94` | industrial | unreviewed | r=0.7, m=0.25 | 54 | MAP20,MAP23,MAP24 |
| `C2` | industrial | unreviewed | r=0.7, m=0.25 | 53 | MAP16,MAP22,MAP34 |
| `HFLATC` | industrial | unreviewed | r=0.7, m=0.25 | 53 | MAP15,MAP17,MAP24,MAP34 |
| `SPACEAX` | metal | unreviewed | r=0.35, m=0.75 | 51 | MAP02,MAP34 |
| `SPACEAY` | metal | unreviewed | r=0.35, m=0.75 | 51 | MAP02,MAP34 |
| `CASF203` | industrial | unreviewed | r=0.7, m=0.25 | 50 | MAP15,MAP22,MAP34 |
| `CASFL53` | industrial | unreviewed | r=0.7, m=0.25 | 50 | MAP10,MAP24,MAP34 |
| `SPACEBQ1` | metal | unreviewed | r=0.35, m=0.75 | 50 | MAP07,MAP34 |
| `SPACECP1` | metal | unreviewed | r=0.35, m=0.75 | 50 | MAP02,MAP05,MAP06,MAP08,MAP29,MAP34 |
| `C50B` | industrial | unreviewed | r=0.7, m=0.25 | 49 | MAP34 |
| `H16` | industrial | unreviewed | r=0.7, m=0.25 | 49 | MAP23 |
| `OUTTEX20` | industrial | unreviewed | r=0.7, m=0.25 | 49 | MAP34 |
| `SPACEAE2` | metal | unreviewed | r=0.35, m=0.75 | 49 | MAP34 |
| `SDFLTCC` | ceiling | unreviewed | r=0.8, m=0.15 | 48 | MAP05,MAP07,MAP29 |
| `SFLATAP` | floor | unreviewed | r=0.9, m=0.05 | 48 | MAP01,MAP02,MAP05,MAP06,MAP08,MAP32… |
| `C79` | industrial | unreviewed | r=0.7, m=0.25 | 47 | MAP13,MAP17,MAP23,MAP34 |
| `H23` | industrial | unreviewed | r=0.7, m=0.25 | 46 | MAP23,MAP31,MAP34 |
| `SFLATD` | floor | unreviewed | r=0.9, m=0.05 | 46 | MAP01,MAP33,MAP34 |
| `SPACECD1` | metal | unreviewed | r=0.35, m=0.75 | 46 | MAP34 |
| `H48` | industrial | unreviewed | r=0.7, m=0.25 | 45 | MAP15,MAP20,MAP34 |
| `OUTTEX37` | industrial | unreviewed | r=0.7, m=0.25 | 45 | MAP34 |
| `H29` | industrial | unreviewed | r=0.7, m=0.25 | 44 | MAP11,MAP20,MAP34 |
| `H31` | industrial | unreviewed | r=0.7, m=0.25 | 44 | MAP20,MAP23,MAP24,MAP34 |
| `C76` | industrial | unreviewed | r=0.7, m=0.25 | 43 | MAP16,MAP34 |
| `HFLATJ` | industrial | unreviewed | r=0.7, m=0.25 | 43 | MAP11,MAP34 |
| `C109` | industrial | unreviewed | r=0.7, m=0.25 | 42 | MAP10 |
| `C86` | industrial | unreviewed | r=0.7, m=0.25 | 42 | MAP23,MAP34 |
| `CASFL5` | industrial | unreviewed | r=0.7, m=0.25 | 42 | MAP15,MAP16,MAP17,MAP18,MAP22,MAP31 |
| `CASFL8` | industrial | unreviewed | r=0.7, m=0.25 | 42 | MAP16,MAP22,MAP34 |
| `H77` | industrial | unreviewed | r=0.7, m=0.25 | 42 | MAP23,MAP24 |
| `HELLAO1` | industrial | unreviewed | r=0.7, m=0.25 | 42 | MAP34 |
| `FRSKYGRN` | industrial | unreviewed | r=0.7, m=0.25 | 41 | MAP23,MAP32,MAP34 |
| `H33` | industrial | unreviewed | r=0.7, m=0.25 | 41 | MAP20,MAP34 |
| `SPACELAT` | metal | unreviewed | r=0.35, m=0.75 | 41 | MAP01,MAP34 |
| `C77` | industrial | unreviewed | r=0.7, m=0.25 | 40 | MAP13,MAP34 |
| `H110` | industrial | unreviewed | r=0.7, m=0.25 | 40 | MAP23,MAP34 |
| `H79` | industrial | unreviewed | r=0.7, m=0.25 | 40 | MAP15,MAP23,MAP34 |
| `CASF105` | industrial | unreviewed | r=0.7, m=0.25 | 39 | MAP12,MAP22,MAP34 |
| `CASF106` | industrial | unreviewed | r=0.7, m=0.25 | 39 | MAP10,MAP18,MAP27 |
| `C80` | industrial | unreviewed | r=0.7, m=0.25 | 38 | MAP16,MAP17,MAP22,MAP34 |
| `H36BGLOW` | tech | unreviewed | r=0.4, m=0.55, e=0.6 | 38 | MAP20 |
| `HTRAC4` | industrial | unreviewed | r=0.7, m=0.25 | 38 | MAP13,MAP24,MAP34 |
| `SDFLTBB` | ceiling | unreviewed | r=0.8, m=0.15 | 38 | MAP10,MAP34 |
| `SDOOR4` | door | unreviewed | r=0.45, m=0.65 | 38 | MAP06,MAP34 |
| `HFL12` | industrial | unreviewed | r=0.7, m=0.25 | 37 | MAP23,MAP24,MAP28 |
| `OUTTEX21` | industrial | unreviewed | r=0.7, m=0.25 | 37 | MAP34 |
| `C24` | industrial | unreviewed | r=0.7, m=0.25 | 36 | MAP09,MAP16,MAP22 |
| `D64N2_01` | industrial | unreviewed | r=0.7, m=0.25 | 36 | MAP34 |
| `HDOR10` | industrial | unreviewed | r=0.7, m=0.25 | 36 | MAP13,MAP15,MAP19,MAP23,MAP24,MAP30… |
| `OUTTEX05` | industrial | unreviewed | r=0.7, m=0.25 | 36 | MAP34 |
| `SPACEAZ` | metal | unreviewed | r=0.35, m=0.75 | 36 | MAP01,MAP03,MAP06 |
| `SPACEBF` | metal | unreviewed | r=0.35, m=0.75 | 36 | MAP03,MAP08,MAP34 |
| `C302` | industrial | unreviewed | r=0.7, m=0.25 | 35 | MAP10,MAP31,MAP34 |
| `H67` | industrial | unreviewed | r=0.7, m=0.25 | 35 | MAP10,MAP11,MAP20,MAP34 |
| `SFLATDE` | floor | unreviewed | r=0.9, m=0.05 | 35 | MAP03,MAP08,MAP34 |
| `C206` | industrial | unreviewed | r=0.7, m=0.25 | 34 | MAP10,MAP22 |
| `C61` | industrial | unreviewed | r=0.7, m=0.25 | 34 | MAP10,MAP34 |
| `CASFL54` | industrial | unreviewed | r=0.7, m=0.25 | 34 | MAP09,MAP12,MAP16,MAP20 |
| `H116` | industrial | unreviewed | r=0.7, m=0.25 | 34 | MAP13,MAP20,MAP34 |
| `SDOOR5A` | door | unreviewed | r=0.45, m=0.65 | 34 | MAP34 |
| `SMONEA` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 34 | MAP02,MAP04,MAP25,MAP29,MAP34 |
| `SPACEAK2` | metal | unreviewed | r=0.35, m=0.75 | 33 | MAP34 |
| `C471` | industrial | unreviewed | r=0.7, m=0.25 | 32 | MAP10,MAP18 |
| `H65` | industrial | unreviewed | r=0.7, m=0.25 | 32 | MAP20,MAP23,MAP24,MAP34 |
| `H96` | industrial | unreviewed | r=0.7, m=0.25 | 32 | MAP20,MAP24,MAP34 |
| `SPACEAS` | metal | unreviewed | r=0.35, m=0.75 | 32 | MAP02,MAP03,MAP34 |
| `SPACECO` | metal | unreviewed | r=0.35, m=0.75 | 32 | MAP03,MAP05,MAP07,MAP34 |
| `SWXCKLB` | industrial | unreviewed | r=0.7, m=0.25 | 32 | MAP11,MAP13,MAP17,MAP19,MAP21,MAP23… |
| `CASF108` | industrial | unreviewed | r=0.7, m=0.25 | 31 | MAP12,MAP15,MAP18,MAP21,MAP34 |
| `H63` | industrial | unreviewed | r=0.7, m=0.25 | 31 | MAP23,MAP31,MAP34 |
| `HELLAS` | industrial | unreviewed | r=0.7, m=0.25 | 31 | MAP28,MAP29,MAP33,MAP34 |
| `C41` | industrial | unreviewed | r=0.7, m=0.25 | 30 | MAP12,MAP16,MAP21,MAP34 |
| `C97` | industrial | unreviewed | r=0.7, m=0.25 | 30 | MAP16,MAP17,MAP18,MAP34 |
| `C97R` | industrial | unreviewed | r=0.7, m=0.25 | 30 | MAP16,MAP17,MAP18,MAP34 |
| `CMPSW10A` | industrial | unreviewed | r=0.7, m=0.25 | 30 | MAP02,MAP34 |
| `H581` | industrial | unreviewed | r=0.7, m=0.25 | 30 | MAP13,MAP21,MAP34 |
| `SDOOR5B` | door | unreviewed | r=0.45, m=0.65 | 30 | MAP05 |
| `SPACEAU` | metal | unreviewed | r=0.35, m=0.75 | 30 | MAP01,MAP04,MAP34 |
| `C44C` | industrial | unreviewed | r=0.7, m=0.25 | 29 | MAP34 |
| `C6F` | industrial | unreviewed | r=0.7, m=0.25 | 29 | MAP34 |
| `H14` | industrial | unreviewed | r=0.7, m=0.25 | 29 | MAP19,MAP34 |
| `HTELA` | industrial | unreviewed | r=0.7, m=0.25 | 29 | MAP18,MAP20,MAP24,MAP34 |
| `SMONCA` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 29 | MAP02,MAP03,MAP04,MAP08,MAP25,MAP34 |
| `SPACEAE1` | metal | unreviewed | r=0.35, m=0.75 | 29 | MAP03,MAP34 |
| `C49` | industrial | unreviewed | r=0.7, m=0.25 | 28 | MAP13,MAP16,MAP34 |
| `CLOUDBRN` | industrial | unreviewed | r=0.7, m=0.25 | 28 | MAP10,MAP16,MAP17,MAP27,MAP34 |
| `H27` | industrial | unreviewed | r=0.7, m=0.25 | 28 | MAP20,MAP21,MAP34 |
| `HELLAK1` | industrial | unreviewed | r=0.7, m=0.25 | 28 | MAP34 |
| `OUTTEX39` | industrial | unreviewed | r=0.7, m=0.25 | 28 | MAP34 |
| `SFLATAE` | floor | unreviewed | r=0.9, m=0.05 | 28 | MAP01,MAP03,MAP04,MAP25,MAP29,MAP34 |
| `SPACEAU1` | metal | unreviewed | r=0.35, m=0.75 | 28 | MAP34 |
| `H261` | industrial | unreviewed | r=0.7, m=0.25 | 27 | MAP23,MAP34 |
| `H32` | industrial | unreviewed | r=0.7, m=0.25 | 27 | MAP23,MAP34 |
| `STRAKX` | industrial | unreviewed | r=0.7, m=0.25 | 27 | MAP02,MAP32,MAP34 |
| `TITLEB` | industrial | unreviewed | r=0.7, m=0.25 | 27 | MAP33 |
| `C306` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP10,MAP34 |
| `C60` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP17,MAP34 |
| `H50` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP15,MAP20 |
| `H91` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP20,MAP24,MAP34 |
| `HELLAN` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP11,MAP34 |
| `OUTTEX24` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP34 |
| `SWXCKA` | industrial | unreviewed | r=0.7, m=0.25 | 26 | MAP10,MAP17,MAP18,MAP22,MAP23,MAP34 |
| `C303` | industrial | unreviewed | r=0.7, m=0.25 | 25 | MAP10,MAP34 |
| `C307B1` | industrial | unreviewed | r=0.7, m=0.25 | 25 | MAP15,MAP18,MAP23,MAP30,MAP34 |
| `C211` | industrial | unreviewed | r=0.7, m=0.25 | 24 | MAP18,MAP34 |
| `C24F` | industrial | unreviewed | r=0.7, m=0.25 | 24 | MAP34 |
| `C25` | industrial | unreviewed | r=0.7, m=0.25 | 24 | MAP16,MAP34 |
| `H13` | industrial | unreviewed | r=0.7, m=0.25 | 24 | MAP20,MAP23,MAP34 |
| `H25` | industrial | unreviewed | r=0.7, m=0.25 | 24 | MAP23,MAP34 |
| `SPACEBA` | metal | unreviewed | r=0.35, m=0.75 | 24 | MAP01,MAP04,MAP08 |
| `C308` | industrial | unreviewed | r=0.7, m=0.25 | 23 | MAP10,MAP12,MAP21,MAP31,MAP34 |
| `TITLEA` | industrial | unreviewed | r=0.7, m=0.25 | 23 | MAP33 |
| `SWXSCA` | industrial | unreviewed | r=0.7, m=0.25 | 22 | MAP05,MAP07,MAP08,MAP29,MAP34 |
| `C6` | industrial | unreviewed | r=0.7, m=0.25 | 21 | MAP16,MAP34 |
| `FRSKYBLU` | industrial | unreviewed | r=0.7, m=0.25 | 21 | MAP34 |
| `OUTTEX49` | industrial | unreviewed | r=0.7, m=0.25 | 21 | MAP34 |
| `SPACEAM1` | metal | unreviewed | r=0.35, m=0.75 | 21 | MAP34 |
| `SWXCLB` | industrial | unreviewed | r=0.7, m=0.25 | 21 | MAP14,MAP17,MAP34 |
| `CASFL28` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP16,MAP34 |
| `CASFL9` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP16,MAP22,MAP31,MAP34 |
| `H117` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP20,MAP34 |
| `H30` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP23,MAP34 |
| `HELLAI` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP15,MAP34 |
| `HFL16` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP23,MAP24,MAP28 |
| `HFLATF` | industrial | unreviewed | r=0.7, m=0.25 | 20 | MAP11,MAP20,MAP24 |
| `SPACEADT` | metal | unreviewed | r=0.35, m=0.75 | 20 | MAP34 |
| `CLOUDPRP` | industrial | unreviewed | r=0.7, m=0.25 | 19 | MAP11,MAP12,MAP14,MAP30,MAP34 |
| `H82` | industrial | unreviewed | r=0.7, m=0.25 | 19 | MAP13,MAP20,MAP23 |
| `HFL10` | industrial | unreviewed | r=0.7, m=0.25 | 19 | MAP24 |
| `SFLATDD` | floor | unreviewed | r=0.9, m=0.05 | 19 | MAP02,MAP05,MAP34 |
| `CASFL3` | industrial | unreviewed | r=0.7, m=0.25 | 18 | MAP13,MAP16 |
| `H1301` | industrial | unreviewed | r=0.7, m=0.25 | 18 | MAP24 |
| `HFLATJ2` | industrial | unreviewed | r=0.7, m=0.25 | 18 | MAP20,MAP34 |
| `VOIDSKY` | industrial | unreviewed | r=0.7, m=0.25 | 18 | MAP25,MAP26,MAP31 |
| `H123` | industrial | unreviewed | r=0.7, m=0.25 | 17 | MAP11,MAP34 |
| `HELLAJ` | industrial | unreviewed | r=0.7, m=0.25 | 17 | MAP11 |
| `VOIDSKYR` | industrial | unreviewed | r=0.7, m=0.25 | 17 | MAP34 |
| `DTWMD29` | industrial | unreviewed | r=0.7, m=0.25 | 16 | MAP34 |
| `HELLAM1` | industrial | unreviewed | r=0.7, m=0.25 | 16 | MAP34 |
| `C20F` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP34 |
| `C4011` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP22 |
| `C911F` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP34 |
| `CLOUDPNK` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP09,MAP15,MAP18,MAP19,MAP20 |
| `CMPSW13A` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP04,MAP29,MAP34 |
| `CMPSW23B` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP09,MAP12,MAP16,MAP18,MAP21,MAP34 |
| `CMPSW37A` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP16,MAP18,MAP21,MAP22,MAP31,MAP34 |
| `DTWMD30` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP34 |
| `H59` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP21,MAP34 |
| `H98` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP24,MAP34 |
| `SPORTB` | industrial | unreviewed | r=0.7, m=0.25 | 15 | MAP01,MAP02,MAP06,MAP29,MAP34 |
| `C307` | industrial | unreviewed | r=0.7, m=0.25 | 14 | MAP31,MAP32 |
| `C59` | industrial | unreviewed | r=0.7, m=0.25 | 14 | MAP21 |
| `C981` | industrial | unreviewed | r=0.7, m=0.25 | 14 | MAP18,MAP34 |
| `CDOR1` | industrial | unreviewed | r=0.7, m=0.25 | 14 | MAP15,MAP16 |
| `HDOR3` | industrial | unreviewed | r=0.7, m=0.25 | 14 | MAP14,MAP15,MAP34 |
| `HDOR9` | industrial | unreviewed | r=0.7, m=0.25 | 14 | MAP13,MAP20,MAP23,MAP34 |
| `SPACECP2` | metal | unreviewed | r=0.35, m=0.75 | 14 | MAP34 |
| `CASL19` | industrial | unreviewed | r=0.7, m=0.25 | 13 | MAP17,MAP34 |
| `CFACEA` | industrial | unreviewed | r=0.7, m=0.25 | 13 | MAP10,MAP12,MAP21,MAP31,MAP34 |
| `STRAKFL` | industrial | unreviewed | r=0.7, m=0.25 | 13 | MAP02,MAP25,MAP34 |
| `SWXSFA` | industrial | unreviewed | r=0.7, m=0.25 | 13 | MAP01,MAP03,MAP34 |
| `H66` | industrial | unreviewed | r=0.7, m=0.25 | 12 | MAP11,MAP17,MAP24 |
| `HFL17` | industrial | unreviewed | r=0.7, m=0.25 | 12 | MAP13,MAP23,MAP24,MAP30 |
| `OUTTEX09` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 12 | MAP34 |
| `SMONF` | industrial | unreviewed | r=0.7, m=0.25 | 12 | MAP06,MAP08,MAP34 |
| `AZTEC01` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP34 |
| `C55` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP16 |
| `CASF103` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP18,MAP22 |
| `DTWMD11` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP34 |
| `H12` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP24 |
| `H521` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP17,MAP34 |
| `HELLAL` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP21 |
| `HELLAQ` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP18,MAP30 |
| `SPACEAH1` | metal | unreviewed | r=0.35, m=0.75 | 11 | MAP06,MAP34 |
| `SWXSGA` | industrial | unreviewed | r=0.7, m=0.25 | 11 | MAP05,MAP08,MAP34 |
| `C101` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP16,MAP17,MAP18 |
| `C921F2` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP34 |
| `CMPSW01A` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP01,MAP34 |
| `CRATESM1` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP33 |
| `H122` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP23 |
| `H95T` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP20 |
| `OUTTEX10` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP34 |
| `OUTTEX53` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP34 |
| `OUTTEX56` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP34 |
| `SFLATAO` | floor | unreviewed | r=0.9, m=0.05 | 10 | MAP02,MAP08,MAP29,MAP34 |
| `SKEYFLBL` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP13,MAP15,MAP31,MAP34 |
| `SPORTA` | industrial | unreviewed | r=0.7, m=0.25 | 10 | MAP01,MAP05,MAP08 |
| `CASFL70` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP12 |
| `CDOR7` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP28,MAP34 |
| `CMPSW24A` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP10,MAP13,MAP18,MAP23 |
| `CMPSW34A` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP15 |
| `CMPSW54A` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP34 |
| `CMPSW56A` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP34 |
| `H37` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP20 |
| `H60` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP23,MAP34 |
| `HFLATI` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP11 |
| `OUTTEX01` | industrial | unreviewed | r=0.7, m=0.25 | 9 | MAP34 |
| `OUTTEX08` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 9 | MAP34 |
| `C10F` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP22 |
| `C500` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP34 |
| `C921F` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP22,MAP34 |
| `CMPSW12A` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP04,MAP34 |
| `CMPSW14A` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP04,MAP08,MAP34 |
| `CMPSW29B` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP12,MAP34 |
| `CMPSW31A` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP12,MAP34 |
| `CMPSW41A` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP20,MAP24 |
| `H100` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP15 |
| `H90` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP13,MAP20 |
| `HDOR4A` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP23 |
| `HLAVA1` | liquid | unreviewed | r=0.35, m=0.0, e=1.5 | 8 | MAP15,MAP20,MAP21,MAP34 |
| `OUTTEX25` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP34 |
| `SDFLTABG` | ceiling | unreviewed | r=0.8, m=0.15 | 8 | MAP34 |
| `SDOORGA` | door | unreviewed | r=0.45, m=0.65 | 8 | MAP01,MAP02,MAP04 |
| `SDOORGB` | door | unreviewed | r=0.45, m=0.65 | 8 | MAP01,MAP02,MAP04 |
| `SWXHCA` | industrial | unreviewed | r=0.7, m=0.25 | 8 | MAP20,MAP34 |
| `CMPSW11A` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP03,MAP34 |
| `CMPSW15A` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP06,MAP34 |
| `D64S1_01` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP12,MAP34 |
| `H68` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP23,MAP34 |
| `H92` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP13 |
| `HELLAP` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP12,MAP31 |
| `HFLATL` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP20 |
| `HFLATN` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP23,MAP34 |
| `SPACECCR` | metal | unreviewed | r=0.35, m=0.75 | 7 | MAP34 |
| `TITLEINV` | industrial | unreviewed | r=0.7, m=0.25 | 7 | MAP00,MAP34 |
| `CASFL55` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP15,MAP16 |
| `CASL13` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP23,MAP34 |
| `CMPSW08A` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP02,MAP34 |
| `CMPSW27A` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP12,MAP30,MAP34 |
| `CMPSW28B` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP12,MAP21,MAP23,MAP34 |
| `FACE1` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP34 |
| `H54` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP13 |
| `H64` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP23,MAP34 |
| `H771` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP24 |
| `H89` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP13 |
| `HDOR12B` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP24 |
| `OUTTEX04` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP34 |
| `SDOOR12` | door | unreviewed | r=0.45, m=0.65 | 6 | MAP34 |
| `SKEYFLYL` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP23,MAP31,MAP34 |
| `SPACEAT` | metal | unreviewed | r=0.35, m=0.75 | 6 | MAP34 |
| `SWXS4A` | industrial | unreviewed | r=0.7, m=0.25 | 6 | MAP20,MAP34 |
| `CMPSW18A` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP08,MAP34 |
| `CMPSW21A` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP08,MAP34 |
| `CMPSW26B` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP11 |
| `CMPSW53A` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP20,MAP24 |
| `D64L1_01` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP34 |
| `H128` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP23,MAP34 |
| `H58` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP21,MAP34 |
| `OUTTEX02` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 5 | MAP34 |
| `OUTTEX26` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP34 |
| `SKEYFLRD` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP21,MAP34 |
| `SWXSHA` | industrial | unreviewed | r=0.7, m=0.25 | 5 | MAP20,MAP28,MAP34 |
| `C403` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP12 |
| `C45CSTM` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP12 |
| `C58` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP31,MAP34 |
| `C81` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP14 |
| `C911F2` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP34 |
| `CASFL56` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP21,MAP34 |
| `CMPSW07A` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP02,MAP34 |
| `CMPSW33B` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP14,MAP30 |
| `CMPSW44A` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP20,MAP34 |
| `CMPSW46A` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP22,MAP34 |
| `CMPSW48A` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP24,MAP34 |
| `CMPSW52A` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP24,MAP34 |
| `HDOR2` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP20 |
| `HDOR6` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP31 |
| `HELLAR` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP29 |
| `HFLATG` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP11,MAP34 |
| `OUTTEX07` | industrial | unreviewed | r=0.7, m=0.25, e=0.8, bm | 4 | MAP34 |
| `OUTTEX35` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP34 |
| `OUTTEX46` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP34 |
| `OUTTEX54` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP34 |
| `SMONLB1` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP07,MAP34 |
| `SPACEBK1` | metal | unreviewed | r=0.35, m=0.75 | 4 | MAP07,MAP34 |
| `SPACECP` | metal | unreviewed | r=0.35, m=0.75 | 4 | MAP29 |
| `SPACECQ` | metal | unreviewed | r=0.35, m=0.75 | 4 | MAP29 |
| `SWXNS01` | industrial | unreviewed | r=0.7, m=0.25 | 4 | MAP34 |
| `CASF107` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP15 |
| `CLOUDRED` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP34 |
| `CMPSW05A` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP02,MAP34 |
| `CMPSW09A` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP02,MAP34 |
| `CMPSW16A` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP34 |
| `CMPSW25A` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP10,MAP34 |
| `CMPSW32B` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP13,MAP34 |
| `CMPSW40A` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP18 |
| `CMPSW42A` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP20 |
| `DTWMD03` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP34 |
| `HELLAH1` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP34 |
| `HFL20` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP24 |
| `OUTTEX06` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP34 |
| `OUTTEX51` | industrial | unreviewed | r=0.7, m=0.25 | 3 | MAP34 |
| `SPACECF1` | metal | unreviewed | r=0.35, m=0.75 | 3 | MAP33 |
| `CASF201` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP15 |
| `CASF50` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP18 |
| `CASF70` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP22 |
| `CDOR2BB` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP15 |
| `CDOR6` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP12 |
| `CMPSW02A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP01,MAP07 |
| `CMPSW06A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP02,MAP08 |
| `CMPSW16B` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP07 |
| `CMPSW35A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP15,MAP20 |
| `CMPSW36A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP16 |
| `CMPSW43A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP20 |
| `CMPSW47B` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP24 |
| `CMPSW55A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `CMPSW62A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `D64LOGO` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP20 |
| `HDOR4` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP23 |
| `HTELD` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `OUTSW01A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `OUTSW03A` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `OUTTEX11` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `OUTTEX36` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `SDOOR10` | door | unreviewed | r=0.45, m=0.65 | 2 | MAP01 |
| `SDOORFB` | door | unreviewed | r=0.45, m=0.65 | 2 | MAP04 |
| `SWXS4B` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `TSFCMONS` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `TSFCNM00` | industrial | unreviewed | r=0.7, m=0.25 | 2 | MAP34 |
| `C37CSTM` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP30 |
| `CASFL98` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP13 |
| `CMPSW03A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP32 |
| `CMPSW17A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP07 |
| `CMPSW19A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP08 |
| `CMPSW30A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP13 |
| `CMPSW38A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP16 |
| `CMPSW39A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP16 |
| `CMPSW45B` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP22 |
| `CMPSW49A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP22 |
| `CMPSW51A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP22 |
| `CMPSW58A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `CMPSW59A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `CRATESM2` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `CREDTEX1` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP20 |
| `CREDTEX2` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP20 |
| `CREDTEX3` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP20 |
| `D64BLOD1` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64BLOD2` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64LAVA1` | liquid | unreviewed | r=0.35, m=0.0, e=1.5 | 1 | MAP34 |
| `D64LAVA2` | liquid | unreviewed | r=0.35, m=0.0, e=1.5 | 1 | MAP34 |
| `D64NUKG1` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64NUKG2` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64S2_01` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64SLDG1` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64SLDG2` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64WATR1` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `D64WATR2` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `DTWMD31` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `FRSKYRED` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `GTEL1` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `H36YGLOW` | tech | unreviewed | r=0.4, m=0.55, e=0.6 | 1 | MAP20 |
| `H49RGLOW` | tech | unreviewed | r=0.4, m=0.55, e=0.6 | 1 | MAP20 |
| `HDOR11B` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP21 |
| `OUTSW02A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `OUTTEX12` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `OUTTEX14` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `OUTTEX22` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `OUTTEX38` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `OUTTEX47` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `SPACEAMT` | metal | unreviewed | r=0.35, m=0.75 | 1 | MAP34 |
| `SPACECN2` | metal | unreviewed | r=0.35, m=0.75 | 1 | MAP06 |
| `SWXAZ1A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |
| `SWXAZ2A` | industrial | unreviewed | r=0.7, m=0.25 | 1 | MAP34 |

## Workflow

1. Launch gallery (`tools/launch-texture-gallery-rt.cmd`).
2. Walk the grid; mark rows in this file `auto` → `tuned` → `done`.
3. For tuned textures: edit scene `textures.json` and/or `rt/mat/<TEX>_*.png`.
4. Re-run `build_texture_gallery.py` to refresh inventory; **statuses/notes are preserved**.

