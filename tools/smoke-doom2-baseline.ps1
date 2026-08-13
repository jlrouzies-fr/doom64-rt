# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ErrorActionPreference = 'Stop'
$wd = '$PROJ\sourcecode\gzdoom-rt\build\RelWithDebInfo'
$log = '$PROJ\smoke-doom2.txt'
$scenes = Join-Path $wd 'rt\scenes'
$backup = Join-Path $wd 'rt\scenes_doom2_backup\map01'
$stock = '$PROJ\gzdoom-rt-1.0.2\rt\scenes\map01'
if (-not (Test-Path (Join-Path $scenes 'map01'))) {
  if (Test-Path $backup) { Copy-Item -Recurse $backup (Join-Path $scenes 'map01') }
  elseif (Test-Path $stock) { Copy-Item -Recurse $stock (Join-Path $scenes 'map01') }
}
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item $log -ErrorAction SilentlyContinue
$args = '-iwad D:\Games\GZDoom\doom2.wad -rtnolauncher -width 1280 -height 720 -stdout -nosound +vid_fullscreen 0 +queryiwad false +rt_autoexport false +map map01'
$p = Start-Process -FilePath (Join-Path $wd 'gzdoom.exe') -WorkingDirectory $wd -ArgumentList $args -RedirectStandardOutput $log -PassThru
Start-Sleep 2
# Click Launch if present
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class D2Click {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  public static void Go(uint pid) {
    EnumWindows((h,l) => {
      uint wpid; GetWindowThreadProcessId(h, out wpid); if (wpid != pid) return true;
      var t = new StringBuilder(256); GetWindowText(h, t, 256);
      string ts = t.ToString();
      if (ts.IndexOf("GZDoom", StringComparison.OrdinalIgnoreCase) < 0 && ts.IndexOf("Ray Traced", StringComparison.OrdinalIgnoreCase) < 0) return true;
      EnumChildWindows(h, (c,x) => {
        var ct = new StringBuilder(128); GetWindowText(c, ct, 128);
        var cc = new StringBuilder(64); GetClassName(c, cc, 64);
        if (cc.ToString().Contains("Button") && ct.ToString().IndexOf("Launch", StringComparison.OrdinalIgnoreCase) >= 0) {
          SendMessage(c, 0x00F5, IntPtr.Zero, IntPtr.Zero); return false;
        }
        return true;
      }, IntPtr.Zero);
      return true;
    }, IntPtr.Zero);
  }
}
'@
[D2Click]::Go([uint32]$p.Id)
$done = $p.WaitForExit(20000)
try { $p.Refresh() } catch {}
Write-Host "waitExit=$done hasExited=$($p.HasExited) code=$(if($p.HasExited){$p.ExitCode}else{'alive'})"
Write-Host '--- log ---'
Get-Content $log -Tail 30
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; Write-Host 'killed alive process' }
