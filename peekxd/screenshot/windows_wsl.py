"""WSL screenshot provider using Windows PowerShell/.NET screen capture.

WSLg can expose both ``DISPLAY`` and ``WAYLAND_DISPLAY`` while root-window
capture via X11 tools fails with errors such as ``BadMatch`` or
``unable to read X window image root``.  From WSL, the Windows host desktop is
still reachable through PowerShell and ``System.Drawing``; this provider uses
that path as a reliable WSL fallback.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.errors import ScreenshotError
from ..core.utils import executable_available, run_command
from .base import ScreenshotProvider


class WindowsWslProvider(ScreenshotProvider):
    """Capture the Windows host desktop from WSL via PowerShell."""

    def capture_screen(self, output_path: str, display: int = 0) -> str:
        """Capture the full virtual Windows desktop."""
        del display  # Windows host capture does not use X11 display numbers.
        return self._run_capture(output_path, mode="screen")

    def capture_window(self, output_path: str, window_id: Optional[str] = None) -> str:
        """Capture a Windows window.

        If ``window_id`` is omitted, captures the foreground Windows window.
        Numeric/hex window handles are accepted for explicit capture.
        """
        return self._run_capture(output_path, mode="window", window_id=window_id)

    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> str:
        """Capture a rectangular region of the Windows virtual desktop."""
        return self._run_capture(output_path, mode="region", x=x, y=y, width=width, height=height)

    def list_windows(self) -> List[Dict[str, Any]]:
        """Window enumeration is intentionally conservative for this fallback."""
        return []

    def list_screens(self) -> List[Dict[str, Any]]:
        """Return the Windows virtual screen dimensions when available."""
        try:
            result = self._run_powershell(
                r"""
Add-Type -AssemblyName System.Windows.Forms
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
[PSCustomObject]@{
  name = 'Windows VirtualScreen'
  width = $bounds.Width
  height = $bounds.Height
  x = $bounds.Left
  y = $bounds.Top
} | ConvertTo-Json -Compress
""",
            )
            data = json.loads(result.stdout.strip())
            return [data]
        except Exception:
            return []

    @property
    def available(self) -> bool:
        """True in WSL when PowerShell is callable."""
        return self._is_wsl() and executable_available("powershell.exe") and executable_available("wslpath")

    @staticmethod
    def _is_wsl() -> bool:
        if os.environ.get("WSL_DISTRO_NAME"):
            return True
        try:
            text = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore")
            return "microsoft" in text.lower() or "wsl" in text.lower()
        except OSError:
            return False

    def _run_capture(
        self,
        output_path: str,
        *,
        mode: str,
        window_id: Optional[str] = None,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> str:
        if not self.available:
            raise ScreenshotError("Windows WSL screenshot provider is not available.")

        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        win_output = self._wslpath_to_windows(str(output))

        ps = self._capture_script(
            win_output=win_output,
            mode=mode,
            window_id=window_id or "",
            x=x,
            y=y,
            width=width,
            height=height,
        )
        self._run_powershell(ps)

        if not output.exists() or output.stat().st_size == 0:
            raise ScreenshotError(f"Windows WSL capture did not create output: {output}")
        return str(output)

    @staticmethod
    def _wslpath_to_windows(path: str) -> str:
        result = run_command(["wslpath", "-w", path], check=True)
        return result.stdout.strip()

    @staticmethod
    def _run_powershell(script: str):
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            ps_path = handle.name
        try:
            win_ps_path = WindowsWslProvider._wslpath_to_windows(ps_path)
            return run_command(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", win_ps_path],
                timeout=30,
                check=True,
            )
        finally:
            try:
                os.unlink(ps_path)
            except OSError:
                pass

    @staticmethod
    def _ps_single_quote(value: str) -> str:
        return value.replace("'", "''")

    @classmethod
    def _capture_script(
        cls,
        *,
        win_output: str,
        mode: str,
        window_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> str:
        win_output_q = cls._ps_single_quote(win_output)
        mode_q = cls._ps_single_quote(mode)
        window_id_q = cls._ps_single_quote(window_id)
        return f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public struct RECT {{ public int Left; public int Top; public int Right; public int Bottom; }}
public class Win32 {{
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}}
'@
$ErrorActionPreference = 'Stop'
$out = '{win_output_q}'
$mode = '{mode_q}'
$windowId = '{window_id_q}'

if ($mode -eq 'region') {{
  $bounds = New-Object System.Drawing.Rectangle({int(x)}, {int(y)}, {int(width)}, {int(height)})
}} elseif ($mode -eq 'window') {{
  if ([string]::IsNullOrWhiteSpace($windowId)) {{
    $hwnd = [Win32]::GetForegroundWindow()
  }} elseif ($windowId.StartsWith('0x')) {{
    $hwnd = [IntPtr]([Convert]::ToInt64($windowId.Substring(2), 16))
  }} else {{
    $hwnd = [IntPtr]([Convert]::ToInt64($windowId, 10))
  }}
  $rect = New-Object RECT
  if (-not [Win32]::GetWindowRect($hwnd, [ref]$rect)) {{ throw 'GetWindowRect failed' }}
  $bounds = New-Object System.Drawing.Rectangle($rect.Left, $rect.Top, ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top))
}} else {{
  $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
}}

if ($bounds.Width -le 0 -or $bounds.Height -le 0) {{ throw "Invalid capture bounds: $($bounds.Width)x$($bounds.Height)" }}
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
try {{
  $graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bmp.Size)
  $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
  Write-Output "saved $($bounds.Width)x$($bounds.Height) -> $out"
}} finally {{
  $graphics.Dispose()
  $bmp.Dispose()
}}
"""
