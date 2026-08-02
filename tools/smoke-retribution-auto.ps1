# Auto smoke-test Retribution RT without user input.
# Windowed + warp to MAP01. Skips IWAD Launch dialog via -config + optional button click.
param(
  [ValidateSet('diag','rt','modcompat')]
  [string]$Mode = 'diag',
  [int]$WaitSeconds = 20,
  [int]$Width = 1280,
  [int]$Height = 720,
  [switch]$NoKeySpam,
  [switch]$KillAfter
)

$ErrorActionPreference = 'Stop'
$Root = 'G:\AI\Doom64-RT'
$Iwad = 'D:\Games\GZDoom\doom2.wad'
$Mod  = Join-Path $Root 'Doom64-Retribution\D64RTR_v15.WAD'
$Bm   = Join-Path $Root 'Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3'
$Cfg  = Join-Path $Root 'tools\gzdoom-auto.ini'
# Prefer NOT forcing a bare -config (strips user settings). Use it only as queryiwad helper.
$UseBareConfig = $false
$Log  = Join-Path $Root "smoke-auto-$Mode.txt"
$Err  = Join-Path $Root "smoke-auto-$Mode.err"

switch ($Mode) {
  'diag' {
    $Wd  = Join-Path $Root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
    $Exe = Join-Path $Wd 'gzdoom.exe'
    $Extra = @('-nosound', '+rt_classic', '1')
  }
  'rt' {
    $Wd  = Join-Path $Root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
    $Exe = Join-Path $Wd 'gzdoom.exe'
    $Extra = @()
  }
  'modcompat' {
    $Wd  = Join-Path $Root 'runtime-mod'
    $Exe = Join-Path $Wd 'gzdoom-mod.exe'
    $Extra = @('+rt_classic', '0')
  }
}

if (-not (Test-Path -LiteralPath $Exe)) { throw "Missing exe: $Exe" }
if (-not (Test-Path -LiteralPath $Mod)) { throw "Missing mod: $Mod" }

Get-Process gzdoom, gzdoom-mod -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Remove-Item $Log, $Err -ErrorAction SilentlyContinue

# Single argument string avoids PowerShell Start-Process array-quoting bugs
function Q([string]$s) { if ($s -match '[\s"]') { '"' + ($s -replace '"','\"') + '"' } else { $s } }

$argParts = @()
if ($UseBareConfig -and (Test-Path -LiteralPath $Cfg)) {
  $argParts += @('-config', (Q $Cfg))
}
$argParts += @(
  '-iwad', (Q $Iwad),
  '-file', (Q $Mod), (Q $Bm),
  '-rtnolauncher',
  '-width', "$Width",
  '-height', "$Height",
  '-stdout',
  '+vid_fullscreen', '0',
  '+queryiwad', 'false',
  '+rt_mod_compat', '3',
  '+r_drawvoxels', '0',
  '+d64_enterfade', '0',
  '+d64_exitfade', '0',
  '+rt_fluid', 'false',
  '+rt_autoexport', 'false',
  '+map', 'map01'
) + $Extra
$argLine = ($argParts -join ' ')

Write-Host "Launching $Mode windowed ${Width}x${Height} -> MAP01 (no Launch click needed)"
Write-Host "  exe: $Exe"
Write-Host "  args: $argLine"
Write-Host "  log: $Log"

$p = Start-Process -FilePath $Exe -WorkingDirectory $Wd -ArgumentList $argLine `
  -RedirectStandardOutput $Log -RedirectStandardError $Err -PassThru

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class AutoUi {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWnd, EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
  const uint BM_CLICK = 0x00F5;
  const uint WM_COMMAND = 0x0111;
  const uint KEYEVENTF_KEYUP = 0x0002;
  static string TextOf(IntPtr h) {
    var sb = new StringBuilder(512);
    GetWindowText(h, sb, sb.Capacity);
    return sb.ToString();
  }
  static string ClassOf(IntPtr h) {
    var sb = new StringBuilder(256);
    GetClassName(h, sb, sb.Capacity);
    return sb.ToString();
  }
  public static bool ClickLaunch(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      uint wpid; GetWindowThreadProcessId(h, out wpid);
      if (wpid != pid) return true;
      string t = TextOf(h);
      string c = ClassOf(h);
      // GZDoom welcome / IWAD dialog
      if (c == "#32770" || t.IndexOf("Ray Traced", StringComparison.OrdinalIgnoreCase) >= 0
          || t.IndexOf("GZDoom", StringComparison.OrdinalIgnoreCase) >= 0
          || t.IndexOf("Welcome", StringComparison.OrdinalIgnoreCase) >= 0) {
        found = h;
        return false;
      }
      return true;
    }, IntPtr.Zero);
    if (found == IntPtr.Zero) return false;
    ShowWindow(found, 5);
    SetForegroundWindow(found);
    // Prefer clicking a button named Launch / OK
    IntPtr button = IntPtr.Zero;
    EnumChildWindows(found, (h, l) => {
      string t = TextOf(h);
      string c = ClassOf(h);
      if (c.Contains("Button") && (t.IndexOf("Launch", StringComparison.OrdinalIgnoreCase) >= 0
          || t == "OK" || t.IndexOf("OK", StringComparison.OrdinalIgnoreCase) >= 0)) {
        button = h; return false;
      }
      return true;
    }, IntPtr.Zero);
    if (button != IntPtr.Zero) {
      SendMessage(button, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
      return true;
    }
    // Fallback: Enter
    keybd_event(0x0D, 0, 0, UIntPtr.Zero);
    keybd_event(0x0D, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    return true;
  }
  public static void Tap(byte vk) {
    keybd_event(vk, 0, 0, UIntPtr.Zero);
    keybd_event(vk, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
  }
}
'@

# Dismiss IWAD dialog if it still appears (config/patch miss)
# Cap waits: never hang more than 20s on game/shell crash checks
if ($WaitSeconds -gt 20) { $WaitSeconds = 20 }
$deadline = (Get-Date).AddSeconds([Math]::Min(8, $WaitSeconds))
$clicked = $false
while ((Get-Date) -lt $deadline -and -not $p.HasExited) {
  try { $p.Refresh() } catch { break }
  if (-not $NoKeySpam) {
    if ([AutoUi]::ClickLaunch([uint32]$p.Id)) {
      if (-not $clicked) { Write-Host "Clicked/dismissed IWAD Launch dialog"; $clicked = $true }
    }
    if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
      [void][AutoUi]::ShowWindow($p.MainWindowHandle, 5)
      [void][AutoUi]::SetForegroundWindow($p.MainWindowHandle)
      [AutoUi]::Tap(0x0D)
      Start-Sleep -Milliseconds 80
      [AutoUi]::Tap(0x20)
    }
  }
  Start-Sleep -Milliseconds 350
}

$exitedClean = $p.WaitForExit($WaitSeconds * 1000)
try { $p.Refresh() } catch {}
$alive = -not $p.HasExited
$exitCode = if ($p.HasExited) { $p.ExitCode } else { $null }

Write-Host ""
Write-Host "=== RESULT ==="
Write-Host ("alive_after_{0}s: {1}" -f $WaitSeconds, $alive)
Write-Host ("waitforexit_returned: {0}" -f $exitedClean)
Write-Host ("exit_code: {0}" -f $(if ($null -eq $exitCode) { '(still running)' } else { $exitCode }))
Write-Host ("pid: {0}" -f $p.Id)
Write-Host ("launch_dialog_clicked: {0}" -f $clicked)

if (Test-Path $Log) {
  Write-Host "--- stdout (tail) ---"
  Get-Content $Log -Tail 50 -ErrorAction SilentlyContinue
}
if (Test-Path $Err) {
  $errText = Get-Content $Err -Raw -ErrorAction SilentlyContinue
  if ($errText) {
    Write-Host "--- stderr (tail) ---"
    Get-Content $Err -Tail 40 -ErrorAction SilentlyContinue
  }
}

if ($KillAfter -and $alive) {
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
  Write-Host "Killed after wait (-KillAfter)."
  $alive = $false
}

if (-not $alive -and $null -ne $exitCode -and $exitCode -ne 0) {
  Write-Host "CRASH/EXIT detected."
  exit 1
}
if ($alive) {
  Write-Host "Still running (windowed). Close manually or: Stop-Process -Id $($p.Id)"
}
exit 0
