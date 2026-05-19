"""Compatibility doctor for peekxd Linux/WSL environments.

The doctor is intentionally diagnostic-only: it performs provider discovery and
read-only checks by default. Optional smoke mode may capture a screenshot and
validate the resulting PNG, but it never clicks, types, focuses, moves, or
modifies windows.
"""

from __future__ import annotations

import enum
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from PIL import Image

from peekxd.core.desktop import detect_desktop
from peekxd.core.utils import executable_available
from peekxd.input import get_input_provider
from peekxd.inspection import get_inspection_provider
from peekxd.screenshot import get_screenshot_provider
from peekxd.vision import get_vision_provider
from peekxd.window import get_window_provider


class CapabilityStatus(enum.Enum):
    """Compatibility status for a single capability."""

    OK = "OK"
    WARN = "WARN"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    UNKNOWN = "UNKNOWN"


@dataclass
class DoctorCheck:
    """A single compatibility check result."""

    capability: str
    status: CapabilityStatus
    provider: str
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    fix_hint: str = ""
    smoke_tested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "status": self.status.value,
            "provider": self.provider,
            "message": self.message,
            "evidence": _sanitize(self.evidence),
            "fix_hint": self.fix_hint,
            "smoke_tested": self.smoke_tested,
        }


@dataclass
class DoctorResult:
    """A complete doctor run."""

    checks: List[DoctorCheck]

    def to_dict(self) -> Dict[str, Any]:
        return {"checks": [check.to_dict() for check in self.checks]}


ALL_CAPABILITIES = ["desktop", "screenshot", "input", "window", "inspection", "vision", "mcp"]


def run_doctor(
    *,
    capability: Optional[str] = None,
    capabilities: Optional[Iterable[str]] = None,
    smoke: bool = False,
    smoke_dir: Optional[Path] = None,
) -> DoctorResult:
    """Run compatibility checks.

    Args:
        capability: Optional single capability name.
        capabilities: Optional explicit capability list.
        smoke: Enable active but safe smoke tests.
        smoke_dir: Directory for smoke artifacts; intended for tests.
    """
    selected = list(capabilities or ([capability] if capability else ALL_CAPABILITIES))
    checks: List[DoctorCheck] = []
    for name in selected:
        fn = _CHECKS.get(name)
        if fn is None:
            checks.append(DoctorCheck(name, CapabilityStatus.UNKNOWN, "unknown", "Unknown capability", {}, "Use one of: " + ", ".join(ALL_CAPABILITIES), False))
            continue
        try:
            checks.append(fn(smoke=smoke, smoke_dir=smoke_dir))
        except Exception as exc:  # doctor must never fail the whole run
            checks.append(DoctorCheck(name, CapabilityStatus.UNKNOWN, "unknown", f"Doctor check crashed: {exc}", {}, "Report this doctor bug with the command output.", False))
    return DoctorResult(checks)


def _safe_provider_label(provider: Any) -> str:
    label = getattr(provider, "permission_label", None)
    if label:
        return str(label)
    name = getattr(provider, "name", None)
    if isinstance(name, str) and name:
        return name
    return provider.__class__.__name__


def _tool_map(names: Iterable[str]) -> Dict[str, bool]:
    return {name: bool(executable_available(name)) for name in names}


def _sanitize(value: Any) -> Any:
    """Remove private absolute paths from JSON evidence."""
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize(v) for v in value]
    if isinstance(value, str):
        home = str(Path.home())
        if home and home in value:
            value = value.replace(home, "~")
        # Smoke artifacts should be machine-readable without leaking full tmp paths.
        if value.startswith("/tmp/") or value.startswith(str(tempfile.gettempdir()) + "/"):
            return Path(value).name
    return value


def _check_desktop(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    del smoke, smoke_dir
    evidence = {
        "desktop": detect_desktop().value,
        "env": {
            "DISPLAY": bool(os.environ.get("DISPLAY")),
            "WAYLAND_DISPLAY": bool(os.environ.get("WAYLAND_DISPLAY")),
            "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE", ""),
            "WSL_DISTRO_NAME": bool(os.environ.get("WSL_DISTRO_NAME")),
            "WSL_INTEROP": bool(os.environ.get("WSL_INTEROP")),
        },
    }
    return DoctorCheck("desktop", CapabilityStatus.OK, evidence["desktop"], "Desktop/session detected", evidence, "", False)


def _check_screenshot(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    tools = _tool_map(["powershell.exe", "wslpath", "import", "xwd", "convert", "grim", "wayshot", "spectacle", "flameshot", "gnome-screenshot"])
    try:
        provider = get_screenshot_provider()
        provider_label = _safe_provider_label(provider)
    except Exception as exc:
        return DoctorCheck(
            "screenshot",
            CapabilityStatus.BLOCKED,
            "none",
            f"No screenshot provider available: {exc}",
            {"tools": tools},
            "Install/fix WSL powershell.exe+wslpath, X11 imagemagick or xwd+convert, Wayland grim/wayshot, or generic spectacle/flameshot/gnome-screenshot.",
            False,
        )

    evidence: Dict[str, Any] = {"tools": tools}
    if smoke:
        out_dir = Path(smoke_dir) if smoke_dir else Path(tempfile.gettempdir())
        out_path = out_dir / "peekxd-doctor-screenshot-smoke.png"
        try:
            captured = Path(provider.capture_screen(str(out_path)))
            with Image.open(captured) as image:
                image.verify()
            with Image.open(captured) as image:
                width, height = image.size
                mode = image.mode
            evidence.update({"file": captured.name, "dimensions": f"{width}x{height}", "mode": mode})
            return DoctorCheck("screenshot", CapabilityStatus.OK, provider_label, f"Screenshot capture works via {provider_label}", evidence, "", True)
        except Exception as exc:
            return DoctorCheck("screenshot", CapabilityStatus.BLOCKED, provider_label, f"Screenshot smoke failed: {exc}", evidence, "Provider is detected but runtime capture failed; check compositor/session support and fallback tools.", True)

    return DoctorCheck("screenshot", CapabilityStatus.OK, provider_label, f"Screenshot provider detected via {provider_label}", evidence, "Run `peekxd doctor --capability screenshot --smoke` to verify runtime capture.", False)


def _check_input(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    del smoke, smoke_dir
    tools = _tool_map(["xdotool", "ydotool"])
    evidence = {"tools": tools}
    try:
        provider = get_input_provider()
        provider_label = _safe_provider_label(provider)
        return DoctorCheck("input", CapabilityStatus.OK, provider_label, f"Input provider detected via {provider_label}; no click/type smoke performed", evidence, "", False)
    except Exception as exc:
        return DoctorCheck("input", CapabilityStatus.BLOCKED, "none", f"No input provider available: {exc}", evidence, "Install xdotool for X11 or ydotool plus a running ydotoold daemon for Wayland.", False)


def _check_window(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    del smoke_dir
    tools = _tool_map(["xdotool", "xwininfo", "wmctrl", "wlrctl", "swaymsg"])
    evidence: Dict[str, Any] = {"tools": tools}
    try:
        provider = get_window_provider()
        provider_label = _safe_provider_label(provider)
        if smoke:
            windows = provider.list_windows()
            evidence["window_count"] = len(windows)
            return DoctorCheck("window", CapabilityStatus.OK, provider_label, f"Read-only window listing works via {provider_label}", evidence, "", True)
        return DoctorCheck("window", CapabilityStatus.OK, provider_label, f"Window provider detected via {provider_label}", evidence, "Run with --smoke for read-only list_windows check.", False)
    except Exception as exc:
        return DoctorCheck("window", CapabilityStatus.BLOCKED, "none", f"No window provider available: {exc}", evidence, "Install xdotool/xwininfo/wmctrl for X11 or wlrctl/swaymsg for Wayland.", False)


def _check_inspection(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    del smoke_dir
    evidence: Dict[str, Any] = {"python_module": "pyatspi"}
    try:
        provider = get_inspection_provider()
        provider_label = _safe_provider_label(provider)
        if smoke:
            elements = provider.get_ui_tree()
            evidence["element_count"] = len(elements)
            status = CapabilityStatus.OK if elements else CapabilityStatus.WARN
            message = "Read-only AT-SPI tree returned elements" if elements else "AT-SPI provider exists but tree is empty or inaccessible"
            hint = "" if elements else "Ensure at-spi2-registryd is running and apps expose accessibility trees."
            return DoctorCheck("inspection", status, provider_label, message, evidence, hint, True)
        return DoctorCheck("inspection", CapabilityStatus.OK, provider_label, f"Inspection provider detected via {provider_label}", evidence, "Run with --smoke for read-only UI tree check.", False)
    except Exception as exc:
        return DoctorCheck("inspection", CapabilityStatus.BLOCKED, "none", f"No inspection provider available: {exc}", evidence, "Install python3-pyatspi and ensure at-spi2-registryd is running.", False)


def _check_vision(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    evidence: Dict[str, Any] = {"providers": ["hermes", "openai", "anthropic", "ollama"]}
    try:
        provider = get_vision_provider()
        provider_label = _safe_provider_label(provider)
        if smoke:
            out_dir = Path(smoke_dir) if smoke_dir else Path(tempfile.gettempdir())
            image_path = out_dir / "peekxd-doctor-vision-smoke.png"
            Image.new("RGBA", (8, 6), (255, 255, 255, 255)).save(image_path)
            answer = provider.analyze(str(image_path), "Answer with exactly: ok")
            evidence.update({"file": image_path.name, "response_chars": len(answer or "")})
            return DoctorCheck("vision", CapabilityStatus.OK, provider_label, f"Vision smoke works via {provider_label}", evidence, "", True)
        return DoctorCheck("vision", CapabilityStatus.OK, provider_label, f"Vision provider detected via {provider_label}", evidence, "Run with --smoke for a tiny image analysis check.", False)
    except Exception as exc:
        return DoctorCheck("vision", CapabilityStatus.BLOCKED, "none", f"No vision provider available or smoke failed: {exc}", evidence, "Configure Hermes vision, OPENAI_API_KEY, ANTHROPIC_API_KEY, or Ollama.", smoke)


def _check_mcp(*, smoke: bool = False, smoke_dir: Optional[Path] = None) -> DoctorCheck:
    del smoke_dir
    try:
        from peekxd.mcp_server.server import FastMCP, create_mcp_server
        if FastMCP is None:
            raise RuntimeError("fastmcp not installed")
        evidence: Dict[str, Any] = {"fastmcp": True}
        if smoke:
            server = create_mcp_server()
            tool_count = 18
            # FastMCP internals vary by version; record stable expected tool count
            # plus server creation success without starting a transport.
            evidence.update({"server_creatable": bool(server), "tools_expected": tool_count})
            return DoctorCheck("mcp", CapabilityStatus.OK, "fastmcp", f"MCP server can be created; expected {tool_count} tools", evidence, "Use `hermes mcp test peekxd` for external discovery.", True)
        return DoctorCheck("mcp", CapabilityStatus.OK, "fastmcp", "FastMCP is importable", evidence, "Run with --smoke or `hermes mcp test peekxd` for discovery.", False)
    except Exception as exc:
        return DoctorCheck("mcp", CapabilityStatus.BLOCKED, "none", f"MCP unavailable: {exc}", {"fastmcp": False}, "Install fastmcp and verify `peekxd mcp` starts.", smoke)


_CHECKS = {
    "desktop": _check_desktop,
    "screenshot": _check_screenshot,
    "capture": _check_screenshot,
    "input": _check_input,
    "window": _check_window,
    "inspection": _check_inspection,
    "vision": _check_vision,
    "mcp": _check_mcp,
}
