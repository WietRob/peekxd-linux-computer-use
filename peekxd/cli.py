"""CLI for peekxd Linux."""

import json
import sys
from pathlib import Path

import click

from .config import ConfigManager
from .core import detect_desktop, peekxdError
from .core.doctor import run_doctor
from .screenshot import REMOVED_SCREENSHOT_MESSAGE


def _fail_removed_screenshot_path() -> None:
    raise click.ClickException(
        f"{REMOVED_SCREENSHOT_MESSAGE} Use `peekxd see --semantic` instead."
    )


def _run_guarded_cli_action(action, params, runner):
    """Run one raw action through the canonical SafetyExecutor boundary (G3).

    Every direct CLI action command goes through the same gate/executor as
    MCP, macro and orchestrator paths. Any block raises ClickException.
    """
    from .core.decision import DecisionDeniedError, DecisionLedgerError, DecisionStateError
    from .core.executor import SafetyExecutionBlocked, get_executor

    try:
        decision, _envelope, result = get_executor().evaluate_and_execute(
            action, params, entry_point="cli", runner=runner,
        )
        return decision, result
    except (DecisionDeniedError, DecisionStateError) as exc:
        raise click.ClickException(f"BLOCKED by safety policy: {exc}") from exc
    except (DecisionLedgerError, SafetyExecutionBlocked) as exc:
        raise click.ClickException(f"SAFETY BOUNDARY FAILURE (fail closed): {exc}") from exc


def _do_capture(kind: str, output, provider_fn) -> None:
    """Perform a REAL screenshot capture and report path + sha256."""
    import hashlib

    from .screenshot import get_screenshot_provider

    try:
        provider = get_screenshot_provider()
        path = provider_fn(provider, output)
        data = Path(path).read_bytes()
    except Exception as exc:
        raise click.ClickException(f"Capture failed ({kind}): {exc}") from exc
    if not data:
        raise click.ClickException(f"Capture failed ({kind}): empty image at {path}")
    click.echo(f"Captured {kind} -> {path}")
    click.echo(f"sha256: {hashlib.sha256(data).hexdigest()}")


@click.group()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx, config, verbose):
    """peekxd -- Linux automation that sees the screen and does the clicks."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = ConfigManager(config)
    ctx.obj["verbose"] = verbose


@cli.group()
def capture():
    """Capture screenshots."""


@capture.command(name="screen")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--display", "-d", default=0, help="Display number")
@click.pass_context
def capture_screen(ctx, output, display):
    """Capture the full screen to an image file."""
    del ctx

    def run(provider, out):
        out = out or _default_capture_path("screen")
        return provider.capture_screen(out, display=display)

    _do_capture("screen", output, run)


@capture.command(name="window")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--id", help="Window ID")
@click.pass_context
def capture_window(ctx, output, id):
    """Capture a window (active window when --id omitted)."""
    del ctx

    def run(provider, out):
        out = out or _default_capture_path("window")
        return provider.capture_window(out, window_id=id)

    _do_capture("window", output, run)


@capture.command(name="region")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.argument("width", type=int)
@click.argument("height", type=int)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def capture_region(ctx, x, y, width, height, output):
    """Capture a rectangular screen region to an image file."""
    del ctx

    def run(provider, out):
        out = out or _default_capture_path("region")
        return provider.capture_region(out, x=x, y=y, width=width, height=height)

    _do_capture("region", output, run)


def _default_capture_path(kind: str) -> str:
    import time as _time
    return str(Path.cwd() / f"peekxd_{kind}_{int(_time.time())}.png")


@cli.group(invoke_without_command=True)
@click.option("--semantic", is_flag=True, help="Return a semantic accessibility snapshot without visual capture")
@click.option("--json", "json_output", is_flag=True, help="Emit only the JSON semantic envelope")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output")
@click.option("--hud/--no-hud", default=True, help="Render a compact terminal HUD for semantic output")
@click.option("--app", help="Application/window title substring filter")
@click.option("--window-id", help="Window ID filter")
@click.option("--cache-policy", default="prefer_live", type=click.Choice(["prefer_live", "live_only", "cache_only", "refresh"]))
@click.option("--ttl", "ttl_seconds", default=30, type=int, help="Semantic snapshot TTL in seconds")
@click.option("--max-elements", default=60, type=int, help="Maximum semantic elements to include")
@click.pass_context
def see(ctx, semantic, json_output, pretty, hud, app, window_id, cache_policy, ttl_seconds, max_elements):
    """See and analyze the screen."""
    if ctx.invoked_subcommand is not None:
        return
    if not semantic:
        click.echo(ctx.get_help())
        return

    from .semantic import build_semantic_snapshot, render_semantic_hud

    envelope = build_semantic_snapshot(
        app=app,
        window_id=window_id,
        cache_policy=cache_policy,
        ttl_seconds=ttl_seconds,
        max_elements=max_elements,
    )
    if json_output:
        click.echo(json.dumps(envelope, indent=2 if pretty else None, sort_keys=bool(pretty)))
    elif hud:
        click.echo(render_semantic_hud(envelope, max_elements=max_elements))
    else:
        click.echo(json.dumps(envelope))


@see.command(name="capture")
@click.option("--app", help="Application name")
@click.option("--output", "-o", type=click.Path(), help="Output path")
@click.option("--analyze", "-a", help="Analyze with AI prompt")
@click.pass_context
def see_capture(ctx, app, output, analyze):
    """Screenshot-backed see was removed; use ``see --semantic``."""
    del ctx, app, output, analyze
    _fail_removed_screenshot_path()


@cli.command(name="click")
@click.argument("x", type=int, required=False)
@click.argument("y", type=int, required=False)
@click.option("--on", "element_id", help="Semantic element id to click, e.g. W1-B1")
@click.option("--button", default="left", type=click.Choice(["left", "right", "middle"]))
def click_cmd(x, y, element_id, button):
    """Click at X Y or on semantic element id."""
    if element_id:
        from .input import get_input_provider
        from .semantic import build_semantic_snapshot, find_semantic_element

        element = find_semantic_element(build_semantic_snapshot(), element_id)
        decision, coords = _run_guarded_cli_action(
            "click",
            {"element_id": element_id, "button": button},
            lambda: element.click_center(get_input_provider(), button=button),
        )
        cx, cy = coords if isinstance(coords, tuple) else (None, None)
        click.echo(f"Clicked {button} on {element_id} at {cx},{cy} (decision {decision.decision_id})")
        return

    if x is None or y is None:
        raise click.UsageError("X and Y are required unless --on is provided")
    from .input import get_input_provider

    _run_guarded_cli_action(
        "click", {"x": x, "y": y, "button": button},
        lambda: get_input_provider().click(x, y, button),
    )
    click.echo(f"Clicked {button} at {x},{y}")


@cli.command(name="type")
@click.argument("text")
@click.option("--on", "element_id", help="Semantic element id to focus before typing, e.g. W1-T1")
def type_cmd(text, element_id):
    """Type TEXT, optionally into a semantic element id."""
    if element_id:
        from .input import get_input_provider
        from .semantic import build_semantic_snapshot, find_semantic_element

        element = find_semantic_element(build_semantic_snapshot(), element_id)
        decision, coords = _run_guarded_cli_action(
            "type",
            {"text": text, "element_id": element_id},
            lambda: element.type_into(get_input_provider(), text),
        )
        tx, ty = coords if isinstance(coords, tuple) else (None, None)
        click.echo(f"Typed into {element_id} at {tx},{ty}: {text} (decision {decision.decision_id})")
        return

    from .input import get_input_provider

    _run_guarded_cli_action(
        "type", {"text": text}, lambda: get_input_provider().type_text(text))
    click.echo(f"Typed: {text}")


@cli.command()
@click.argument("key")
@click.option("--hotkey", is_flag=True, help="Treat as hotkey combination (comma-separated)")
def key(key, hotkey):
    """Press KEY or hotkey combination."""
    from .input import get_input_provider
    if hotkey:
        keys = key.split(",")
        _run_guarded_cli_action(
            "hotkey", {"keys": keys},
            lambda: get_input_provider().hotkey(*keys))
        click.echo(f"Hotkey: {'+'.join(keys)}")
    else:
        _run_guarded_cli_action(
            "key", {"key": key}, lambda: get_input_provider().key_press(key))
        click.echo(f"Key: {key}")


@cli.command()
@click.argument("x", type=int)
@click.argument("y", type=int)
def move(x, y):
    """Move mouse to X Y."""
    from .input import get_input_provider
    _run_guarded_cli_action(
        "move", {"x": x, "y": y},
        lambda: get_input_provider().move_mouse(x, y))
    click.echo(f"Moved to {x},{y}")


@cli.command()
@click.option("--direction", default="down", type=click.Choice(["up", "down", "left", "right"]))
@click.option("--amount", default=3, help="Scroll amount")
def scroll(direction, amount):
    """Scroll in DIRECTION."""
    from .input import get_input_provider
    _run_guarded_cli_action(
        "scroll", {"direction": direction, "amount": amount},
        lambda: get_input_provider().scroll(direction, amount))
    click.echo(f"Scrolled {direction} x{amount}")


@cli.group()
def window():
    """Window management."""


@window.command(name="list")
def window_list():
    """List all windows."""
    from .window import get_window_provider
    windows = get_window_provider().list_windows()
    for w in windows:
        click.echo(f"{w['id']}: {w.get('title', 'N/A')} ({w.get('class', 'N/A')})")


@window.command(name="focus")
@click.argument("window_id")
def window_focus(window_id):
    """Focus window by ID."""
    from .window import get_window_provider
    _run_guarded_cli_action(
        "focus_window", {"window_id": window_id},
        lambda: get_window_provider().focus_window(window_id))
    click.echo(f"Focused window {window_id}")


@window.command(name="move")
@click.argument("window_id")
@click.argument("x", type=int)
@click.argument("y", type=int)
def window_move(window_id, x, y):
    """Move window to X Y."""
    from .window import get_window_provider
    get_window_provider().move_window(window_id, x, y)
    click.echo(f"Moved window {window_id} to {x},{y}")


@window.command(name="resize")
@click.argument("window_id")
@click.argument("width", type=int)
@click.argument("height", type=int)
def window_resize(window_id, width, height):
    """Resize window to WIDTH HEIGHT."""
    from .window import get_window_provider
    get_window_provider().resize_window(window_id, width, height)
    click.echo(f"Resized window {window_id} to {width}x{height}")


@cli.group()
def display():
    """Display resolution queries."""


@display.command(name="list")
def display_list():
    """List connected displays and resolutions."""
    from .display import get_display_provider

    displays = get_display_provider().list_displays()
    for item in displays:
        suffix = " primary" if item.primary else ""
        click.echo(f"{item.name}: {item.width}x{item.height}+{item.x}+{item.y}{suffix}")


@cli.group(name="file")
def file_cmd():
    """Desktop filesystem navigation."""


@file_cmd.command(name="open")
@click.argument("path", type=click.Path(path_type=Path))
def file_open(path):
    """Open PATH with the desktop's default handler."""
    from .filesystem import get_filesystem_provider

    get_filesystem_provider().open_path(path)
    click.echo(f"Opened: {path}")


@file_cmd.command(name="select")
@click.argument("path", type=click.Path(path_type=Path))
def file_select(path):
    """Reveal PATH in the desktop file manager."""
    from .filesystem import get_filesystem_provider

    get_filesystem_provider().select_path(path)
    click.echo(f"Selected: {path}")


@cli.command(name="notify")
@click.argument("title")
@click.option("--body", default="", help="Notification body text")
@click.option("--urgency", default="normal", type=click.Choice(["low", "normal", "critical"]))
@click.option("--expire-timeout", type=int, help="Notification timeout in milliseconds")
def notify(title, body, urgency, expire_timeout):
    """Send a desktop notification."""
    from .notification import Notification, get_notification_provider

    notification = Notification(
        title=title,
        body=body,
        urgency=urgency,
        expire_timeout=expire_timeout,
    )
    get_notification_provider().send(notification)
    click.echo(f"Notification sent: {title}")


@cli.group()
def inspect():
    """UI inspection."""


@inspect.command(name="tree")
@click.option("--app", help="Application name filter")
def inspect_tree(app):
    """Get UI element tree."""
    from .inspection import get_inspection_provider
    elements = get_inspection_provider().get_ui_tree(app)
    for e in elements[:50]:  # Limit output
        indent = "  " * e.id.count(":")
        click.echo(f"{indent}[{e.role}] {e.name} ({e.position})")


@inspect.command(name="find")
@click.option("--name", "-n", help="Element name")
@click.option("--role", "-r", help="Element role")
def inspect_find(name, role):
    """Find a UI element."""
    from .inspection import get_inspection_provider
    elem = get_inspection_provider().find_element(name=name, role=role)
    if elem:
        click.echo(f"Found: [{elem.role}] {elem.name} at {elem.position}")
    else:
        click.echo("Not found")


@cli.command()
@click.argument("image_path", type=click.Path(exists=True))
@click.argument("prompt")
def analyze(image_path, prompt):
    """Analyze IMAGE with AI using PROMPT."""
    from .vision import get_vision_provider
    result = get_vision_provider().analyze(image_path, prompt)
    click.echo(result)


@cli.group()
def config():
    """Configuration management."""


@config.command(name="init")
@click.pass_context
def config_init(ctx):
    """Create default config."""
    ctx.obj["config"].init()
    click.echo(f"Config created at {ctx.obj['config'].config_path}")


@config.command(name="show")
@click.pass_context
def config_show(ctx):
    """Show current config."""
    click.echo(ctx.obj["config"].show())


@config.command(name="set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx, key, value):
    """Set config KEY to VALUE."""
    ctx.obj["config"].set(key, value)
    ctx.obj["config"].save()
    click.echo(f"Set {key} = {value}")


@config.command(name="get")
@click.argument("key")
@click.pass_context
def config_get(ctx, key):
    """Get config value for KEY."""
    value = ctx.obj["config"].get(key)
    click.echo(f"{key} = {value}")


@cli.command()
def permissions():
    """Check system permissions."""
    from .input import get_input_provider
    from .inspection import get_inspection_provider
    from .vision import get_vision_provider
    from .window import get_window_provider

    def _status(label, check):
        try:
            value = check()
            if not value:
                return (label, "FAIL")
            provider_label = getattr(value, "permission_label", None)
            if provider_label:
                return (label, f"OK ({provider_label})")
            return (label, "OK")
        except Exception as exc:
            return (label, f"FAIL ({exc})")

    checks = [
        ("Desktop", f"{detect_desktop().value}"),
        ("Screenshot", "REMOVED (use semantic state)"),
        _status("Input", get_input_provider),
        _status("Inspection", get_inspection_provider),
        _status("Window", get_window_provider),
        _status("Vision", get_vision_provider),
    ]
    for name, status in checks:
        click.echo(f"  {name}: {status}")


def _format_doctor_text(result):
    """Format doctor result as compact terminal text."""
    lines = []
    for check in result.checks:
        line = f"{check.capability}: {check.status.value} via {check.provider}"
        if check.smoke_tested:
            dims = check.evidence.get("dimensions")
            mode = check.evidence.get("mode")
            if dims and mode:
                line += f" smoke={dims} {mode}"
            else:
                line += " smoke=true"
        if check.message:
            line += f" — {check.message}"
        if check.fix_hint and check.status.value in ("WARN", "BLOCKED", "UNKNOWN"):
            line += f" fix={check.fix_hint}"
        lines.append(line)
    return "\n".join(lines)


@cli.command(name="doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
@click.option("--smoke", is_flag=True, help="Run safe runtime smoke checks")
@click.option("--capability", type=click.Choice(["desktop", "screenshot", "capture", "input", "window", "inspection", "vision", "mcp"]), help="Check one capability")
def doctor(as_json, smoke, capability):
    """Diagnose Linux/WSL compatibility by capability."""
    import json as json_module

    result = run_doctor(capability=capability, smoke=smoke)
    if as_json:
        click.echo(json_module.dumps(result.to_dict(), sort_keys=True))
    else:
        click.echo(_format_doctor_text(result))


@cli.command(name="compatibility")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
def compatibility(as_json):
    """Show compatibility matrix without active smoke checks."""
    import json as json_module

    result = run_doctor(smoke=False)
    if as_json:
        click.echo(json_module.dumps(result.to_dict(), sort_keys=True))
    else:
        click.echo(_format_doctor_text(result))


@cli.command()
@click.option("--port", default=3000, help="Port for SSE transport")
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "sse"]))
@click.option(
    "--safety-level",
    default=None,
    type=click.Choice(["strict", "normal", "permissive"]),
    help="Initial MCP SafetyGuard level",
)
@click.option(
    "--overlay",
    default=None,
    type=click.Choice(["auto", "noop", "tkinter"]),
    help="Enable GHOST approval overlay backend for MCP actions",
)
@click.option(
    "--audit-export",
    default=None,
    type=click.Path(),
    help="Default path used by the peekxd_audit_export MCP tool",
)
def mcp(port, transport, safety_level, overlay, audit_export):
    """Run MCP server."""
    from .mcp_server import create_mcp_server
    config = ConfigManager()
    config.set("mcp.transport", transport)
    config.set("mcp.port", port)
    if safety_level is not None:
        config.set("mcp.safety_level", safety_level)
    if overlay is not None:
        config.set("mcp.overlay", overlay)
    if audit_export is not None:
        config.set("mcp.audit_export", audit_export)
    server = create_mcp_server(config)
    if transport == "stdio":
        server.run(transport="stdio", show_banner=False)
    else:
        server.run(transport="sse", port=port, show_banner=False)


@cli.group()
def agent():
    """AI agent automation — See, Think, Act loop."""


@agent.command(name="run")
@click.argument("task")
@click.option("--max-steps", default=10, help="Maximum steps")
@click.option("--step-delay", default=1.0, help="Seconds between steps")
@click.option("--verbose", "-v", is_flag=True, help="Show step details")
@click.option("--safety", "safety_level", default="normal",
              type=click.Choice(["strict", "normal", "permissive"]),
              help="Safety level: strict=preview only, normal=confirm destructive, permissive=no checks")
@click.option("--no-memory", is_flag=True, help="Disable element position caching")
@click.option("--no-audit", is_flag=True, help="Disable action logging")
@click.option("--ghost", is_flag=True, help="Force GHOST mode: all actions as preview only (Softbox)")
@click.option("--ghost-overlay", is_flag=True, help="Show live overlay for GHOST actions (Softbox V3)")
@click.option("--ghost-overlay-timeout", default=5, type=int,
              help="Seconds before overlay auto-cancels (default: 5)")
@click.option("--ghost-overlay-backend", default="auto",
              type=click.Choice(["auto", "noop", "tkinter"]),
              help="Overlay backend (default: auto)")
@click.option("--ghost-approval-execution", is_flag=True, help="Allow approved, explicitly approvable GHOST actions to execute. Hard-blocked actions remain blocked. (Softbox V4)")
def agent_run(task, max_steps, step_delay, verbose, safety_level,
              no_memory, no_audit, ghost, ghost_overlay,
              ghost_overlay_timeout, ghost_overlay_backend, ghost_approval_execution):
    """Run a task autonomously: TASK_DESCRIPTION.

    Example: peekxd agent run "Open Firefox and go to github.com"
    """
    from .agent import AgentOrchestrator
    from .core.safety import SafetyLevel

    level_map = {"strict": SafetyLevel.STRICT, "normal": SafetyLevel.NORMAL,
                 "permissive": SafetyLevel.PERMISSIVE}

    def callback(step_type, data):
        if verbose or step_type in ("task_start", "task_done", "task_end", "error"):
            click.echo(f"  [{step_type}] {data}")

    orch = AgentOrchestrator(
        max_steps=max_steps,
        step_delay=step_delay,
        callback=callback,
        safety_level=level_map[safety_level],
        enable_memory=not no_memory,
        enable_audit=not no_audit,
        force_ghost=ghost,
        enable_ghost_overlay=ghost_overlay,
        ghost_overlay_timeout=ghost_overlay_timeout,
        ghost_overlay_backend=ghost_overlay_backend,
        enable_ghost_approval_execution=ghost_approval_execution,
    )
    result = orch.run_task(task)

    click.echo(f"\nResult: {'SUCCESS' if result.success else 'FAILED'}")
    click.echo(f"Steps: {result.steps_taken}")
    click.echo(f"Time: {result.elapsed_seconds:.1f}s")
    if result.summary:
        click.echo(f"\n{result.summary}")
    if result.errors:
        click.echo(f"\nErrors: {result.errors}")


@agent.command(name="tools")
def agent_tools():
    """List all available Hermes tool definitions (JSON)."""
    import json

    from .agent import get_hermes_tool_definitions
    tools = get_hermes_tool_definitions()
    click.echo(json.dumps(tools, indent=2))


@agent.command(name="mark")
@click.option("--output", "-o", type=click.Path(), help="Output path for marked image")
@click.option("--prompt", "-p", help="Custom element detection prompt")
def agent_mark(output, prompt):
    """Screenshot-backed element markup was removed; use semantic IDs."""
    del output, prompt
    _fail_removed_screenshot_path()


@cli.group()
def macro():
    """Action sequences — chain multiple actions."""


@macro.command(name="run")
@click.argument("steps_json")
@click.option("--stop-on-error", is_flag=True, default=True, help="Stop on first error")
def macro_run(steps_json, stop_on_error):
    """Run an action sequence from JSON.

    Example: peekxd macro run '[{"action":"click","params":{"x":100,"y":200}}]'
    """
    import json

    from .agent import ActionSequence

    steps = json.loads(steps_json)
    seq = ActionSequence.from_dict(steps)
    results = seq.execute(stop_on_error=stop_on_error)

    for r in results:
        status = "OK" if r["success"] else "FAIL"
        click.echo(f"  [{status}] {r['description']}: {r.get('detail', '')}")


@cli.command(name="wait-for")
@click.option("--element", "-e", help="Wait for element description")
@click.option("--text", "-t", help="Wait for text to appear")
@click.option("--stable", "-s", is_flag=True, help="Wait for screen to stabilize")
@click.option("--change", "-c", is_flag=True, help="Wait for screen to change")
@click.option("--timeout", default=10.0, help="Timeout in seconds")
def wait_for(element, text, stable, change, timeout):
    """Wait for a condition on screen."""
    from .agent.actions import WaitCondition

    if element:
        result = WaitCondition.for_element(element, timeout)
        if result["found"]:
            click.echo(f"Found '{element}' at {result['position']} ({result['elapsed']}s)")
        else:
            click.echo(f"Timeout waiting for element: {element}")
    elif text:
        result = WaitCondition.for_text(text, timeout)
        if result["found"]:
            click.echo(f"Found text '{text}' ({result['elapsed']}s)")
        else:
            click.echo(f"Timeout waiting for text: {text}")
    elif stable or change:
        _fail_removed_screenshot_path()
    else:
        click.echo("Error: Specify --element, --text, --stable, or --change")


@cli.group()
def safety():
    """Safety guardrails and preview mode."""


@safety.command(name="check")
@click.argument("action")
@click.argument("params_json", default="{}")
def safety_check(action, params_json):
    """Check if an action would pass safety checks."""
    import json

    from .core.safety import SafetyGuard, SafetyLevel

    guard = SafetyGuard(SafetyLevel.NORMAL)
    params = json.loads(params_json)
    try:
        guard.check_action(action, params)
        click.echo("SAFE: Action passes safety checks")
    except Exception as e:
        click.echo(f"BLOCKED: {e}")


@safety.command(name="preview")
@click.argument("action")
@click.argument("params_json", default="{}")
def safety_preview(action, params_json):
    """Preview what an action would do (dry-run, no execution)."""
    import json

    from .core.safety import DryRunExecutor

    dry = DryRunExecutor()
    params = json.loads(params_json)
    result = dry.execute(action, params)
    click.echo(dry.summary())


@safety.command(name="decide")
@click.argument("action")
@click.argument("params_json", default="{}")
@click.option("--entry-point", default="cli",
              help="Calling surface: cli|macro|mcp|orchestrator|bridge")
@click.option("--json-output", "as_json", is_flag=True,
              help="Emit the SafetyDecision as JSON")
@click.option("--confirmable/--no-confirmable", default=False,
              help="Route zero-risk approvable actions to the "
                   "confirmable-ghost approval flow (Softbox V4)")
def safety_decide(action, params_json, entry_point, as_json, confirmable):
    """Obtain the canonical SafetyDecision for an action (no execution).

    This is the single policy boundary: every entry point must consume
    this decision rather than duplicating policy logic.
    """
    import json as _json

    from .core.decision import get_gate

    params = _json.loads(params_json) if params_json else {}
    from .core.decision import SafetyDecisionGate
    gate = SafetyDecisionGate(confirmable=confirmable) if confirmable else get_gate()
    decision = gate.evaluate(action, params, entry_point=entry_point)
    if as_json:
        click.echo(_json.dumps(decision.to_dict(), indent=2))
        return
    click.echo(
        f"decision_id={decision.decision_id}\n"
        f"zone={decision.zone} classification={decision.ghost_classification}\n"
        f"policy={decision.policy_result} "
        f"approval_state={decision.required_approval_state}\n"
        f"expiry={decision.expiry} nonce={decision.execution_nonce[:8]}…\n"
        f"correlation={decision.evidence_correlation_id}\n"
        f"reason={decision.reason}"
    )


@safety.command(name="approve")
@click.argument("decision_id")
@click.option("--json-output", "as_json", is_flag=True)
def safety_approve(decision_id, as_json):
    """Approve a pending APPROVABLE_GHOST decision (permits ONE execution)."""
    import json as _json

    from .core.decision import ApprovalStore, DecisionStateError

    store = ApprovalStore()
    try:
        rec = store.approve(decision_id)
    except DecisionStateError as exc:
        click.echo(f"REJECTED: {exc}")
        raise SystemExit(1)
    if as_json:
        click.echo(_json.dumps(rec, indent=2))
        return
    click.echo(f"APPROVED: {decision_id} (single-use; expires {rec.get('expiry')})")


@safety.command(name="deny")
@click.argument("decision_id")
def safety_deny(decision_id):
    """Deny a pending decision — executes nothing."""
    from .core.decision import ApprovalStore, DecisionStateError

    try:
        ApprovalStore().deny(decision_id)
        click.echo(f"DENIED: {decision_id}")
    except DecisionStateError as exc:
        click.echo(f"REJECTED: {exc}")
        raise SystemExit(1)


@safety.command(name="status")
@click.argument("decision_id", required=False)
def safety_status_cmd(decision_id):
    """Show approval-ledger state for a decision (or recent ones)."""
    from .core.decision import ApprovalStore

    store = ApprovalStore()
    if decision_id:
        rec = store.load(decision_id)
        if rec is None:
            click.echo("UNKNOWN decision")
            raise SystemExit(1)
        click.echo(json.dumps(rec, indent=2))
        return
    import glob as _glob
    import time as _time
    recs = []
    for p in _glob.glob(str(store._dir / "*.json")):
        try:
            recs.append(json.loads(Path(p).read_text()))
        except Exception:
            continue  # skip unreadable records in the listing
    # Most recent first (created_at), not glob-hex order: with large ledgers
    # the hex window hides the decisions an operator/adapter actually needs.
    recs.sort(key=lambda r: float(r.get("created_at") or 0.0), reverse=True)
    rows = []
    for rec in recs[:10]:
        age = max(0.0, _time.time() - float(rec.get("created_at") or 0.0))
        rows.append(f"{rec['decision_id']}  "
                    f"{rec.get('approval_state'):9s}  {rec.get('action')}"
                    f"  ({age:.0f}s ago)")
    click.echo("\n".join(rows) or "no decisions recorded")


@cli.command()
@click.option("--max-age", default=24.0, help="Max age in hours")
@click.option("--max-files", default=100, help="Max files to keep")
def cleanup(max_age, max_files):
    """Clean up old peekxd temporary files."""
    from .core.cleanup import cleanup_now
    stats = cleanup_now(max_age_hours=max_age, max_files=max_files)
    click.echo(f"Cleaned {stats['cleaned']} files ({stats['bytes_freed']} bytes)")
    click.echo(f"Remaining: {stats['remaining']} files")


@cli.group()
def audit():
    """Audit trail and session history."""


@audit.command(name="show")
def audit_show():
    """Show current session audit trail."""
    from .core.audit import get_logger
    logger = get_logger()
    click.echo(logger.format_readable())


@audit.command(name="export")
@click.argument("output_path", required=False)
def audit_export(output_path):
    """Export audit trail to JSON."""
    from .core.audit import get_logger
    path = get_logger().export_json(output_path)
    click.echo(f"Audit exported to: {path}")


@audit.command(name="summary")
def audit_summary():
    """Show audit session summary."""
    from .core.audit import get_logger
    summary = get_logger().get_session_summary()
    click.echo(f"Session: {summary['session_id']}")
    click.echo(f"Actions: {summary['total_actions']} ({summary['successful']} OK, {summary['failed']} failed)")
    click.echo(f"Duration: {summary['elapsed_seconds']}s")


@cli.command()
def version():
    """Show version."""
    click.echo("peekxd-linux 0.3.0")


def main():
    """Entry point."""
    try:
        cli()
    except peekxdError as e:
        click.echo(f"Error: {e.message}", err=True)
        if e.details:
            click.echo(f"Details: {e.details}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nAborted.", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
