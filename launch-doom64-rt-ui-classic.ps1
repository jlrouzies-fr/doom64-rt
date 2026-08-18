#requires -version 5
<#
    Doom 64 - Ray Traced : startup check.  (classic WinForms window)

    Runs every launch. It lists what the game needs, ticks off what it found and
    explains what it did not, because the alternative -- a console line that
    flashes past on a double-click -- is how a first-time user concludes the
    download is broken when they are simply missing the game files we are not
    allowed to ship.

    Once everything passes, the user can tick "setup is done" and never see this
    window again: that writes configdone.txt next to the launcher, which the .cmd
    tests with `if exist`.

    What it FINDS lives in launch-doom64-rt-checks.ps1, shared with the -winforms
    and -wpf variants of this window. This file is only how it looks.

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

. (Join-Path $PSScriptRoot 'launch-doom64-rt-checks.ps1')

$BG    = [System.Drawing.Color]::FromArgb(10, 9, 9)
$PANEL = [System.Drawing.Color]::FromArgb(20, 18, 18)
$BLOOD = [System.Drawing.Color]::FromArgb(200, 80, 30)
$RED   = [System.Drawing.Color]::FromArgb(224, 59, 30)
$GREEN = [System.Drawing.Color]::FromArgb(122, 176, 91)
$AMBER = [System.Drawing.Color]::FromArgb(206, 160, 60)
$BONE  = [System.Drawing.Color]::FromArgb(201, 201, 201)
$DIM   = [System.Drawing.Color]::FromArgb(130, 125, 122)

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
    $pic.Size     = New-Object System.Drawing.Size(330, 200)
    $pic.Location = New-Object System.Drawing.Point(((720 - 330) / 2), 8)
    $pic.BackColor = $BG
    $form.Controls.Add($pic)
    $logoH = 201
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
$rowH    = 54
# Rows in the checklist. Everything below the list is positioned off this, so
# adding a check is one number here, not nine edits.
$nRows   = 9

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
        $mark.Text      = if ($c.Ok) { [char]0x2713 } else { if ($c.Req) { [char]0x2715 } elseif ($c.Opt) { '+' } else { '!' } }
        $mark.Font      = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
        $mark.ForeColor = if ($c.Ok) { $GREEN } else { if ($c.Req) { $RED } elseif ($c.Opt) { $DIM } else { $AMBER } }
        $mark.AutoSize  = $true
        $mark.Location  = New-Object System.Drawing.Point(12, 8)
        $p.Controls.Add($mark)

        $n           = New-Object System.Windows.Forms.Label
        $n.Text      = $c.Name
        $n.Font      = New-Object System.Drawing.Font('Consolas', 10, [System.Drawing.FontStyle]::Bold)
        $n.ForeColor = if ($c.Ok) { $BONE } else { if ($c.Opt) { $DIM } else { $BLOOD } }
        $n.Size      = New-Object System.Drawing.Size(230, 18)
        $n.Location  = New-Object System.Drawing.Point(46, 11)
        $p.Controls.Add($n)

        $d           = New-Object System.Windows.Forms.Label
        $d.Text      = if ($c.Ok) { $c.Good } else { $c.Bad }
        $d.ForeColor = if ($c.Ok -or $c.Opt) { $DIM } else { $BONE }
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

    # Offering "never show this again" while something is still missing would let
    # the user disable the one window that explains the problem. Hidden, not
    # disabled: WinForms draws disabled text with the system's embossed grey,
    # which ForeColor cannot touch and which is unreadable on black.
    $skip.Visible    = $script:AllOk
    $skipOff.Visible = -not $script:AllOk
    if (-not $script:AllOk) { $skip.Checked = $false }

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
$iwadLbl.Location  = New-Object System.Drawing.Point(28, ($listTop + $nRows * $rowH + 8))
$form.Controls.Add($iwadLbl)

$iwadBox             = New-Object System.Windows.Forms.TextBox
$iwadBox.BackColor   = $PANEL
$iwadBox.ForeColor   = $BONE
$iwadBox.BorderStyle = 'FixedSingle'
$iwadBox.Size        = New-Object System.Drawing.Size(430, 22)
$iwadBox.Location    = New-Object System.Drawing.Point(100, ($listTop + $nRows * $rowH + 5))
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

$browse = New-Btn 'Browse...' 540 ($listTop + $nRows * $rowH + 3) 70 $BONE
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

$recheck = New-Btn 'Re-check' 616 ($listTop + $nRows * $rowH + 3) 76 $BLOOD
$recheck.Add_Click({ Draw-Checks })
$form.Controls.Add($recheck)

# --- status + actions -------------------------------------------------------
$status           = New-Object System.Windows.Forms.Label
$status.Font      = New-Object System.Drawing.Font('Consolas', 9)
$status.Size      = New-Object System.Drawing.Size(430, 20)
$status.Location  = New-Object System.Drawing.Point(28, ($listTop + $nRows * $rowH + 42))
$form.Controls.Add($status)

# --- optional add-ons -------------------------------------------------------
#  Only offered when the file is really there -- a checkbox that does nothing
#  when ticked is worse than no checkbox. The "Classic recolour" row above says
#  so either way, so an absent add-on still announces itself.
#
#  The user's own ModDB download, loaded untouched. We ship none of it.
$recolWad = @('D64ClassicRecolored.wad', 'D64ClassicRecolored_OffsetFix.wad') |
            ForEach-Object { Join-Path $Proj "Addons\$_" } |
            Where-Object { Test-Path $_ } | Select-Object -First 1

$recolor             = New-Object System.Windows.Forms.CheckBox
$recolor.Text        = 'Classic recoloured Cacodemon / Pain Elemental'
$recolor.Font        = New-Object System.Drawing.Font('Consolas', 9)
$recolor.ForeColor   = $BONE
$recolor.BackColor   = $BG
$recolor.FlatStyle   = 'Flat'
$recolor.AutoSize    = $true
$recolor.Location    = New-Object System.Drawing.Point(28, ($listTop + $nRows * $rowH + 106))
$recolor.Visible     = [bool]$recolWad
# Whatever was ticked last time. The launcher clears the value when unticked,
# so an absent line means off, not "never asked".
$recolor.Checked     = $false
if ($Settings -and (Test-Path $Settings)) {
    foreach ($line in Get-Content $Settings) {
        if ($line -match '^\s*recolor\s*=\s*1\s*$') { $recolor.Checked = $true }
    }
}
$form.Controls.Add($recolor)

# --- do not ask me again ----------------------------------------------------
#  Ticked, this writes configdone.txt and the launcher goes straight to the game
#  from then on. Enabled only once every required item is green -- see Draw-Checks.
$skipY = $listTop + $nRows * $rowH + $(if ($recolWad) { 128 } else { 106 })
$skip              = New-Object System.Windows.Forms.CheckBox
$skip.Text         = 'Setup is done - go straight to the game next time'
$skip.Font         = New-Object System.Drawing.Font('Consolas', 9)
$skip.ForeColor    = $BONE
$skip.BackColor    = $BG
$skip.FlatStyle    = 'Flat'
$skip.AutoSize     = $true
$skip.Location     = New-Object System.Drawing.Point(28, $skipY)
$skip.Checked      = Test-ConfigDone
$form.Controls.Add($skip)

# What stands in its place until the checklist is green.
$skipOff           = New-Object System.Windows.Forms.Label
$skipOff.Text      = 'Setup is done - offered once every required line is green'
$skipOff.Font      = New-Object System.Drawing.Font('Consolas', 9)
$skipOff.ForeColor = $DIM
$skipOff.BackColor = $BG
$skipOff.AutoSize  = $true
$skipOff.Location  = New-Object System.Drawing.Point(45, ($skipY + 2))
$form.Controls.Add($skipOff)

$openDir = New-Btn 'Open game folder' 28 ($listTop + $nRows * $rowH + 66) 140 $BONE
$openDir.Add_Click({ if (Test-Path $GameDir) { Start-Process explorer.exe $GameDir } else { New-Item -ItemType Directory -Path $GameDir -Force | Out-Null; Start-Process explorer.exe $GameDir } })
$form.Controls.Add($openDir)

$quit = New-Btn 'Quit' 470 ($listTop + $nRows * $rowH + 64) 90 $DIM
$quit.Add_Click({ $form.Tag = 'quit'; $form.Close() })
$form.Controls.Add($quit)

$launch = New-Btn 'RIP AND TEAR' 570 ($listTop + $nRows * $rowH + 60) 122 $BLOOD
$launch.Font = New-Object System.Drawing.Font('Consolas', 10, [System.Drawing.FontStyle]::Bold)
$launch.Size = New-Object System.Drawing.Size(122, 34)
$launch.Add_Click({
    Save-Launch -Recolor $recolor.Checked -SkipNextTime ($skip.Checked -and $script:AllOk)
    $form.Tag = 'launch'
    $form.Close()
})
$form.Controls.Add($launch)

# The two checkboxes are the only things below the buttons, so they are also the
# only reason to grow the window.
$form.ClientSize = New-Object System.Drawing.Size(720, ($skipY + 40))

$form.Add_Shown({ $recheck.Select() })

Draw-Checks
[void]$form.ShowDialog()

if ($form.Tag -eq 'launch') { exit 0 } else { exit 1 }
