param([string]$Out = 'G:\AI\Doom64-RT\tools\_map_isol\play_shot.png')
# Capture the gzdoom client area from the desktop after forcing the window
# topmost at a known rect. PrintWindow is broken for RT/Vulkan; unfocused
# CopyFromScreen grabs whatever overlaps the game (browser, etc.).
Add-Type -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class WinShot3 {
  [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
  static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
  const uint SWP_SHOWWINDOW = 0x0040;
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X,Y; }
  public static bool Capture(IntPtr hwnd, string path) {
    if (IsIconic(hwnd)) ShowWindow(hwnd, 9);
    // Keep game above other windows for the grab.
    SetWindowPos(hwnd, HWND_TOPMOST, 8, 8, 0, 0, 0x0001 | SWP_SHOWWINDOW); // SWP_NOSIZE
    SetForegroundWindow(hwnd);
    System.Threading.Thread.Sleep(200);
    RECT r; if (!GetClientRect(hwnd, out r)) return false;
    int w = r.Right - r.Left, h = r.Bottom - r.Top;
    if (w < 32 || h < 32) return false;
    POINT p = new POINT();
    if (!ClientToScreen(hwnd, ref p)) return false;
    using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb))
    using (var g = Graphics.FromImage(bmp)) {
      g.CopyFromScreen(p.X, p.Y, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
      bmp.Save(path, ImageFormat.Png);
    }
    SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002); // NOSIZE|NOMOVE
    return true;
  }
}
'@ -ReferencedAssemblies System.Drawing
$p = Get-Process gzdoom -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { throw 'gzdoom not running' }
$p.Refresh()
if ($p.MainWindowHandle -eq [IntPtr]::Zero) { throw 'no main window' }
if ([WinShot3]::Capture($p.MainWindowHandle, $Out)) { "saved $Out" } else { throw 'capture failed' }
