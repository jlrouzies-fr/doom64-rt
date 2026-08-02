# Launch Retribution 20s max, click Launch if needed, capture window bitmap.
param([int]$WaitSeconds = 20)
$ErrorActionPreference = 'Stop'
$Root = 'G:\AI\Doom64-RT'
$Wd = Join-Path $Root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$ShotDir = Join-Path $Root 'screenshots'
New-Item -ItemType Directory -Force -Path $ShotDir | Out-Null
$Shot = Join-Path $ShotDir ("ret-{0:yyyyMMdd-HHmmss}.png" -f (Get-Date))

Get-Process gzdoom,gzdoom-mod -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

$arg = @(
  '-iwad','D:\Games\GZDoom\doom2.wad',
  '-file','G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD','G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3',
  '-rtnolauncher','-nosound','-width','1280','-height','720',
  '+vid_fullscreen','0','+map','map01',
  '+rt_mod_compat','3','+r_drawvoxels','0','+d64_enterfade','0',
  '+rt_classic','1','+rt_classic_llpow','1','+rt_classic_llmin','0.4',
  '+rt_autoexport','true','+rt_fluid','false','+rt_upscale_dlss','0'
) -join ' '

$p = Start-Process -FilePath (Join-Path $Wd 'gzdoom.exe') -WorkingDirectory $Wd -ArgumentList $arg -PassThru

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class WinCap {
  public delegate bool E(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(E cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, E cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr h);
  [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr hdcDest, int x, int y, int cx, int cy, IntPtr hdcSrc, int x1, int y1, int rop);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public static void ClickLaunch(uint pid) {
    for (int i=0;i<12;i++) {
      EnumWindows((h,l) => {
        uint wp; GetWindowThreadProcessId(h, out wp); if (wp!=pid) return true;
        EnumChildWindows(h, (c,x) => {
          var ct=new StringBuilder(64); GetWindowText(c,ct,64);
          var cc=new StringBuilder(32); GetClassName(c,cc,32);
          if (cc.ToString().Contains("Button") && ct.ToString().IndexOf("Launch", StringComparison.OrdinalIgnoreCase)>=0) {
            SendMessage(c, 0x00F5, IntPtr.Zero, IntPtr.Zero); return false;
          }
          return true;
        }, IntPtr.Zero);
        return true;
      }, IntPtr.Zero);
      System.Threading.Thread.Sleep(200);
    }
  }
  public static IntPtr MainHwnd(uint pid) {
    IntPtr found = IntPtr.Zero; int best = 0;
    EnumWindows((h,l) => {
      uint wp; GetWindowThreadProcessId(h, out wp); if (wp!=pid) return true;
      RECT r; if (!GetClientRect(h, out r)) return true;
      int area = Math.Max(0,r.R-r.L) * Math.Max(0,r.B-r.T);
      if (area > best) { best = area; found = h; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static bool Capture(IntPtr hwnd, string path) {
    if (hwnd == IntPtr.Zero) return false;
    RECT r; if (!GetClientRect(hwnd, out r)) return false;
    int w = r.R - r.L, h = r.B - r.T;
    if (w < 16 || h < 16) return false;
    SetForegroundWindow(hwnd);
    using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb)) {
      using (var g = Graphics.FromImage(bmp)) {
        IntPtr hdc = g.GetHdc();
        // PW_RENDERFULLCONTENT = 2
        bool ok = PrintWindow(hwnd, hdc, 2);
        if (!ok) {
          IntPtr src = GetDC(hwnd);
          BitBlt(hdc, 0, 0, w, h, src, 0, 0, 0x00CC0020);
          ReleaseDC(hwnd, src);
        }
        g.ReleaseHdc(hdc);
      }
      bmp.Save(path, ImageFormat.Png);
    }
    return true;
  }
}
'@

[WinCap]::ClickLaunch([uint32]$p.Id)
# Let map settle (~8s), capture, then wait remaining up to 20s total
$t0 = Get-Date
Start-Sleep -Seconds 8
$hwnd = [WinCap]::MainHwnd([uint32]$p.Id)
$cap = $false
if ($hwnd -ne [IntPtr]::Zero) {
  $cap = [WinCap]::Capture($hwnd, $Shot)
}
$left = [Math]::Max(0, $WaitSeconds - [int]((Get-Date) - $t0).TotalSeconds)
if ($left -gt 0) { [void]$p.WaitForExit($left * 1000) }
try { $p.Refresh() } catch {}
$alive = -not $p.HasExited
"alive=$alive exit=$(if($p.HasExited){$p.ExitCode}else{'n/a'})"
"hwnd=$hwnd capture=$cap shot=$Shot"
if (Test-Path $Shot) { Get-Item $Shot | Select-Object FullName, Length }
if ($alive) { Stop-Process -Id $p.Id -Force; 'killed' }
