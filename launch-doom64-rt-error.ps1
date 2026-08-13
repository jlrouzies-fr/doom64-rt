#requires -version 5
<#
    The window Doom 64 - Ray Traced shows when it cannot start.

    Called by launch-doom64-rt.cmd with a semicolon-separated list of missing
    pieces. It exists because the alternative -- a console line that flashes past
    on a double-click -- is how a first-time user concludes the download is
    broken when they are simply missing the game files we are not allowed to ship.
#>
param(
    [string] $Missing = "",
    [string] $GameDir = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$BG      = [System.Drawing.Color]::FromArgb(10, 9, 9)
$PANEL   = [System.Drawing.Color]::FromArgb(20, 18, 18)
$BLOOD   = [System.Drawing.Color]::FromArgb(200, 80, 30)
$RED     = [System.Drawing.Color]::FromArgb(224, 59, 30)
$BONE    = [System.Drawing.Color]::FromArgb(201, 201, 201)
$DIM     = [System.Drawing.Color]::FromArgb(130, 125, 122)

$items = @{
    'iwad' = @{
        Title = 'DOOM II IWAD  (doom2.wad)'
        Body  = "Retribution is a PWAD -- it needs a DOOM II you own. Buy it on Steam or GOG and drop doom2.wad in the game folder, or set D64RT_IWAD to its path. Freedoom Phase 2 works as a free stand-in (untested here)."
        Link  = 'https://store.steampowered.com/app/2300/DOOM_II/'
        LinkText = 'DOOM II on Steam'
    }
    'retribution' = @{
        Title = 'Doom 64: Retribution v1.5  (D64RTR_v15.WAD)'
        Body  = "The total conversion this project renders. Free, from the mod's own ModDB page."
        Link  = 'https://www.moddb.com/mods/doom-64-retribution'
        LinkText = 'Retribution on ModDB'
    }
    'brightmaps' = @{
        Title = 'Retribution brightmaps  (D64RTR_BRIGHTMAPS.PK3)'
        Body  = "Ships in the same Retribution download. Every enemy eye and glowing panel is masked from it."
        Link  = 'https://www.moddb.com/mods/doom-64-retribution'
        LinkText = 'Retribution on ModDB'
    }
    'music' = @{
        Title = 'OGG music pack v1.3  (D64MUS.PK3)'
        Body  = "Aubrey Hodges' soundtrack, recorded to OGG. Download D64MUS.ZIP and unzip it into the game folder."
        Link  = 'https://www.moddb.com/mods/doom-64-retribution/addons/doom-64-retribution-ogg-music-pack-v13'
        LinkText = 'OGG music pack on ModDB'
    }
    'engine'    = @{ Title = 'gzdoom.exe is missing from this package'; Body = 'This download is incomplete. Re-extract the release, keeping the folder structure intact.'; Link = ''; LinkText = '' }
    'rtgl'      = @{ Title = 'rt\bin\RTGL1.dll is missing from this package'; Body = 'This download is incomplete. Re-extract the release, keeping the folder structure intact.'; Link = ''; LinkText = '' }
}

$keys = @($Missing -split ';' | Where-Object { $_ -and $items.ContainsKey($_) })
if (-not $keys) { $keys = @('retribution') }

$form                 = New-Object System.Windows.Forms.Form
$form.Text            = 'Doom 64 - Ray Traced'
$form.BackColor       = $BG
$form.ForeColor       = $BONE
$form.ClientSize      = New-Object System.Drawing.Size(710, 400)   # height set after layout
# Every position below is in pixels. Without this, WinForms rescales them by the
# display DPI after Show() while the size we compute stays put, and the bottom
# button falls off the window on any 125% or 150% screen.
$form.AutoScaleMode   = [System.Windows.Forms.AutoScaleMode]::None
$form.StartPosition   = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox     = $false
$form.MinimizeBox     = $false
$form.Font            = New-Object System.Drawing.Font('Segoe UI', 9)

# --- title -----------------------------------------------------------------
$title            = New-Object System.Windows.Forms.Label
$title.Text       = 'DOOM 64'
$title.Font       = New-Object System.Drawing.Font('Impact', 40, [System.Drawing.FontStyle]::Regular)
$title.ForeColor  = $BLOOD
$title.AutoSize   = $true
$title.Location   = New-Object System.Drawing.Point(28, 16)
$form.Controls.Add($title)

$sub              = New-Object System.Windows.Forms.Label
$sub.Text         = 'R A Y   T R A C E D'
$sub.Font         = New-Object System.Drawing.Font('Consolas', 12, [System.Drawing.FontStyle]::Bold)
$sub.ForeColor    = $DIM
$sub.AutoSize     = $true
$sub.Location     = New-Object System.Drawing.Point(34, 78)
$form.Controls.Add($sub)

$rule             = New-Object System.Windows.Forms.Label
$rule.BorderStyle = 'None'
$rule.BackColor   = $BLOOD
$rule.Size        = New-Object System.Drawing.Size(654, 2)
$rule.Location    = New-Object System.Drawing.Point(28, 108)
$form.Controls.Add($rule)

$head             = New-Object System.Windows.Forms.Label
$head.Text        = if ($keys -contains 'engine' -or $keys -contains 'rtgl') { 'THIS DOWNLOAD IS INCOMPLETE' } else { 'YOU ARE MISSING THE GAME FILES' }
$head.Font        = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
$head.ForeColor   = $RED
$head.AutoSize    = $true
$head.Location    = New-Object System.Drawing.Point(28, 122)
$form.Controls.Add($head)

$intro            = New-Object System.Windows.Forms.Label
$intro.Text       = "This project ships the renderer, not the game. Doom 64, Retribution and its soundtrack belong to their authors, so you bring those yourself -- all of it is free except the DOOM II IWAD."
$intro.ForeColor  = $BONE
$intro.Size       = New-Object System.Drawing.Size(654, 40)
$intro.Location   = New-Object System.Drawing.Point(28, 150)
$form.Controls.Add($intro)

# --- one panel per missing piece -------------------------------------------
$y = 196
foreach ($k in $keys) {
    $it = $items[$k]

    $p           = New-Object System.Windows.Forms.Panel
    $p.BackColor = $PANEL
    $p.Size      = New-Object System.Drawing.Size(654, 116)
    $p.Location  = New-Object System.Drawing.Point(28, $y)

    $bar           = New-Object System.Windows.Forms.Label
    $bar.BackColor = $RED
    $bar.Size      = New-Object System.Drawing.Size(3, 116)
    $bar.Location  = New-Object System.Drawing.Point(0, 0)
    $p.Controls.Add($bar)

    $t           = New-Object System.Windows.Forms.Label
    $t.Text      = $it.Title
    $t.Font      = New-Object System.Drawing.Font('Consolas', 11, [System.Drawing.FontStyle]::Bold)
    $t.ForeColor = $BLOOD
    $t.AutoSize  = $true
    $t.Location  = New-Object System.Drawing.Point(18, 12)
    $p.Controls.Add($t)

    $b           = New-Object System.Windows.Forms.Label
    $b.Text      = $it.Body
    $b.ForeColor = $BONE
    $b.Size      = New-Object System.Drawing.Size(614, 42)
    $b.Location  = New-Object System.Drawing.Point(18, 38)
    $p.Controls.Add($b)

    if ($it.Link) {
        $lnk               = New-Object System.Windows.Forms.LinkLabel
        $lnk.Text          = $it.LinkText
        $lnk.LinkColor     = $BLOOD
        $lnk.ActiveLinkColor = $RED
        $lnk.AutoSize      = $true
        $lnk.Location      = New-Object System.Drawing.Point(18, 86)
        $url               = $it.Link
        $lnk.Add_LinkClicked({ Start-Process $url }.GetNewClosure())
        $p.Controls.Add($lnk)
    }

    $form.Controls.Add($p)
    $y += 132
}

# --- where to put them ------------------------------------------------------
$where           = New-Object System.Windows.Forms.Label
$where.Text      = "Put them here:  $GameDir"
$where.Font      = New-Object System.Drawing.Font('Consolas', 9)
$where.ForeColor = $DIM
$where.Size      = New-Object System.Drawing.Size(500, 20)
$where.Location  = New-Object System.Drawing.Point(28, ($y + 12))
$form.Controls.Add($where)

$open            = New-Object System.Windows.Forms.Button
$open.Text       = 'Open folder'
$open.FlatStyle  = 'Flat'
$open.BackColor  = $PANEL
$open.ForeColor  = $BONE
$open.Size       = New-Object System.Drawing.Size(110, 30)
$open.Location   = New-Object System.Drawing.Point(546, ($y + 6))
$open.Add_Click({ if (Test-Path $GameDir) { Start-Process explorer.exe $GameDir } })
$form.Controls.Add($open)

$ok              = New-Object System.Windows.Forms.Button
$ok.Text         = 'Rip and tear... later'
$ok.FlatStyle    = 'Flat'
$ok.BackColor    = $PANEL
$ok.ForeColor    = $BLOOD
$ok.Size         = New-Object System.Drawing.Size(180, 32)
$ok.Location     = New-Object System.Drawing.Point(476, ($y + 46))
$ok.Add_Click({ $form.Close() })
$form.Controls.Add($ok)
$form.AcceptButton = $ok

# The window is exactly as tall as its content: one panel per missing piece,
# so a single missing file does not open a half-empty window.
$form.ClientSize = New-Object System.Drawing.Size(710, ($y + 92))

[void]$form.ShowDialog()
