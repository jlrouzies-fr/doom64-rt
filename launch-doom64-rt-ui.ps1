#requires -version 5
<#
    Doom 64 - Ray Traced : startup check.

    Runs every launch. It lists what the game needs, ticks off what it found and
    explains what it did not, because the alternative -- a console line that
    flashes past on a double-click -- is how a first-time user concludes the
    download is broken when they are simply missing the game files we are not
    allowed to ship.

    Exit 0 = launch, with the chosen IWAD written to the settings file.
    Exit 1 = the user closed the window.
#>
param(
    [string] $Proj      = "",
    [string] $EngineDir = "",
    [string] $ModsDir   = "",
    [string] $GameDir   = "",
    [string] $IwadHint  = "",
    [string] $Settings  = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$BG    = [System.Drawing.Color]::FromArgb(10, 9, 9)
$PANEL = [System.Drawing.Color]::FromArgb(20, 18, 18)
$BLOOD = [System.Drawing.Color]::FromArgb(200, 80, 30)
$RED   = [System.Drawing.Color]::FromArgb(224, 59, 30)
$GREEN = [System.Drawing.Color]::FromArgb(122, 176, 91)
$AMBER = [System.Drawing.Color]::FromArgb(206, 160, 60)
$BONE  = [System.Drawing.Color]::FromArgb(201, 201, 201)
$DIM   = [System.Drawing.Color]::FromArgb(130, 125, 122)

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

    $c += @{ Key='retribution'; Name='Doom 64: Retribution v1.5'; Req=$true
             Ok=(Test-Path "$GameDir\D64RTR_v15.WAD")
             Good="D64RTR_v15.WAD"
             Bad="Free, from the mod's own ModDB page. Put D64RTR_v15.WAD in the game folder."
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
#  Window
# ---------------------------------------------------------------------------
$form                 = New-Object System.Windows.Forms.Form
$form.Text            = 'Doom 64 - Ray Traced'
$form.BackColor       = $BG
$form.ForeColor       = $BONE
$form.StartPosition   = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox     = $false
$form.MinimizeBox     = $false
$form.Font            = New-Object System.Drawing.Font('Segoe UI', 9)
$form.ClientSize      = New-Object System.Drawing.Size(720, 700)
# Positions below are pixels. Without this WinForms rescales them by display DPI
# after Show() while our computed height stays put, and the bottom row falls off.
$form.AutoScaleMode   = [System.Windows.Forms.AutoScaleMode]::None

# --- logo, centred ----------------------------------------------------------
$logoPath = @("$Proj\launcher-banner.png", "$Proj\docs\img\doom64rt-banner.png") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
$logoH = 0
if ($logoPath) {
    $pic          = New-Object System.Windows.Forms.PictureBox
    $pic.Image    = [System.Drawing.Image]::FromFile($logoPath)
    $pic.SizeMode = 'Zoom'
    $pic.Size     = New-Object System.Drawing.Size(330, 245)
    $pic.Location = New-Object System.Drawing.Point(((720 - 330) / 2), 10)
    $pic.BackColor = $BG
    $form.Controls.Add($pic)
    $logoH = 246
} else {
    $t           = New-Object System.Windows.Forms.Label
    $t.Text      = 'DOOM 64'
    $t.Font      = New-Object System.Drawing.Font('Impact', 40)
    $t.ForeColor = $BLOOD
    $t.AutoSize  = $true
    $t.Location  = New-Object System.Drawing.Point(270, 18)
    $form.Controls.Add($t)
    $logoH = 96
}

$rule           = New-Object System.Windows.Forms.Label
$rule.BackColor = $BLOOD
$rule.Size      = New-Object System.Drawing.Size(664, 2)
$rule.Location  = New-Object System.Drawing.Point(28, ($logoH + 6))
$form.Controls.Add($rule)

$head           = New-Object System.Windows.Forms.Label
$head.Text      = 'STARTUP CHECK'
$head.Font      = New-Object System.Drawing.Font('Consolas', 11, [System.Drawing.FontStyle]::Bold)
$head.ForeColor = $DIM
$head.AutoSize  = $true
$head.Location  = New-Object System.Drawing.Point(28, ($logoH + 16))
$form.Controls.Add($head)

$listTop = $logoH + 42
# Tall enough for two lines of detail plus a store link under the name; a shorter
# row clipped the ModDB links against the next panel.
$rowH    = 56

$rows = @()          # rebuilt on every re-check
$script:AllOk = $false

function Clear-Rows {
    foreach ($r in $script:rows) { $form.Controls.Remove($r); $r.Dispose() }
    $script:rows = @()
}

function Draw-Checks {
    Clear-Rows

    # Text typed or browsed into the box is a deliberate choice, so it counts as
    # confirmation. Text we auto-filled ourselves does not.
    $typed = $iwadBox.Text
    $script:TypedBad = ""
    if ($typed -and $typed -ne $script:LastAuto) {
        if (Test-Path $typed) {
            $script:Confirmed += (Resolve-Path $typed).Path
        } else {
            # Otherwise we silently fall back to auto-detection and the box text
            # changes under the user, which reads as "it ignored what I typed".
            $script:TypedBad = $typed
        }
    }

    $info = Find-Iwad -Hint $typed
    $script:IwadPath   = if ($info) { $info.Path }   else { "" }
    $script:IwadSource = if ($info) { $info.Source } else { "" }
    if ($script:IwadPath) {
        $iwadBox.Text     = $script:IwadPath
        $script:LastAuto  = $script:IwadPath
    }

    $checks = Get-Checks
    $y = $listTop
    $missing = 0

    foreach ($c in $checks) {
        $p           = New-Object System.Windows.Forms.Panel
        $p.BackColor = $PANEL
        $p.Size      = New-Object System.Drawing.Size(664, ($rowH - 6))
        $p.Location  = New-Object System.Drawing.Point(28, $y)

        $mark           = New-Object System.Windows.Forms.Label
        $mark.Text      = if ($c.Ok) { [char]0x2713 } else { if ($c.Req) { [char]0x2715 } else { '!' } }
        $mark.Font      = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
        $mark.ForeColor = if ($c.Ok) { $GREEN } else { if ($c.Req) { $RED } else { $AMBER } }
        $mark.AutoSize  = $true
        $mark.Location  = New-Object System.Drawing.Point(12, 8)
        $p.Controls.Add($mark)

        $n           = New-Object System.Windows.Forms.Label
        $n.Text      = $c.Name
        $n.Font      = New-Object System.Drawing.Font('Consolas', 10, [System.Drawing.FontStyle]::Bold)
        $n.ForeColor = if ($c.Ok) { $BONE } else { $BLOOD }
        $n.Size      = New-Object System.Drawing.Size(230, 18)
        $n.Location  = New-Object System.Drawing.Point(46, 11)
        $p.Controls.Add($n)

        $d           = New-Object System.Windows.Forms.Label
        $d.Text      = if ($c.Ok) { $c.Good } else { $c.Bad }
        $d.ForeColor = if ($c.Ok) { $DIM } else { $BONE }
        $d.Size      = New-Object System.Drawing.Size(370, 42)
        $d.Location  = New-Object System.Drawing.Point(286, 5)
        $p.Controls.Add($d)

        if ($c.Confirm) {
            $use           = New-Object System.Windows.Forms.Button
            $use.Text      = 'Use this copy'
            $use.FlatStyle = 'Flat'
            $use.BackColor = $PANEL
            $use.ForeColor = $AMBER
            $use.Size      = New-Object System.Drawing.Size(104, 24)
            $use.Location  = New-Object System.Drawing.Point(160, 13)
            $use.Add_Click({
                if ($script:IwadPath) { $script:Confirmed += $script:IwadPath }
                Draw-Checks
            })
            $p.Controls.Add($use)
        }

        if (-not $c.Ok -and $c.Link) {
            $lnk                 = New-Object System.Windows.Forms.LinkLabel
            $lnk.Text            = $c.LinkText
            $lnk.LinkColor       = $BLOOD
            $lnk.ActiveLinkColor = $RED
            $lnk.AutoSize        = $true
            $lnk.Location        = New-Object System.Drawing.Point(46, 30)
            $u = $c.Link
            $lnk.Add_LinkClicked({ Start-Process $u }.GetNewClosure())
            $p.Controls.Add($lnk)
        }

        $form.Controls.Add($p)
        $p.BringToFront()
        $script:rows += $p
        $y += $rowH
        if ($c.Req -and -not $c.Ok) { $missing++ }
    }

    $script:AllOk = ($missing -eq 0)
    $launch.Enabled = $script:AllOk
    if ($script:TypedBad) {
        $status.Text      = "No file at that path - check it and press Re-check."
        $status.ForeColor = $AMBER
    } elseif ($script:AllOk) {
        $status.Text      = "All checks passed  -  upscaler: $(Get-Upscaler)"
        $status.ForeColor = $GREEN
    } else {
        $status.Text      = "$missing item(s) still needed. Fix them, then Re-check."
        $status.ForeColor = $RED
    }
}

# --- IWAD row: type it, or browse for it -----------------------------------
$iwadLbl           = New-Object System.Windows.Forms.Label
$iwadLbl.Text      = 'doom2.wad'
$iwadLbl.Font      = New-Object System.Drawing.Font('Consolas', 9)
$iwadLbl.ForeColor = $DIM
$iwadLbl.AutoSize  = $true
$iwadLbl.Location  = New-Object System.Drawing.Point(28, ($listTop + 8 * $rowH + 8))
$form.Controls.Add($iwadLbl)

$iwadBox             = New-Object System.Windows.Forms.TextBox
$iwadBox.BackColor   = $PANEL
$iwadBox.ForeColor   = $BONE
$iwadBox.BorderStyle = 'FixedSingle'
$iwadBox.Size        = New-Object System.Drawing.Size(430, 22)
$iwadBox.Location    = New-Object System.Drawing.Point(100, ($listTop + 8 * $rowH + 5))
$iwadBox.Text        = $IwadHint
$form.Controls.Add($iwadBox)

function New-Btn([string]$text, [int]$x, [int]$y, [int]$w, $fg) {
    $b           = New-Object System.Windows.Forms.Button
    $b.Text      = $text
    $b.FlatStyle = 'Flat'
    $b.BackColor = $PANEL
    $b.ForeColor = $fg
    $b.Size      = New-Object System.Drawing.Size($w, 26)
    $b.Location  = New-Object System.Drawing.Point($x, $y)
    return $b
}

$browse = New-Btn 'Browse...' 540 ($listTop + 8 * $rowH + 3) 70 $BONE
$browse.Add_Click({
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Filter = 'DOOM II IWAD (doom2.wad)|doom2.wad|All WADs (*.wad)|*.wad'
    $dlg.Title  = 'Where is your doom2.wad?'
    if ($dlg.ShowDialog() -eq 'OK') {
        $script:Confirmed += (Resolve-Path $dlg.FileName).Path
        $iwadBox.Text = $dlg.FileName
        Draw-Checks
    }
})
$form.Controls.Add($browse)

$recheck = New-Btn 'Re-check' 616 ($listTop + 8 * $rowH + 3) 76 $BLOOD
$recheck.Add_Click({ Draw-Checks })
$form.Controls.Add($recheck)

# --- status + actions -------------------------------------------------------
$status           = New-Object System.Windows.Forms.Label
$status.Font      = New-Object System.Drawing.Font('Consolas', 9)
$status.Size      = New-Object System.Drawing.Size(430, 20)
$status.Location  = New-Object System.Drawing.Point(28, ($listTop + 8 * $rowH + 44))
$form.Controls.Add($status)

$openDir = New-Btn 'Open game folder' 28 ($listTop + 8 * $rowH + 72) 140 $BONE
$openDir.Add_Click({ if (Test-Path $GameDir) { Start-Process explorer.exe $GameDir } else { New-Item -ItemType Directory -Path $GameDir -Force | Out-Null; Start-Process explorer.exe $GameDir } })
$form.Controls.Add($openDir)

$quit = New-Btn 'Quit' 470 ($listTop + 8 * $rowH + 70) 90 $DIM
$quit.Add_Click({ $form.Tag = 'quit'; $form.Close() })
$form.Controls.Add($quit)

$launch = New-Btn 'RIP AND TEAR' 570 ($listTop + 8 * $rowH + 66) 122 $BLOOD
$launch.Font = New-Object System.Drawing.Font('Consolas', 10, [System.Drawing.FontStyle]::Bold)
$launch.Size = New-Object System.Drawing.Size(122, 34)
$launch.Add_Click({
    if ($script:IwadPath) { Set-Content -Path $Settings -Value "iwad=$($script:IwadPath)" -Encoding ASCII }
    $form.Tag = 'launch'
    $form.Close()
})
$form.Controls.Add($launch)

$form.ClientSize = New-Object System.Drawing.Size(720, ($listTop + 8 * $rowH + 116))

Draw-Checks
[void]$form.ShowDialog()

if ($form.Tag -eq 'launch') { exit 0 } else { exit 1 }
