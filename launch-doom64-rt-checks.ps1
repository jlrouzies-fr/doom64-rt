<#
    Doom 64 - Ray Traced : what the startup check knows.

    Finding the files, ranking the doom2.wads, writing the answer back out.
    Everything here is presentation-free on purpose: the launcher windows
    (classic, winforms, wpf) dot-source this file, so the only difference
    between them is how they draw, never what they find.

    Dot-sourced, so it runs in the caller's scope and reads the caller's
    $Proj / $EngineDir / $GameDir / $IwadHint / $Settings parameters directly.
#>

# ---------------------------------------------------------------------------
#  Finding a DOOM II IWAD
#
#  Hardcoded Program Files paths miss every non-default Steam library, which is
#  most of them once a second drive exists. So: ask the registry where Steam is,
#  read its library list, and walk those.
# ---------------------------------------------------------------------------
function Get-SteamRoots {
    $roots = @()
    foreach ($k in @('HKCU:\Software\Valve\Steam',
                     'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam',
                     'HKLM:\SOFTWARE\Valve\Steam')) {
        try {
            $p = Get-ItemProperty -Path $k -ErrorAction Stop
            foreach ($v in @($p.SteamPath, $p.InstallPath)) {
                if ($v -and (Test-Path $v)) { $roots += (Resolve-Path $v).Path }
            }
        } catch { }
    }
    # every library folder Steam knows about, not just the install drive
    $libs = @($roots)
    foreach ($r in $roots) {
        foreach ($vdf in @("$r\steamapps\libraryfolders.vdf", "$r\config\libraryfolders.vdf")) {
            if (Test-Path $vdf) {
                foreach ($m in ([regex]'(?m)"path"\s+"([^"]+)"').Matches((Get-Content $vdf -Raw))) {
                    $lib = $m.Groups[1].Value -replace '\\\\', '\'
                    if (Test-Path $lib) { $libs += $lib }
                }
            }
        }
    }
    $libs | Select-Object -Unique
}

function Get-GogRoots {
    $out = @()
    foreach ($k in @('HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games',
                     'HKLM:\SOFTWARE\GOG.com\Games')) {
        try {
            foreach ($g in Get-ChildItem $k -ErrorAction Stop) {
                $p = (Get-ItemProperty $g.PSPath -ErrorAction SilentlyContinue).path
                if ($p -and (Test-Path $p)) { $out += $p }
            }
        } catch { }
    }
    $out
}

# A doom2.wad found inside a Steam or GOG install is one the user demonstrably
# owns. A doom2.wad lying in the game folder, next to the package or in Documents
# is just a file of the right name -- it gets shown, never auto-accepted, and the
# user has to confirm it. Confirmed choices are remembered in the settings file.
function Find-Iwad {
    param([string] $Hint)

    $ranked = @()   # ordered: confirmed, steam, gog, unverified

    foreach ($h in @($Hint, $env:D64RT_IWAD)) {
        if ($h -and (Test-Path $h) -and $script:Confirmed -contains (Resolve-Path $h).Path) {
            $ranked += @{ Path = (Resolve-Path $h).Path; Source = 'user' }
        }
    }

    $steam = @()
    $gog   = @()
    $other = @()

    foreach ($lib in Get-SteamRoots) {
        $common = Join-Path $lib 'steamapps\common'
        if (-not (Test-Path $common)) { continue }
        # the 1994 release, the 2024 re-release and the Master Levels all differ
        foreach ($sub in @('Doom 2\base', 'Doom 2\masterbase', 'Doom 2\finaldoombase',
                           'DOOM 2\base', 'Ultimate Doom\base',
                           'DOOM 3 BFG Edition\base\wads')) {
            $steam += (Join-Path $common "$sub\doom2.wad")
        }
        # 2024 "DOOM + DOOM II" puts it under a rerelease folder that keeps moving
        try {
            $steam += (Get-ChildItem $common -Filter 'doom2.wad' -Recurse -Depth 3 -File -ErrorAction SilentlyContinue |
                       Select-Object -First 4 -Expand FullName)
        } catch { }
    }
    foreach ($g in Get-GogRoots) {
        try {
            $gog += (Get-ChildItem $g -Filter 'doom2.wad' -Recurse -Depth 2 -File -ErrorAction SilentlyContinue |
                     Select-Object -First 2 -Expand FullName)
        } catch { }
    }

    # Everything below this line is a file of the right name in a plausible place.
    # It is offered, not trusted.
    $other += "$GameDir\doom2.wad"
    $other += "$Proj\doom2.wad"
    $other += "$env:USERPROFILE\Documents\GZDoom\doom2.wad"
    foreach ($h in @($Hint, $env:D64RT_IWAD)) { if ($h) { $other += $h } }

    # Several doom2.wads on one machine are not interchangeable: the Steam DOOM II
    # is 14,604,584 bytes, other bundles ship variants that load but differ. Within
    # a source, prefer the known-good size.
    function Rank([string[]] $paths, [string] $src) {
        $ok = @()
        foreach ($p in $paths) { if ($p -and (Test-Path $p)) { $ok += (Resolve-Path $p).Path } }
        $ok = $ok | Select-Object -Unique
        $good = @($ok | Where-Object { (Get-Item $_).Length -eq 14604584 })
        $rest = @($ok | Where-Object { (Get-Item $_).Length -ne 14604584 })
        # parenthesised on purpose: `$good + $rest | ForEach` binds the pipeline to
        # $rest alone and returns a mix of strings and hashtables.
        $sorted = @($good) + @($rest)
        return @($sorted | ForEach-Object { @{ Path = $_; Source = $src } })
    }

    $ranked += Rank $steam 'steam'
    $ranked += Rank $gog   'gog'
    $ranked += Rank $other 'other'

    # a path the user already confirmed outranks everything
    $conf = $ranked | Where-Object { $script:Confirmed -contains $_.Path } | Select-Object -First 1
    if ($conf) { return @{ Path = $conf.Path; Source = 'user' } }
    if ($ranked.Count) { return $ranked[0] }
    return $null
}

# ---------------------------------------------------------------------------
#  The checks themselves
# ---------------------------------------------------------------------------
$script:IwadPath   = ""
$script:IwadSource = ""
$script:LastAuto   = ""
# Paths the user has vouched for: whatever the settings file or D64RT_IWAD already
# held (they put it there), plus anything they browse to or type this session.
$script:Confirmed  = @()
foreach ($h in @($IwadHint, $env:D64RT_IWAD)) {
    if ($h -and (Test-Path $h)) { $script:Confirmed += (Resolve-Path $h).Path }
}

function Get-Checks {
    $c = @()

    $c += @{ Key='engine'; Name='Ray-traced engine';  Req=$true
             Ok=(Test-Path "$EngineDir\gzdoom.exe")
             Good="gzdoom.exe"
             Bad="Missing from this package - re-extract the download, keeping the folders intact."
             Link=$null }

    $c += @{ Key='rtgl'; Name='RTGL1 path tracer'; Req=$true
             Ok=(Test-Path "$EngineDir\rt\bin\RTGL1.dll")
             Good="rt\bin\RTGL1.dll"
             Bad="Missing from this package - re-extract the download, keeping the folders intact."
             Link=$null }

    # A stock 30 KB textures.json instead of our ~236 KB one means every world
    # emissive falls back to defaults: lamps read as overbright and nothing warns.
    $meta = "$EngineDir\rt\data\textures.json"
    $metaOk = (Test-Path $meta) -and ((Get-Item $meta).Length -gt 100000)
    $c += @{ Key='mats'; Name='RT materials'; Req=$true
             Ok=$metaOk
             Good=("textures.json, {0:N0} KB" -f (&{ if (Test-Path $meta) { (Get-Item $meta).Length/1KB } else { 0 } }))
             Bad="The authored material metadata is missing or is the stock file. Re-extract the download."
             Link=$null }

    $iwadOk     = $false
    $iwadDetail = "Retribution is a PWAD - it needs a DOOM II you own. Buy it on Steam or GOG, or point at your copy below."
    if ($script:IwadPath) {
        $len   = (Get-Item $script:IwadPath).Length
        $parts = $script:IwadPath -split '\\'
        $short = if ($parts.Count -gt 3) { '...\' + ($parts[-3..-1] -join '\') } else { $script:IwadPath }
        $size  = if ($len -eq 14604584) { "{0:N0} bytes" -f $len }
                 else { "{0:N0} bytes - unusual size" -f $len }

        switch ($script:IwadSource) {
            'steam' { $iwadOk = $true;  $iwadDetail = "{0}`r`n{1}  (Steam install)" -f $short, $size }
            'gog'   { $iwadOk = $true;  $iwadDetail = "{0}`r`n{1}  (GOG install)"   -f $short, $size }
            'user'  { $iwadOk = $true;  $iwadDetail = "{0}`r`n{1}  (confirmed)"     -f $short, $size }
            default { $iwadOk = $false
                      $iwadDetail = "Found a doom2.wad outside any Steam or GOG install:`r`n{0}  ({1}). Confirm it is your own copy." -f $short, $size }
        }
    }
    $c += @{ Key='iwad'; Name='DOOM II IWAD'; Req=$true
             Ok=$iwadOk
             Good=$iwadDetail
             Bad=$iwadDetail
             Link=(&{ if ($script:IwadPath) { $null } else { 'https://store.steampowered.com/app/2300/DOOM_II/' } })
             LinkText='DOOM II on Steam'
             Confirm=($script:IwadPath -and -not $iwadOk) }

    # The ModDB download is named D64RTR[v1.5].WAD. Two consequences: accept that
    # name as well as the shell-safe D64RTR_v15.WAD, and use -LiteralPath -- to
    # Test-Path, "[v1.5]" is a character-class wildcard, so the plain form reports
    # the file missing while it is sitting right there.
    $script:RetroWad = @("$GameDir\D64RTR[v1.5].WAD", "$GameDir\D64RTR_v15.WAD") |
                       Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    $c += @{ Key='retribution'; Name='Doom 64: Retribution v1.5'; Req=$true
             Ok=[bool]$script:RetroWad
             Good=(&{ if ($script:RetroWad) { Split-Path -Leaf $script:RetroWad } })
             Bad="Free, from the mod's own ModDB page. Extract the whole download into the game folder - D64RTR[v1.5].WAD, the brightmaps and the soundfont are all needed."
             Link='https://www.moddb.com/mods/doom-64-retribution'; LinkText='Retribution on ModDB' }

    $c += @{ Key='brightmaps'; Name='Retribution brightmaps'; Req=$true
             Ok=(Test-Path "$GameDir\D64RTR_BRIGHTMAPS.PK3")
             Good="D64RTR_BRIGHTMAPS.PK3"
             Bad="Ships in the same Retribution download. Every enemy eye and glowing panel is masked from it."
             Link='https://www.moddb.com/mods/doom-64-retribution'; LinkText='Retribution on ModDB' }

    $c += @{ Key='music'; Name='OGG music pack v1.3'; Req=$true
             Ok=(Test-Path "$GameDir\D64MUS.PK3")
             Good="D64MUS.PK3"
             Bad="Aubrey Hodges' soundtrack. Download D64MUS.ZIP and unzip it into the game folder."
             Link='https://www.moddb.com/mods/doom-64-retribution/addons/doom-64-retribution-ogg-music-pack-v13'; LinkText='OGG music pack on ModDB' }

    # Not required: only the handful of MIDI tracks need it.
    $c += @{ Key='soundfont'; Name='Soundfont (optional)'; Req=$false
             Ok=(Test-Path "$GameDir\DOOMSND.SF2")
             Good="DOOMSND.SF2"
             Bad="Without it the few MIDI tracks (title screen, MAP00) stay silent. Ships with Retribution."
             Link=$null }

    # Nothing is wrong when this one is absent, so it gets Opt: a dim "+" and a
    # link, not the amber "!" that means "you are missing something". The row is
    # the only place an add-on we do not ship can announce that it exists.
    $script:RecolorWad = @('D64ClassicRecolored.wad', 'D64ClassicRecolored_OffsetFix.wad') |
                         ForEach-Object { Join-Path $Proj "Addons\$_" } |
                         Where-Object { Test-Path $_ } | Select-Object -First 1
    $c += @{ Key='recolor'; Name='Classic recolour (add-on)'; Req=$false; Opt=$true
             Ok=[bool]$script:RecolorWad
             Good=(&{ if ($script:RecolorWad) { Split-Path -Leaf $script:RecolorWad } })
             Bad="Optional recolour of the Cacodemon and Pain Elemental in classic Doom hues. Put the wad in the Addons folder beside the launcher, then press Re-check."
             Toggle='Play with the recoloured Cacodemon / Pain Elemental'
             Link='https://www.moddb.com/games/doom-64/addons/d64classicrecolored'; LinkText='D64ClassicRecolored on ModDB' }

    # SHIPPED WITH THE PACKAGE, unlike the recolour above -- but still Opt, because
    # the game is complete without it and a missing pk3 must not block a launch.
    # The detail text has to say REPLACES: these monsters are not added on top of
    # the roster, they take the place of ones already in the map, and a player who
    # does not know that will read a converted Baron as a missing Baron.
    $script:UeMonWad = @("$ModsDir\d64r-ue-monsters.pk3") |
                       Where-Object { Test-Path $_ } | Select-Object -First 1
    $c += @{ Key='uemonsters'; Name='Unseen Evil monsters'; Req=$false; Opt=$true
             Ok=[bool]$script:UeMonWad
             Good=("Chaingunner, Revenant, Arch-Vile and Spider Mastermind, drawn in the Doom 64 style by DrPyspy. " +
                   "They REPLACE monsters already placed in each map rather than adding to it, so the kill count " +
                   "is unchanged. Which ones is fixed per map, not re-rolled each playthrough, and it unlocks as " +
                   "you go: Chaingunners from MAP05, Revenants from MAP10, one Arch-Vile on a few late maps, one " +
                   "Mastermind on MAP22. Untick to play the stock Retribution roster.")
             Bad=("Not in the public download, and not by mistake: the sprites are DrPyspy's and " +
                  "Doom 64: Unseen Evil ships no licence statement, so this project credits them " +
                  "rather than redistributing them. Build the pk3 yourself with " +
                  "tools\pack_ue_monsters.py from a copy of D64UnseenEvil-v1.0.3.pk3 and drop it " +
                  "in the mods folder.")
             Toggle='Play with the Unseen Evil monsters'
             Link='https://www.moddb.com/mods/doom-64-unseen-evil'; LinkText='Doom 64: Unseen Evil on ModDB' }

    return $c
}

function Get-Upscaler {
    if ($env:D64RT_UPSCALER) { return $env:D64RT_UPSCALER.ToLower() }
    try {
        if (((Get-CimInstance Win32_VideoController).Name -join ' ') -match 'NVIDIA') { return 'dlss' }
    } catch { }
    return 'fsr'
}

# ---------------------------------------------------------------------------
#  "Do not ask me again"
#
#  The marker is a file whose EXISTENCE is the flag -- the launcher is a .cmd and
#  `if exist` is the one test it can make without help. The contents are for the
#  human who finds the file and wonders what it is.
#
#  It is not a promise that the files are still there: the launcher re-checks the
#  required ones on every start and opens this window again if any went missing.
# ---------------------------------------------------------------------------
function Get-ConfigDonePath {
    $root = if ($Proj) { $Proj } else { $PSScriptRoot }
    Join-Path $root 'configdone.txt'
}

function Test-ConfigDone { Test-Path (Get-ConfigDonePath) }

#  Windows PowerShell's `-Encoding UTF8` means UTF-8 *with* a BOM, and the reader
#  is a .cmd: `for /f` hands those three bytes to the caller as part of the first
#  key, so `iwad=` came back as `<BOM>iwad` and never matched. The launcher then
#  had no IWAD, reported doom2.wad missing, and reopened this window on every
#  start -- ticked box, green checklist and all. Write plain UTF-8, no BOM.
function Write-TextNoBom {
    param([string] $Path, [string[]] $Lines)
    $full = [System.IO.Path]::GetFullPath($Path)
    $enc  = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($full, (($Lines -join "`r`n") + "`r`n"), $enc)
}

function Save-Launch {
    # $UeMonsters defaults to $true so the WinForms fallback, which does not pass
    # it, cannot silently switch the monsters off.
    param([bool] $Recolor, [bool] $SkipNextTime, [bool] $UeMonsters = $true)

    $lines = @()
    if ($script:IwadPath) { $lines += "iwad=$($script:IwadPath)" }
    # Which Retribution filename was found, so the launcher does not have to
    # guess between D64RTR[v1.5].WAD and D64RTR_v15.WAD a second time.
    if ($script:RetroWad) { $lines += "mod=$($script:RetroWad)" }
    # Always written, both ways: the launcher reads this file into RECOLOR, so
    # an unticked box has to be able to turn a previous 1 back off.
    $lines += "recolor=$([int]$Recolor)"
    # Always written, both ways, same as recolor -- an unticked box has to be able
    # to turn a previous 1 back off. Note the launcher treats an ABSENT key as ON:
    # this shipped always-loaded, and a settings file written before this row
    # existed must not read as "the user turned it off".
    $lines += "uemonsters=$([int]$UeMonsters)"
    if ($Settings -and $lines) { Write-TextNoBom $Settings $lines }

    $done = Get-ConfigDonePath
    if ($SkipNextTime) {
        Write-TextNoBom $done @(
          "Doom 64 - Ray Traced : setup confirmed, startup window disabled.",
          "",
          "Delete this file to get the startup window back, or run",
          "    launch-doom64-rt.cmd setup",
          "which shows it once without deleting anything.",
          "",
          "The launcher still checks the required files on every start, and shows",
          "the window anyway if one of them has gone missing.",
          "",
          "iwad = $($script:IwadPath)",
          "mod  = $($script:RetroWad)")
    } elseif (Test-Path $done) {
        Remove-Item $done -Force -ErrorAction SilentlyContinue
    }
}
