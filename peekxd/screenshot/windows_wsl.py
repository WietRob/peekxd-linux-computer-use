"""WSL screenshot provider using Windows PowerShell/.NET screen capture.

WSLg can expose both ``DISPLAY`` and ``WAYLAND_DISPLAY`` while root-window
capture via X11 tools fails with errors such as ``BadMatch`` or
``unable to read X window image root``. From WSL, the Windows host desktop is
still reachable through PowerShell and ``System.Drawing``; this provider uses
that path as a reliable WSL fallback.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from ..core.errors import ScreenshotError, peekxdError
from ..core.utils import executable_available, run_command
from .base import ScreenshotProvider


class WindowsWslProvider(ScreenshotProvider):
    """Capture the Windows host desktop from WSL via PowerShell."""

    permission_label = "wslg/windows-host"

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
            result = self._run_powershell_script(
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
        """True in WSL when PowerShell and path conversion are callable."""
        return self._is_wsl() and executable_available("powershell.exe") and executable_available("wslpath")

    @staticmethod
    def _is_wsl() -> bool:
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
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
            raise ScreenshotError(
                "Windows WSL screenshot provider is not available: requires WSL, powershell.exe, and wslpath.",
            )

        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        win_temp: Optional[str] = None
        try:
            win_temp = self._run_powershell_capture(
                mode=mode,
                window_id=window_id or "",
                x=x,
                y=y,
                width=width,
                height=height,
            )
            source = Path(self._windows_path_to_wsl(win_temp))
            if not source.exists() or source.stat().st_size == 0:
                raise ScreenshotError(f"Windows WSL capture did not create output: {source}")
            shutil.copyfile(source, output)
            self._validate_png(output)
            return str(output)
        except subprocess.TimeoutExpired as exc:
            raise ScreenshotError(f"Windows WSL capture timed out after {exc.timeout}s") from exc
        except peekxdError as exc:
            raise ScreenshotError(f"Windows WSL capture failed: {exc}") from exc
        finally:
            if win_temp:
                self._cleanup_windows_temp(win_temp)

    @staticmethod
    def _wslpath_to_windows(path: str) -> str:
        result = run_command(["wslpath", "-w", path], check=True)
        return result.stdout.strip()

    @staticmethod
    def _windows_path_to_wsl(path: str) -> str:
        result = run_command(["wslpath", "-u", path], check=True)
        return result.stdout.strip()

    @staticmethod
    def _run_powershell_script(script: str, args: Optional[List[str]] = None):
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            ps_path = handle.name
        try:
            win_ps_path = WindowsWslProvider._wslpath_to_windows(ps_path)
            return run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    win_ps_path,
                    *(args or []),
                ],
                timeout=30,
                check=True,
            )
        finally:
            try:
                os.unlink(ps_path)
            except OSError:
                pass

    def _run_powershell_capture(
        self,
        *,
        mode: str,
        window_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> str:
        result = self._run_powershell_script(
            self._capture_script(),
            [mode, window_id, str(int(x)), str(int(y)), str(int(width)), str(int(height))],
        )
        win_path = result.stdout.strip().splitlines()[-1].strip() if result.stdout else ""
        if not win_path:
            raise ScreenshotError("Windows WSL capture failed: PowerShell did not return an output path.")
        return win_path

    @staticmethod
    def _cleanup_windows_temp(win_path: str) -> None:
        try:
            WindowsWslProvider._run_powershell_script(
                "param([string]$Path)\nRemove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue\n",
                [win_path],
            )
        except Exception:
            pass

    @staticmethod
    def _validate_png(path: Path) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise ScreenshotError(f"Windows WSL capture invalid PNG dimensions: {width}x{height}")
        except ScreenshotError:
            raise
        except Exception as exc:
            raise ScreenshotError(f"Windows WSL capture invalid PNG: {path}") from exc

    @staticmethod
    def _capture_script() -> str:
        return r"""
param(
  [string]$Mode,
  [string]$WindowId,
  [int]$X,
  [int]$Y,
  [int]$Width,
  [int]$Height
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
public class Win32 {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}
'@

$out = Join-Path $env:TEMP ("peekxd-wslg-" + [Guid]::NewGuid().ToString() + ".png")

if ($Mode -eq 'region') {
  $bounds = New-Object System.Drawing.Rectangle($X, $Y, $Width, $Height)
} elseif ($Mode -eq 'window') {
  if ([string]::IsNullOrWhiteSpace($WindowId)) {
    $hwnd = [Win32]::GetForegroundWindow()
  } elseif ($WindowId.StartsWith('0x')) {
    $hwnd = [IntPtr]([Convert]::ToInt64($WindowId.Substring(2), 16))
  } else {
    $hwnd = [IntPtr]([Convert]::ToInt64($WindowId, 10))
  }
  $rect = New-Object RECT
  if (-not [Win32]::GetWindowRect($hwnd, [ref]$rect)) { throw 'GetWindowRect failed' }
  $bounds = New-Object System.Drawing.Rectangle($rect.Left, $rect.Top, ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top))
} else {
  $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
}

if ($bounds.Width -le 0 -or $bounds.Height -le 0) { throw "Invalid capture bounds: $($bounds.Width)x$($bounds.Height)" }
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
try {
  $graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bmp.Size)
  $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
  Write-Output $out
} finally {
  $graphics.Dispose()
  $bmp.Dispose()
}
"""


#: Historical alias: WSLg capture is handled by WindowsWslProvider.
WSLgScreenshotProvider = WindowsWslProvider
