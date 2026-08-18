#requires -version 5
<#
    Doom 64 - Ray Traced : startup check.

    Runs every launch. It lists what the game needs, ticks off what it found and
    explains what it did not, because the alternative -- a console line that
    flashes past on a double-click -- is how a first-time user concludes the
    download is broken when they are simply missing the game files we are not
    allowed to ship.

    Once everything passes, the user can tick "setup is done": that writes
    configdone.txt next to the launcher, which the .cmd tests with `if exist`
    and then goes straight to the game.

    What it FINDS is in launch-doom64-rt-checks.ps1. This file is only how it
    looks -- WPF, chosen over the WinForms window that is still here as
    launch-doom64-rt-ui-classic.ps1 and that the launcher falls back to if this
    one cannot open (exit 2). What WPF buys:

      * layout is in device-independent units, so 4K at 150% needs no scaling
        code at all -- there is no $Scale in this file,
      * every control is retemplated: the checkbox tick is our vector path, the
        scrollbar is eight pixels of our own, the menu and its popups are ours.
        None of those three are reachable from WinForms,
      * the window resizes, and the checklist scrolls inside it, so no screen is
        too small,
      * hover and disabled states are triggers, not event handlers.

    Still not free: the title bar is DWM's either way (same P/Invoke as the
    WinForms build), and .NET Framework WPF re-renders for a per-monitor DPI
    change only with an app.config switch we cannot add to powershell.exe --
    starting DPI is correct, dragging between mismatched monitors may not be.

    Exit 0 = launch, Exit 1 = the user closed the window.
#>
param(
    [string] $Proj      = "",
    [string] $EngineDir = "",
    [string] $ModsDir   = "",
    [string] $GameDir   = "",
    [string] $IwadHint  = "",
    [string] $Settings  = ""
)

Add-Type -Namespace D64 -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")] public static extern IntPtr SetProcessDpiAwarenessContext(IntPtr ctx);
[DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int val, int size);
'@

# Before the first window exists, or the whole thing is a stretched bitmap.
try   { [void][D64.Win]::SetProcessDpiAwarenessContext([System.IntPtr]::new(-4)) }
catch { try { [void][D64.Win]::SetProcessDPIAware() } catch { } }

# Exit 2, not 1, if WPF itself is unavailable: 1 means "the user said no" and
# stops the launch, 2 means "this window could not open" and hands over to the
# WinForms one. A missing window must never be the reason nobody can play.
try {
    Add-Type -AssemblyName PresentationFramework -ErrorAction Stop
    Add-Type -AssemblyName PresentationCore -ErrorAction Stop
    Add-Type -AssemblyName WindowsBase -ErrorAction Stop
} catch {
    [Console]::Error.WriteLine("startup window: WPF is not available ($($_.Exception.Message))")
    exit 2
}

. (Join-Path $PSScriptRoot 'launch-doom64-rt-checks.ps1')

$hBG    = '#0A0909'
$hPANEL = '#141212'
$hEDGE  = '#302C2A'
$hHOT   = '#281A14'
$hBLOOD = '#C8501E'
$hRED   = '#E03B1E'
$hGREEN = '#7AB05B'
$hAMBER = '#CEA03C'
$hBONE  = '#C9C9C9'
$hDIM   = '#827D7A'

function B([string]$hex) {
    New-Object System.Windows.Media.SolidColorBrush(
        [System.Windows.Media.Color][System.Windows.Media.ColorConverter]::ConvertFromString($hex))
}

function Esc([string]$s) {
    if ($null -eq $s) { return '' }
    # &#10; because the detail strings carry a hard line break we want kept
    ($s -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;').Replace("`r`n", '&#10;').Replace("`n", '&#10;')
}

# ---------------------------------------------------------------------------
#  The window
# ---------------------------------------------------------------------------
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Doom 64 - Ray Traced"
        Background="#0A0909" Foreground="#C9C9C9"
        FontFamily="Segoe UI" FontSize="12"
        Width="780" Height="945" MinWidth="620" MinHeight="420"
        WindowStartupLocation="CenterScreen"
        SnapsToDevicePixels="True" UseLayoutRounding="True">
  <Window.Resources>
    <SolidColorBrush x:Key="Bg"    Color="#0A0909"/>
    <SolidColorBrush x:Key="Panel" Color="#141212"/>
    <SolidColorBrush x:Key="Edge"  Color="#302C2A"/>
    <SolidColorBrush x:Key="Hot"   Color="#281A14"/>
    <SolidColorBrush x:Key="Blood" Color="#C8501E"/>
    <SolidColorBrush x:Key="Bone"  Color="#C9C9C9"/>
    <SolidColorBrush x:Key="Dim"   Color="#827D7A"/>

    <!-- Buttons: one template, three states, no event handlers. -->
    <Style TargetType="Button">
      <Setter Property="Foreground" Value="{StaticResource Bone}"/>
      <Setter Property="Background" Value="{StaticResource Panel}"/>
      <Setter Property="BorderBrush" Value="{StaticResource Edge}"/>
      <Setter Property="Padding" Value="14,6"/>
      <Setter Property="SnapsToDevicePixels" Value="True"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="{TemplateBinding Background}"
                    BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="1"
                    Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="b" Property="Background" Value="{StaticResource Hot}"/>
                <Setter TargetName="b" Property="BorderBrush" Value="{StaticResource Blood}"/>
              </Trigger>
              <Trigger Property="IsPressed" Value="True">
                <Setter TargetName="b" Property="Background" Value="{StaticResource Blood}"/>
                <Setter Property="Foreground" Value="#0A0909"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Foreground" Value="#5A5552"/>
                <Setter TargetName="b" Property="BorderBrush" Value="#241F1D"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <!-- The tick is a Path we draw. WinForms hands this glyph to the system
         theme and there is no way to take it back. -->
    <Style TargetType="CheckBox">
      <Setter Property="Foreground" Value="{StaticResource Bone}"/>
      <Setter Property="FontFamily" Value="Consolas"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="CheckBox">
            <StackPanel Orientation="Horizontal" Background="Transparent">
              <Border x:Name="box" Width="15" Height="15" BorderThickness="1"
                      BorderBrush="{StaticResource Edge}" Background="{StaticResource Panel}"
                      VerticalAlignment="Center">
                <Path x:Name="tick" Data="M 2.5,7 L 6,10.5 L 12,3.5"
                      Stroke="{StaticResource Blood}" StrokeThickness="2"
                      Visibility="Collapsed" SnapsToDevicePixels="True"/>
              </Border>
              <ContentPresenter Margin="9,0,0,0" VerticalAlignment="Center"/>
            </StackPanel>
            <ControlTemplate.Triggers>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="tick" Property="Visibility" Value="Visible"/>
                <Setter TargetName="box" Property="BorderBrush" Value="{StaticResource Blood}"/>
              </Trigger>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="box" Property="Background" Value="{StaticResource Hot}"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter Property="Foreground" Value="{StaticResource Dim}"/>
                <Setter TargetName="box" Property="Opacity" Value="0.45"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style TargetType="TextBox">
      <Setter Property="Background" Value="{StaticResource Panel}"/>
      <Setter Property="Foreground" Value="{StaticResource Bone}"/>
      <Setter Property="CaretBrush" Value="{StaticResource Blood}"/>
      <Setter Property="BorderBrush" Value="{StaticResource Edge}"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="6,4"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="TextBox">
            <Border x:Name="b" Background="{TemplateBinding Background}"
                    BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="1"
                    Padding="{TemplateBinding Padding}">
              <ScrollViewer x:Name="PART_ContentHost"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsFocused" Value="True">
                <Setter TargetName="b" Property="BorderBrush" Value="{StaticResource Blood}"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <!-- Eight pixels wide, our colours, no arrow buttons. The WinForms one is
         always the system's light-grey scrollbar. -->
    <Style TargetType="ScrollBar">
      <Setter Property="Width" Value="8"/>
      <Setter Property="Background" Value="Transparent"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ScrollBar">
            <Grid Background="{TemplateBinding Background}">
              <Track x:Name="PART_Track" IsDirectionReversed="True">
                <Track.Thumb>
                  <Thumb>
                    <Thumb.Template>
                      <ControlTemplate TargetType="Thumb">
                        <Border x:Name="t" Background="#4A4442" Margin="2,0"/>
                        <ControlTemplate.Triggers>
                          <Trigger Property="IsMouseOver" Value="True">
                            <Setter TargetName="t" Property="Background" Value="{StaticResource Blood}"/>
                          </Trigger>
                        </ControlTemplate.Triggers>
                      </ControlTemplate>
                    </Thumb.Template>
                  </Thumb>
                </Track.Thumb>
                <Track.IncreaseRepeatButton>
                  <RepeatButton Command="ScrollBar.PageDownCommand" Opacity="0" Focusable="False"/>
                </Track.IncreaseRepeatButton>
                <Track.DecreaseRepeatButton>
                  <RepeatButton Command="ScrollBar.PageUpCommand" Opacity="0" Focusable="False"/>
                </Track.DecreaseRepeatButton>
              </Track>
            </Grid>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style TargetType="Hyperlink">
      <Setter Property="Foreground" Value="{StaticResource Blood}"/>
      <Setter Property="TextDecorations" Value="{x:Null}"/>
      <Style.Triggers>
        <Trigger Property="IsMouseOver" Value="True">
          <Setter Property="Foreground" Value="#E03B1E"/>
          <Setter Property="TextDecorations" Value="Underline"/>
        </Trigger>
      </Style.Triggers>
    </Style>

    <!-- Menu: top-level items and popup items, both ours. -->
    <ControlTemplate x:Key="TopHeader" TargetType="MenuItem">
      <Border x:Name="b" Background="Transparent" Padding="11,5">
        <Grid>
          <ContentPresenter ContentSource="Header" RecognizesAccessKey="True"/>
          <Popup x:Name="PART_Popup" AllowsTransparency="True" Placement="Bottom"
                 IsOpen="{TemplateBinding IsSubmenuOpen}" Focusable="False" PopupAnimation="None">
            <Border Background="{StaticResource Panel}" BorderBrush="{StaticResource Blood}"
                    BorderThickness="1" Padding="2">
              <StackPanel IsItemsHost="True" KeyboardNavigation.DirectionalNavigation="Cycle"/>
            </Border>
          </Popup>
        </Grid>
      </Border>
      <ControlTemplate.Triggers>
        <Trigger Property="IsHighlighted" Value="True">
          <Setter TargetName="b" Property="Background" Value="{StaticResource Hot}"/>
        </Trigger>
      </ControlTemplate.Triggers>
    </ControlTemplate>

    <ControlTemplate x:Key="SubItem" TargetType="MenuItem">
      <Border x:Name="b" Background="Transparent" Padding="14,6">
        <ContentPresenter ContentSource="Header" RecognizesAccessKey="True"/>
      </Border>
      <ControlTemplate.Triggers>
        <Trigger Property="IsHighlighted" Value="True">
          <Setter TargetName="b" Property="Background" Value="{StaticResource Hot}"/>
        </Trigger>
      </ControlTemplate.Triggers>
    </ControlTemplate>

    <Style TargetType="MenuItem">
      <Setter Property="Foreground" Value="{StaticResource Bone}"/>
      <Setter Property="Template" Value="{StaticResource SubItem}"/>
      <Style.Triggers>
        <Trigger Property="Role" Value="TopLevelHeader">
          <Setter Property="Template" Value="{StaticResource TopHeader}"/>
        </Trigger>
        <Trigger Property="Role" Value="TopLevelItem">
          <Setter Property="Template" Value="{StaticResource TopHeader}"/>
        </Trigger>
      </Style.Triggers>
    </Style>

    <Style TargetType="Separator">
      <Setter Property="Background" Value="{StaticResource Edge}"/>
      <Setter Property="Height" Value="1"/>
      <Setter Property="Margin" Value="4,3"/>
    </Style>
  </Window.Resources>

  <Grid>
    <Grid.RowDefinitions>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="*"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
    </Grid.RowDefinitions>

    <Menu x:Name="menu" Grid.Row="0" Background="#141212" BorderThickness="0" Padding="4,0">
      <MenuItem Header="_Setup">
        <MenuItem x:Name="miRecheck" Header="Re-check now  (F5)"/>
        <MenuItem x:Name="miBrowse"  Header="Browse for doom2.wad..."/>
        <MenuItem x:Name="miFolder"  Header="Open game folder"/>
        <Separator/>
        <MenuItem x:Name="miQuit"    Header="Quit"/>
      </MenuItem>
      <MenuItem Header="_Get the files">
        <MenuItem x:Name="miRetro" Header="Doom 64: Retribution (ModDB)"/>
        <MenuItem x:Name="miMusic" Header="OGG music pack v1.3 (ModDB)"/>
        <MenuItem x:Name="miIwad"  Header="DOOM II (Steam)"/>
        <MenuItem x:Name="miRecol" Header="Classic recolour add-on"/>
      </MenuItem>
      <MenuItem Header="_Help">
        <MenuItem x:Name="miAbout" Header="What is being checked?"/>
      </MenuItem>
    </Menu>

    <Image x:Name="logo" Grid.Row="1" Height="150" Margin="0,8,0,4" Stretch="Uniform"/>

    <Grid Grid.Row="2" Margin="28,0,28,8">
      <Border Height="2" Background="{StaticResource Blood}" VerticalAlignment="Top"/>
      <TextBlock Text="STARTUP CHECK" FontFamily="Consolas" FontSize="14" FontWeight="Bold"
                 Foreground="{StaticResource Dim}" Margin="0,10,0,0"/>
    </Grid>

    <ScrollViewer Grid.Row="3" Margin="28,0,20,0" VerticalScrollBarVisibility="Auto"
                  HorizontalScrollBarVisibility="Disabled" Focusable="False">
      <StackPanel x:Name="rowHost" Margin="0,0,8,0"/>
    </ScrollViewer>

    <Grid Grid.Row="4" Margin="28,10,28,0">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="Auto"/>
        <ColumnDefinition Width="*"/>
        <ColumnDefinition Width="Auto"/>
        <ColumnDefinition Width="Auto"/>
      </Grid.ColumnDefinitions>
      <TextBlock Grid.Column="0" Text="doom2.wad" FontFamily="Consolas" Foreground="{StaticResource Dim}"
                 VerticalAlignment="Center" Margin="0,0,10,0"/>
      <TextBox   x:Name="iwadBox" Grid.Column="1" VerticalAlignment="Center"/>
      <Button    x:Name="btnBrowse"  Grid.Column="2" Content="Browse..." Margin="8,0,0,0"/>
      <Button    x:Name="btnRecheck" Grid.Column="3" Content="Re-check"  Margin="8,0,0,0"
                 Foreground="{StaticResource Blood}"/>
    </Grid>

    <TextBlock x:Name="status" Grid.Row="5" Margin="28,10,28,0" FontFamily="Consolas"/>

    <Grid Grid.Row="6" Margin="28,14,28,18">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="*"/>
        <ColumnDefinition Width="Auto"/>
      </Grid.ColumnDefinitions>
      <StackPanel Grid.Column="0" VerticalAlignment="Center">
        <CheckBox x:Name="recolor" Content="Classic recoloured Cacodemon / Pain Elemental"
                  Visibility="Collapsed" Margin="0,0,0,8"/>
        <CheckBox x:Name="skip" Content="Setup is done - go straight to the game next time"/>
        <TextBlock x:Name="skipNote" Foreground="{StaticResource Dim}" FontSize="11" Margin="24,4,0,0"/>
      </StackPanel>
      <StackPanel Grid.Column="1" Orientation="Horizontal" VerticalAlignment="Bottom">
        <Button x:Name="btnFolder" Content="Open game folder"/>
        <Button x:Name="btnQuit"   Content="Quit" Margin="8,0,0,0" Foreground="{StaticResource Dim}"/>
        <Button x:Name="btnLaunch" Content="RIP AND TEAR" Margin="8,0,0,0" Padding="18,10"
                FontFamily="Consolas" FontWeight="Bold" FontSize="14"
                Foreground="{StaticResource Blood}"/>
      </StackPanel>
    </Grid>
  </Grid>
</Window>
'@

try { $win = [System.Windows.Markup.XamlReader]::Parse($xaml) }
catch {
    [Console]::Error.WriteLine("startup window: XAML rejected ($($_.Exception.Message))")
    exit 2
}

foreach ($n in 'menu','logo','rowHost','iwadBox','btnBrowse','btnRecheck','status',
                'recolor','skip','skipNote','btnFolder','btnQuit','btnLaunch',
                'miRecheck','miBrowse','miFolder','miQuit','miRetro','miMusic','miIwad','miRecol','miAbout') {
    Set-Variable -Name $n -Value $win.FindName($n) -Scope Script
}

# Never taller than the screen it opens on -- the checklist scrolls instead.
$wa = [System.Windows.SystemParameters]::WorkArea
$win.MaxHeight = $wa.Height - 20
$win.MaxWidth  = $wa.Width  - 20

# Dark caption, square corners, blood border -- DWM owns the title bar in WPF
# exactly as much as it does in WinForms.
$win.Add_SourceInitialized({
    $h = (New-Object System.Windows.Interop.WindowInteropHelper($win)).Handle
    if ($h -eq [System.IntPtr]::Zero) { return }
    foreach ($attr in 20, 19) { $v = 1; try { [void][D64.Win]::DwmSetWindowAttribute($h, $attr, [ref]$v, 4) } catch { } }
    $v = 1;        try { [void][D64.Win]::DwmSetWindowAttribute($h, 33, [ref]$v, 4) } catch { }
    $v = 0x121214; try { [void][D64.Win]::DwmSetWindowAttribute($h, 35, [ref]$v, 4) } catch { }
    $v = 0xC9C9C9; try { [void][D64.Win]::DwmSetWindowAttribute($h, 36, [ref]$v, 4) } catch { }
    $v = 0x1E50C8; try { [void][D64.Win]::DwmSetWindowAttribute($h, 34, [ref]$v, 4) } catch { }
})

$logoPath = @("$Proj\launcher-banner.png", "$Proj\docs\img\doom64rt-banner.png") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
if ($logoPath) {
    $logo.Source = New-Object System.Windows.Media.Imaging.BitmapImage([Uri]((Resolve-Path $logoPath).Path))
} else {
    $logo.Visibility = 'Collapsed'
}

# ---------------------------------------------------------------------------
#  Rows
# ---------------------------------------------------------------------------
$script:AllOk = $false

function New-Row($c) {
    $tone = if ($c.Ok) { $hGREEN } else { if ($c.Req) { $hRED } elseif ($c.Opt) { $hDIM } else { $hAMBER } }
    $mark = if ($c.Ok) { [char]0x2713 } else { if ($c.Req) { [char]0x2715 } elseif ($c.Opt) { '+' } else { '!' } }
    $name = if ($c.Ok) { $hBONE } else { if ($c.Opt) { $hDIM } else { $hBLOOD } }
    $det  = if ($c.Ok -or $c.Opt) { $hDIM } else { $hBONE }
    $text = if ($c.Ok) { $c.Good } else { $c.Bad }

    $link = ''
    if (-not $c.Ok -and $c.Link) {
        $link = '<TextBlock Margin="0,4,0,0"><Hyperlink x:Name="lnk" NavigateUri="{0}">{1}</Hyperlink></TextBlock>' -f (Esc $c.Link), (Esc $c.LinkText)
    }
    $confirm = ''
    if ($c.Confirm) {
        $confirm = '<Button x:Name="use" Content="Use this copy" HorizontalAlignment="Left" Margin="0,6,0,0" Padding="10,3" Foreground="#CEA03C"/>'
    }

    $rowXaml = @'
<Border xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Background="#141212" Margin="0,0,0,6">
  <Grid>
    <Grid.ColumnDefinitions>
      <ColumnDefinition Width="3"/>
      <ColumnDefinition Width="42"/>
      <ColumnDefinition Width="250"/>
      <ColumnDefinition Width="*"/>
    </Grid.ColumnDefinitions>
    <Rectangle Grid.Column="0" Fill="{TONE}"/>
    <TextBlock Grid.Column="1" Text="{MARK}" Foreground="{TONE}" FontSize="17" FontWeight="Bold"
               HorizontalAlignment="Center" Margin="0,12,0,0"/>
    <StackPanel Grid.Column="2" Margin="0,12,10,12">
      <TextBlock Text="{NAME}" FontFamily="Consolas" FontSize="13" FontWeight="Bold" Foreground="{NAMECOLOR}"
                 TextWrapping="Wrap"/>
      {LINK}
      {CONFIRM}
    </StackPanel>
    <TextBlock Grid.Column="3" Text="{DETAIL}" Foreground="{DETCOLOR}" TextWrapping="Wrap"
               Margin="0,12,14,12"/>
  </Grid>
</Border>
'@
    foreach ($sub in @(@('{TONE}', $tone), @('{MARK}', (Esc $mark)),
                       @('{NAMECOLOR}', $name), @('{NAME}', (Esc $c.Name)),
                       @('{DETCOLOR}', $det), @('{DETAIL}', (Esc $text)),
                       @('{LINK}', $link), @('{CONFIRM}', $confirm))) {
        $rowXaml = $rowXaml.Replace($sub[0], [string]$sub[1])
    }

    $row = [System.Windows.Markup.XamlReader]::Parse($rowXaml)

    if ($link) {
        $h = $row.FindName('lnk')
        if ($h) {
            $u = $c.Link
            $h.Add_RequestNavigate({ Start-Process $u }.GetNewClosure())
        }
    }
    if ($confirm) {
        $b = $row.FindName('use')
        if ($b) {
            $b.Add_Click({
                if ($script:IwadPath) { $script:Confirmed += $script:IwadPath }
                Draw-Checks
            })
        }
    }
    return $row
}

function Draw-Checks {
    $rowHost.Children.Clear()

    # Text typed or browsed into the box is a deliberate choice, so it counts as
    # confirmation. Text we auto-filled ourselves does not.
    $typed = $iwadBox.Text
    $script:TypedBad = ""
    if ($typed -and $typed -ne $script:LastAuto) {
        if (Test-Path $typed) { $script:Confirmed += (Resolve-Path $typed).Path }
        else                  { $script:TypedBad = $typed }
    }

    $info = Find-Iwad -Hint $typed
    $script:IwadPath   = if ($info) { $info.Path }   else { "" }
    $script:IwadSource = if ($info) { $info.Source } else { "" }
    if ($script:IwadPath) {
        $iwadBox.Text    = $script:IwadPath
        $script:LastAuto = $script:IwadPath
    }

    $missing = 0
    foreach ($c in (Get-Checks)) {
        [void]$rowHost.Children.Add((New-Row $c))
        if ($c.Req -and -not $c.Ok) { $missing++ }
    }

    $script:AllOk      = ($missing -eq 0)
    $btnLaunch.IsEnabled = $script:AllOk

    # Offering "never show this again" while something is still missing would let
    # the user disable the one window that explains the problem.
    $skip.IsEnabled = $script:AllOk
    if (-not $script:AllOk) { $skip.IsChecked = $false }
    $skipNote.Text = if ($script:AllOk) { 'Writes configdone.txt. Delete it, or run the launcher with "setup", to bring this window back.' }
                     else               { 'Available once every required line is green.' }

    if ($script:TypedBad) {
        $status.Text = 'No file at that path - check it and press Re-check.'
        $status.Foreground = B $hAMBER
    } elseif ($script:AllOk) {
        $status.Text = "All checks passed  -  upscaler: $(Get-Upscaler)"
        $status.Foreground = B $hGREEN
    } else {
        $status.Text = "$missing item(s) still needed. Fix them, then Re-check."
        $status.Foreground = B $hRED
    }
}

# ---------------------------------------------------------------------------
#  Actions
# ---------------------------------------------------------------------------
function Invoke-Browse {
    $dlg = New-Object Microsoft.Win32.OpenFileDialog
    $dlg.Filter = 'DOOM II IWAD (doom2.wad)|doom2.wad|All WADs (*.wad)|*.wad'
    $dlg.Title  = 'Where is your doom2.wad?'
    if ($dlg.ShowDialog() -eq $true) {
        $script:Confirmed += (Resolve-Path $dlg.FileName).Path
        $iwadBox.Text = $dlg.FileName
        Draw-Checks
    }
}

function Open-GameFolder {
    if (-not (Test-Path $GameDir)) { New-Item -ItemType Directory -Path $GameDir -Force | Out-Null }
    Start-Process explorer.exe $GameDir
}

$btnBrowse.Add_Click({ Invoke-Browse })
$btnRecheck.Add_Click({ Draw-Checks })
$btnFolder.Add_Click({ Open-GameFolder })
$btnQuit.Add_Click({ $win.Tag = 'quit'; $win.Close() })
$btnLaunch.Add_Click({
    Save-Launch -Recolor ([bool]$recolor.IsChecked) -SkipNextTime ([bool]$skip.IsChecked -and $script:AllOk)
    $win.Tag = 'launch'
    $win.Close()
})

$miRecheck.Add_Click({ Draw-Checks })
$miBrowse.Add_Click({ Invoke-Browse })
$miFolder.Add_Click({ Open-GameFolder })
$miQuit.Add_Click({ $win.Tag = 'quit'; $win.Close() })
$miRetro.Add_Click({ Start-Process 'https://www.moddb.com/mods/doom-64-retribution' })
$miMusic.Add_Click({ Start-Process 'https://www.moddb.com/mods/doom-64-retribution/addons/doom-64-retribution-ogg-music-pack-v13' })
$miIwad.Add_Click({ Start-Process 'https://store.steampowered.com/app/2300/DOOM_II/' })
$miRecol.Add_Click({ Start-Process 'https://www.moddb.com/games/doom-64/addons/d64classicrecolored' })
$miAbout.Add_Click({
    [void][System.Windows.MessageBox]::Show(
        "Doom 64 - Ray Traced is an engine and a set of ray-tracing assets.`r`n`r`n" +
        "It cannot ship the game: Retribution is a free mod from ModDB, and it in turn needs " +
        "a DOOM II you own. This window finds those files, or says which one is missing and " +
        "where to get it.`r`n`r`n" +
        'Tick "setup is done" once every line is green and it will stop appearing.',
        'Doom 64 - Ray Traced')
})

$win.Add_KeyDown({
    $k = $args[1]
    if (-not $k) { return }
    if ($k.Key -eq 'F5')     { Draw-Checks }
    if ($k.Key -eq 'Escape') { $win.Tag = 'quit'; $win.Close() }
})

# --- optional add-on --------------------------------------------------------
#  Only offered when the file is really there -- a checkbox that does nothing
#  when ticked is worse than no checkbox.
$recolWad = @('D64ClassicRecolored.wad', 'D64ClassicRecolored_OffsetFix.wad') |
            ForEach-Object { Join-Path $Proj "Addons\$_" } |
            Where-Object { Test-Path $_ } | Select-Object -First 1
if ($recolWad) { $recolor.Visibility = 'Visible' }
# Whatever was ticked last time. The launcher clears the value when unticked,
# so an absent line means off, not "never asked".
if ($Settings -and (Test-Path $Settings)) {
    foreach ($line in Get-Content $Settings) {
        if ($line -match '^\s*recolor\s*=\s*1\s*$') { $recolor.IsChecked = $true }
    }
}

$iwadBox.Text  = $IwadHint
$skip.IsChecked = Test-ConfigDone

Draw-Checks
try { [void]$win.ShowDialog() }
catch {
    [Console]::Error.WriteLine("startup window: could not open ($($_.Exception.Message))")
    exit 2
}

if ($win.Tag -eq 'launch') { exit 0 } else { exit 1 }
