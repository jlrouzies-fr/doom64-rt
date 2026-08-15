# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$wd = '$PROJ\sourcecode\gzdoom-rt\build\RelWithDebInfo'
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class CL9 {
  public delegate bool E(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(E cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, E cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  public static void Go(uint pid) {
    for (int i = 0; i < 8; i++) {
      EnumWindows((h, l) => {
        uint wp; GetWindowThreadProcessId(h, out wp); if (wp != pid) return true;
        EnumChildWindows(h, (c, x) => {
          var ct = new StringBuilder(64); GetWindowText(c, ct, 64);
          var cc = new StringBuilder(32); GetClassName(c, cc, 32);
          if (cc.ToString().Contains("Button") && ct.ToString().IndexOf("Launch", StringComparison.OrdinalIgnoreCase) >= 0) {
            SendMessage(c, 0x00F5, IntPtr.Zero, IntPtr.Zero); return false;
          }
          return true;
        }, IntPtr.Zero);
        return true;
      }, IntPtr.Zero);
      System.Threading.Thread.Sleep(150);
    }
  }
}
'@
$arg = @(
  '-iwad','D:\Games\GZDoom\doom2.wad',
  '-file',
  '$PROJ\Doom64-Retribution\D64RTR_v15.WAD',
  '$PROJ\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3',
  '$PROJ\Doom64-Retribution\d64r-map01-rtfix.wad',
  '-rtnolauncher','-nosound','-width','1280','-height','720',
  '+vid_fullscreen','0','+map','map01',
  '+rt_mod_compat','3','+r_drawvoxels','0','+d64_enterfade','0',
  '+rt_classic','1','+rt_autoexport','false','+rt_fluid','false','+rt_upscale_dlss','0'
) -join ' '
$p = Start-Process -FilePath "$wd\gzdoom.exe" -WorkingDirectory $wd -ArgumentList $arg -PassThru
Start-Sleep 1
[CL9]::Go([uint32]$p.Id)
$parts = @()
foreach ($sec in 3, 8, 15, 20) {
  while ([int]((Get-Date) - $p.StartTime).TotalSeconds -lt $sec -and -not $p.HasExited) { Start-Sleep -Milliseconds 150 }
  try { $p.Refresh() } catch {}
  if ($p.HasExited) { $parts += "${sec}s=EXIT:$($p.ExitCode)"; break }
  else { $parts += "${sec}s=$($p.Responding)" }
}
Write-Output ("map01_with_fix : {0}" -f ($parts -join ' | '))
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; 'killed' }
