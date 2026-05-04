"""Agent orchestrator for peekxd Linux.

Implements a See → Think → Act loop for autonomous task execution.
The orchestrator can run tasks by capturing the screen, analyzing it,
planning actions, and executing them — repeating until the task is done.
"""

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core.errors import peekxdError
from ..core.safety import SafetyGuard, SafetyLevel
from ..core.audit import AuditLogger
from ..core.cleanup import CleanupManager
from .actions import ActionSequence
from .function_calling import RobustJSONParser
from .hermes_tools import execute_hermes_action, get_hermes_tool_definitions
from .memory import AgentMemory


@dataclass
class TaskResult:
    """Result of an orchestrated task execution."""

    success: bool
    steps_taken: int
    actions_executed: List[Dict[str, Any]]
    final_screenshot: Optional[str] = None
    summary: str = ""
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "steps_taken": self.steps_taken,
            "actions_executed": self.actions_executed,
            "final_screenshot": self.final_screenshot,
            "summary": self.summary,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "errors": self.errors,
        }


class AgentOrchestrator:
    """High-level orchestrator for autonomous desktop automation.

    Implements the See → Think → Act loop:
    1. SEE: Capture and analyze the current screen state
    2. THINK: Plan the next action(s) based on the analysis
    3. ACT: Execute the planned action(s)
    4. Repeat until task is complete or max steps reached

    Example:
        orch = AgentOrchestrator(max_steps=10)
        result = orch.run_task("Open Firefox and navigate to github.com")
    """

    def __init__(
        self,
        max_steps: int = 20,
        step_delay: float = 1.0,
        vision_provider=None,
        screenshot_provider=None,
        input_provider=None,
        window_provider=None,
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        safety_level: SafetyLevel = SafetyLevel.NORMAL,
        enable_memory: bool = True,
        enable_audit: bool = True,
        enable_cleanup: bool = True,
        force_ghost: bool = False,
        enable_ghost_overlay: bool = False,
        ghost_overlay_timeout: int = 5,
        ghost_overlay_backend: Optional[str] = None,
        enable_ghost_approval_execution: bool = False,
    ):
        """Initialize the orchestrator.

        Args:
            max_steps: Maximum number of See→Think→Act iterations.
            step_delay: Seconds to wait between steps.
            vision_provider: Optional vision provider override.
            screenshot_provider: Optional screenshot provider override.
            input_provider: Optional input provider override.
            window_provider: Optional window provider override.
            callback: Optional callback fn(step_type, data) for each step.
            safety_level: Safety guard level (strict/normal/permissive).
            enable_memory: Whether to use element position caching.
            enable_audit: Whether to log all actions.
            enable_cleanup: Whether to clean up temp files after run.
            force_ghost: If True, ALL actions are forced to GHOST zone (preview only).
            enable_ghost_overlay: If True, show a live overlay for GHOST actions.
            ghost_overlay_timeout: Seconds before overlay auto-cancels.
            ghost_overlay_backend: Override overlay backend (auto/noop/tkinter).
            enable_ghost_approval_execution: If True, allow approved APPROVABLE_GHOST actions to execute (V4).
        """
        self.max_steps = max_steps
        self.step_delay = step_delay
        self._vision_prov = vision_provider
        self._screenshot_prov = screenshot_provider
        self._input_prov = input_provider
        self._window_prov = window_provider
        self._callback = callback
        self.safety = SafetyGuard(safety_level)
        self.memory = AgentMemory() if enable_memory else None
        self.audit = AuditLogger() if enable_audit else None
        self._cleanup = CleanupManager() if enable_cleanup else None
        if self._cleanup:
            self._cleanup.schedule(interval_minutes=30)
        self._parser = RobustJSONParser()
        self.force_ghost = force_ghost
        self.enable_ghost_overlay = enable_ghost_overlay
        self.ghost_overlay_timeout = ghost_overlay_timeout
        self.ghost_overlay_backend = ghost_overlay_backend
        self._overlay_controller = None
        self.enable_ghost_approval_execution = enable_ghost_approval_execution

    # --- Lazy providers ---

    def _get_vision(self):
        if self._vision_prov is None:
            from ..vision import get_vision_provider
            self._vision_prov = get_vision_provider()
        return self._vision_prov

    def _get_screenshot(self):
        if self._screenshot_prov is None:
            from ..screenshot import get_screenshot_provider
            self._screenshot_prov = get_screenshot_provider()
        return self._screenshot_prov

    def _get_input(self):
        if self._input_prov is None:
            from ..input import get_input_provider
            self._input_prov = get_input_provider()
        return self._input_prov

    def _get_window(self):
        if self._window_prov is None:
            from ..window import get_window_provider
            self._window_prov = get_window_provider()
        return self._window_prov

    # Use properties to avoid name conflicts
    @property
    def vision(self):
        return self._get_vision()

    @property
    def screenshot(self):
        return self._get_screenshot()

    @property
    def input(self):
        return self._get_input()

    @property
    def window(self):
        return self._get_window()

    def _get_overlay_controller(self):
        """Lazy-init the GhostOverlayController."""
        if self._overlay_controller is None:
            from ..core.overlay import GhostOverlayController
            self._overlay_controller = GhostOverlayController(
                backend_name=self.ghost_overlay_backend,
                timeout=self.ghost_overlay_timeout,
            )
        return self._overlay_controller

    def _should_route_shadow_to_confirmable_ghost(
        self, action: str, params: Dict[str, Any], zone_decision,
    ) -> bool:
        """Determine if a SHADOW-zone action should be routed to the
        confirmable-ghost overlay flow instead of executing directly.

        Returns True only when ALL of:
        - enable_ghost_overlay is True
        - enable_ghost_approval_execution is True
        - force_ghost is False
        - zone is SHADOW (caller should verify, but we check too)
        - action is in the approvable set (click, type, hotkey, etc.)
        - risk_factors are empty (safe action)
        """
        from ..core.zones import ZoneDecision, Zone

        # Feature flags must be enabled
        if not self.enable_ghost_overlay or not self.enable_ghost_approval_execution:
            return False
        # force_ghost must be off
        if self.force_ghost:
            return False
        # Zone must be SHADOW
        if zone_decision.zone != Zone.SHADOW:
            return False
        # Must have zero risk factors
        if zone_decision.risk_factors:
            return False
        # Action must be in the approvable set
        approvable = ZoneDecision._SHADOW_ACTIONS | ZoneDecision._LOW_RISK_ACTIONS | ZoneDecision._MODIFYING_ACTIONS
        if action.strip().lower() not in approvable:
            return False
        return True

    # --- Core Loop ---

    def run_task(self, task_description: str) -> TaskResult:
        """Execute a high-level task autonomously.

        This method implements the full See → Think → Act loop.
        It uses the vision model to understand the screen and decide actions.

        Args:
            task_description: Natural language description of the task.
                Examples: "Open the settings app and enable dark mode"
                          "Fill out the login form with username 'admin'"
                          "Take a screenshot and save it to the desktop"

        Returns:
            TaskResult with full execution details.
        """
        start_time = time.time()
        actions_log: List[Dict[str, Any]] = []
        errors: List[str] = []
        final_screenshot: Optional[str] = None

        self._notify("task_start", {"task": task_description})

        for step in range(self.max_steps):
            self._notify("step_start", {"step": step + 1, "of": self.max_steps})

            try:
                # === SEE ===
                screen_state = self._see()
                self._notify("see", {"screenshot": screen_state["path"], "description": screen_state["description"]})

                # === THINK ===
                plan = self._think(task_description, screen_state, actions_log, step)
                self._notify("think", {"plan": plan})

                # Check if task is complete
                if plan.get("done", False):
                    self._notify("task_done", {"reason": plan.get("reason", "Task complete")})
                    final_screenshot = screen_state["path"]
                    break

                # === ACT ===
                action_result = self._act(plan, screen_state)
                actions_log.append({
                    "step": step + 1,
                    "plan": plan,
                    "result": action_result,
                })
                self._notify("act", {"result": action_result})

                if action_result.get("screenshot_path"):
                    final_screenshot = action_result["screenshot_path"]

            except Exception as exc:
                error_msg = f"Step {step + 1} error: {exc}"
                errors.append(error_msg)
                self._notify("error", {"error": error_msg})

            if self.step_delay > 0:
                time.sleep(self.step_delay)

        else:
            # Max steps reached
            errors.append(f"Max steps ({self.max_steps}) reached")

        elapsed = time.time() - start_time

        # Generate summary
        summary = self._generate_summary(task_description, actions_log, errors)

        result = TaskResult(
            success=len(errors) == 0 or any(a.get("result", {}).get("success", False) for a in actions_log),
            steps_taken=len(actions_log),
            actions_executed=actions_log,
            final_screenshot=final_screenshot,
            summary=summary,
            elapsed_seconds=elapsed,
            errors=errors,
        )

        # Export audit trail
        if self.audit:
            audit_path = self.audit.export_json()
            result.summary += f"\nAudit trail: {audit_path}"

        # Cleanup temp files
        if self._cleanup:
            cleanup_stats = self._cleanup.run()
            result.summary += f"\nCleanup: {cleanup_stats['cleaned']} old files removed"

        self._notify("task_end", result.to_dict())
        return result

    def _see(self) -> Dict[str, Any]:
        """Capture and analyze the current screen.

        Returns:
            Dict with 'path' (screenshot), 'description' (AI analysis),
            and 'elements' (detected UI elements).
        """
        cap_path = os.path.join(tempfile.gettempdir(), f"orch_see_{int(time.time())}.png")
        self.screenshot.capture_screen(cap_path)

        # Quick analysis
        description = self.vision.analyze(
            cap_path,
            "Describe the current screen briefly. What application is active? "
            "What interactive elements (buttons, fields, links) are visible? "
            "List them with their approximate positions.",
        )

        # Record in memory and audit
        if self.memory:
            self.memory.record_screen(cap_path, description)
        if self.audit:
            self.audit.log_screenshot(cap_path, "orchestrator_see")

        return {
            "path": cap_path,
            "description": description,
        }

    def _think(
        self,
        task: str,
        screen_state: Dict[str, Any],
        history: List[Dict[str, Any]],
        step: int,
    ) -> Dict[str, Any]:
        """Plan the next action based on current state and task.

        Uses the vision model to decide what to do next. Returns a plan dict
        that the _act method can execute.

        The prompt includes:
        - The task description
        - Current screen description
        - Action history
        - Available tools
        """
        # Build context for the LLM
        history_summary = ""
        if history:
            recent = history[-5:]  # Last 5 actions
            history_summary = "Previous actions:\n"
            for h in recent:
                plan = h.get("plan", {})
                result = h.get("result", {})
                history_summary += f"  - {plan.get('action', '?')}: {result.get('detail', 'ok')}\n"

        prompt = f"""You are an AI agent controlling a Linux desktop. Your task: {task}

Current screen analysis:
{screen_state['description']}

{history_summary}
Step {step + 1} of {self.max_steps}.

Decide the SINGLE next action to progress toward the task.

IMPORTANT: For element interactions, FIRST use mark_elements to detect all UI elements with coordinates,
then use those coordinates for clicks. Only use element_description for click when you are confident
about the element's appearance.

Available actions:
- capture_screen: Take a screenshot
- mark_elements: Detect all UI elements with bounding boxes (USE THIS FIRST when unsure about coordinates)
- click: Click at x,y coordinates OR click an element by description
- type: Type text
- key: Press a key or hotkey
- scroll: Scroll in a direction
- focus_window: Focus a window by title
- wait: Wait briefly
- done: Mark task as complete

Respond with ONLY a JSON object:
{{
  "action": "click|type|key|scroll|capture_screen|mark_elements|focus_window|wait|done",
  "params": {{}},
  "reason": "why this action"
}}

If the task is complete, use action "done"."""

        try:
            response = self.vision.analyze(screen_state["path"], prompt)

            # Use robust parser instead of fragile manual extraction
            try:
                plan = self._parser.extract_with_retry(response, max_retries=1)
            except ValueError:
                # Fallback: capture screen and try again
                return {
                    "action": "capture_screen",
                    "params": {},
                    "reason": f"Failed to parse plan from vision response. Re-observing.",
                }

            # Validate required fields
            if "action" not in plan or not isinstance(plan["action"], str):
                plan["action"] = "capture_screen"
            if "params" not in plan or not isinstance(plan["params"], dict):
                plan["params"] = {}
            if "reason" not in plan:
                plan["reason"] = "No reason given"

            # Sanitize action name
            plan["action"] = plan["action"].strip().lower()

            return plan

        except Exception as exc:
            # Fallback: just capture screen and try again
            return {
                "action": "capture_screen",
                "params": {},
                "reason": f"Think-phase error: {exc}. Re-observing.",
            }

    def _act(self, plan: Dict[str, Any], screen_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a planned action with safety checks, zone assignment, and audit logging.

        V2 Softbox integration:
        - GHOST: Action is NOT executed — previewed and audited with executed=False.
        - SHADOW: Action IS executed with before/after snapshots. Audit includes
          zone="shadow", executed=True, screenshot_before/after, shadow metadata.
        - GUIDED/DIRECT: Legacy path, executed with normal guardrails.

        Args:
            plan: The plan dict from _think.
            screen_state: Current screen state.

        Returns:
            Action result dict.
        """
        action = plan.get("action", "")
        params = plan.get("params", {})

        if action == "done":
            return {"success": True, "detail": "Task marked complete", "done": True}

        # Determine zone via Softbox risk decision
        zone_decision = self.safety.check_zone(action, params)

        # force_ghost override: CLI --ghost forces ALL actions to GHOST
        if self.force_ghost:
            from ..core.zones import Zone, RiskDecision
            zone_decision = RiskDecision(
                zone=Zone.GHOST,
                risk_level="forced_preview",
                risk_factors=["force_ghost_enabled"],
                reason="GHOST mode forced via CLI/API --ghost flag",
            )

        # GHOST zone: preview, optionally execute after approval (V4)
        if zone_decision.zone.value == "ghost":
            from ..core.zones import ZoneDecision
            screenshot_path = screen_state.get("path") if screen_state else None
            preview = ZoneDecision.create_ghost_preview(
                action, params, zone_decision, screenshot_path=screenshot_path
            )
            preview_dict = preview.to_dict()

            # V3: Show live overlay if enabled
            overlay_decision_dict = None
            overlay_approved = False
            if self.enable_ghost_overlay:
                from ..core.overlay import OverlayRequest
                overlay_request = OverlayRequest(
                    action=action,
                    params=params,
                    preview=preview_dict,
                    screenshot_path=screenshot_path,
                    markup_path=preview.markup_path,
                    timeout_seconds=self.ghost_overlay_timeout,
                )
                overlay_ctrl = self._get_overlay_controller()
                overlay_decision = overlay_ctrl.show_preview(overlay_request)
                overlay_decision_dict = overlay_decision.to_dict()
                overlay_approved = overlay_decision.approved and not overlay_decision.cancelled and not overlay_decision.timed_out

            # V4: Classify ghost action and decide execution
            is_force_ghost = self.force_ghost
            ghost_classification = ZoneDecision.classify_ghost_action(
                action=action,
                params=params,
                risk_factors=zone_decision.risk_factors,
                force_ghost=is_force_ghost,
            )
            classification_dict = ghost_classification.to_dict()

            # Determine if execution is allowed
            should_execute = (
                self.enable_ghost_overlay
                and self.enable_ghost_approval_execution
                and ghost_classification.can_execute_after_approval
                and overlay_approved
                and not is_force_ghost
            )

            executed = False
            execution_result = None
            approval_execution_decision = {
                "classification": classification_dict,
                "enable_ghost_overlay": self.enable_ghost_overlay,
                "enable_ghost_approval_execution": self.enable_ghost_approval_execution,
                "overlay_approved": overlay_approved,
                "force_ghost": is_force_ghost,
                "should_execute": should_execute,
            }

            if should_execute:
                try:
                    execution_result = self._execute_action(action, params)
                    executed = True
                    approval_execution_decision["executed"] = True
                except Exception as exec_err:
                    execution_result = {"success": False, "detail": str(exec_err)}
                    executed = False
                    approval_execution_decision["executed"] = False
                    approval_execution_decision["execution_error"] = str(exec_err)
            else:
                approval_execution_decision["executed"] = False

            # Audit log
            if self.audit:
                audit_result = {"ghost_preview": preview_dict}
                if overlay_decision_dict is not None:
                    audit_result["overlay_decision"] = overlay_decision_dict
                audit_result["approval_execution_decision"] = approval_execution_decision
                self.audit.log_action(
                    action=action,
                    params=params,
                    result=audit_result,
                    zone=zone_decision.zone.value,
                    executed=executed,
                )

            # Build result
            if executed:
                result = {
                    "success": execution_result.get("success", True) if execution_result else True,
                    "ghost": True,
                    "blocked": False,
                    "executed": True,
                    "preview": preview_dict,
                    "approval_execution_decision": approval_execution_decision,
                    "detail": f"[GHOST-V4] Action '{action}' executed after approval (APPROVABLE_GHOST)",
                }
                if execution_result:
                    result.update({k: v for k, v in execution_result.items() if k not in ("success",)})
            else:
                result = {
                    "success": False,
                    "ghost": True,
                    "blocked": True,
                    "executed": False,
                    "preview": preview_dict,
                    "approval_execution_decision": approval_execution_decision,
                    "detail": f"[GHOST] Action '{action}' blocked. Reason: {zone_decision.reason}",
                }
            if overlay_decision_dict is not None:
                result["overlay_decision"] = overlay_decision_dict
            return result

        # SHADOW zone (V2): confirmable-ghost overlay OR normal shadow execution
        if zone_decision.zone.value == "shadow":
            # Safety check first
            try:
                self.safety.check_action(action, params)
            except Exception as safety_err:
                return {"success": False, "detail": str(safety_err), "blocked": True}

            # --- V4 Confirmable-Ghost Routing ---
            # If both overlay and approval-execution are enabled, and this is a
            # safe SHADOW action (zero risk factors, approvable action type, no
            # force_ghost), route through the overlay confirmation flow instead
            # of executing blindly.
            if self._should_route_shadow_to_confirmable_ghost(action, params, zone_decision):
                from ..core.zones import ZoneDecision as _ZD
                from ..core.overlay import OverlayRequest

                screenshot_path = screen_state.get("path") if screen_state else None
                preview = _ZD.create_ghost_preview(
                    action, params, zone_decision, screenshot_path=screenshot_path,
                )
                preview_dict = preview.to_dict()

                # Show overlay
                overlay_request = OverlayRequest(
                    action=action,
                    params=params,
                    preview=preview_dict,
                    screenshot_path=screenshot_path,
                    markup_path=preview.markup_path,
                    timeout_seconds=self.ghost_overlay_timeout,
                )
                overlay_ctrl = self._get_overlay_controller()
                overlay_decision = overlay_ctrl.show_preview(overlay_request)
                overlay_decision_dict = overlay_decision.to_dict()
                overlay_approved = (
                    overlay_decision.approved
                    and not overlay_decision.cancelled
                    and not overlay_decision.timed_out
                )

                # Classify — for SHADOW with zero risk factors this is APPROVABLE_GHOST
                ghost_classification = _ZD.classify_ghost_action(
                    action=action,
                    params=params,
                    risk_factors=zone_decision.risk_factors,
                    force_ghost=self.force_ghost,
                )
                classification_dict = ghost_classification.to_dict()

                # Determine execution
                should_execute = (
                    ghost_classification.can_execute_after_approval
                    and overlay_approved
                )
                executed = False
                execution_result = None
                approval_execution_decision = {
                    "classification": classification_dict,
                    "overlay_approved": overlay_approved,
                    "should_execute": should_execute,
                }

                if should_execute:
                    try:
                        execution_result = self._execute_action(action, params)
                        executed = True
                        approval_execution_decision["executed"] = True
                    except Exception as exec_err:
                        execution_result = {"success": False, "detail": str(exec_err)}
                        executed = False
                        approval_execution_decision["executed"] = False
                        approval_execution_decision["execution_error"] = str(exec_err)
                else:
                    approval_execution_decision["executed"] = False

                # Audit log
                if self.audit:
                    audit_result = {
                        "ghost_preview": preview_dict,
                        "overlay_decision": overlay_decision_dict,
                        "approval_execution_decision": approval_execution_decision,
                    }
                    self.audit.log_action(
                        action=action,
                        params=params,
                        result=audit_result,
                        zone="shadow_confirmable_ghost",
                        executed=executed,
                    )

                # Build result
                if executed:
                    result = {
                        "success": execution_result.get("success", True) if execution_result else True,
                        "ghost": True,
                        "blocked": False,
                        "executed": True,
                        "preview": preview_dict,
                        "overlay_decision": overlay_decision_dict,
                        "approval_execution_decision": approval_execution_decision,
                        "detail": f"[SHADOW-V4] Action '{action}' executed after approval (APPROVABLE_GHOST via SHADOW)",
                    }
                    if execution_result:
                        result.update({k: v for k, v in execution_result.items() if k not in ("success",)})
                else:
                    result = {
                        "success": False,
                        "ghost": True,
                        "blocked": True,
                        "executed": False,
                        "preview": preview_dict,
                        "overlay_decision": overlay_decision_dict,
                        "approval_execution_decision": approval_execution_decision,
                        "detail": f"[SHADOW-V4] Action '{action}' blocked. Overlay not approved or classification prevents execution.",
                    }
                return result

            # --- V2 Normal SHADOW execution (no confirmable-ghost overlay) ---
            # Memory lookup for click actions (same as non-shadow)
            resolved_params = dict(params)
            if action == "click" and "element_description" in resolved_params:
                desc = resolved_params["element_description"]
                if self.memory:
                    cached = self.memory.recall_element(desc, max_age_hours=0.5)
                    if cached:
                        resolved_params = {**resolved_params, "x": cached[0], "y": cached[1]}
                        del resolved_params["element_description"]

            # Setup ShadowRecorder
            from ..core.shadow import ShadowRecorder
            shadow_recorder = ShadowRecorder(
                capture_fn=lambda p: self.screenshot.capture_screen(p),
                get_screenshot_path_fn=lambda: self.audit.get_next_screenshot_path("shadow")
                if self.audit else f"/tmp/shadow_{int(time.time())}.png",
            )

            # Wrap execution: before snapshot → execute → after snapshot
            action_result, shadow_result = shadow_recorder.wrap(
                action_callable=lambda: self._execute_action(action, resolved_params),
                action=action,
                params=resolved_params,
                screen_state=screen_state,
            )

            # Update memory with element positions
            if action in ("click",) and self.memory and "x" in action_result:
                pos = (action_result.get("x", 0), action_result.get("y", 0))
                elem_desc = params.get("element_description", f"element_at_{pos}")
                self.memory.remember_element(elem_desc, pos, source="agent")

            # Always attach shadow metadata to action_result
            shadow_dict = shadow_result.to_dict()
            action_result["shadow"] = shadow_dict

            # Audit log with zone=shadow, executed=True, screenshot paths
            if self.audit:
                screenshot_before = shadow_result.before_snapshot.screenshot_path if shadow_result.before_snapshot else None
                screenshot_after = shadow_result.after_snapshot.screenshot_path if shadow_result.after_snapshot else None

                self.audit.log_action(
                    action=action,
                    params=resolved_params,
                    result=action_result,
                    zone=zone_decision.zone.value,
                    executed=True,
                    screenshot_before=screenshot_before,
                    screenshot_after=screenshot_after,
                )

            return action_result

        # Safety check (legacy, for non-ghost zones)
        try:
            self.safety.check_action(action, params)
        except Exception as safety_err:
            return {"success": False, "detail": str(safety_err), "blocked": True}

        # Check memory for element positions (for click actions)
        if action == "click" and "element_description" in params:
            desc = params["element_description"]
            if self.memory:
                cached = self.memory.recall_element(desc, max_age_hours=0.5)
                if cached:
                    # Use cached position, skip vision lookup
                    params = {**params, "x": cached[0], "y": cached[1]}
                    del params["element_description"]

        # Execute the action
        result = self._execute_action(action, params)

        # Update memory with element positions from result
        if action in ("click",) and self.memory and "x" in result:
            pos = (result.get("x", 0), result.get("y", 0))
            elem_desc = params.get("element_description", f"element_at_{pos}")
            self.memory.remember_element(elem_desc, pos, source="agent")

        # Audit log with zone and executed=True
        if self.audit:
            self.audit.log_action(
                action=action,
                params=params,
                result=result,
                zone=zone_decision.zone.value,
                executed=True,
            )

        return result

    def _execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch action to Hermes tool execution."""
        dispatch = {
            "capture_screen": lambda p: execute_hermes_action("peekxd_capture_screen", p).get("result", {}),
            "mark_elements": lambda p: execute_hermes_action("peekxd_mark_elements", p).get("result", {}),
            "click": lambda p: execute_hermes_action("peekxd_click", p).get("result", {}),
            "type": lambda p: execute_hermes_action("peekxd_type", p).get("result", {}),
            "type_text": lambda p: execute_hermes_action("peekxd_type", p).get("result", {}),
            "key": lambda p: execute_hermes_action("peekxd_key", p).get("result", {}),
            "scroll": lambda p: execute_hermes_action("peekxd_scroll", p).get("result", {}),
            "focus_window": lambda p: execute_hermes_action("peekxd_focus_window", p).get("result", {}),
            "list_windows": lambda p: execute_hermes_action("peekxd_list_windows", p).get("result", {}),
            "find_element": lambda p: execute_hermes_action("peekxd_find_element", p).get("result", {}),
        }

        handler = dispatch.get(action)
        if handler:
            return handler(params)

        if action == "wait":
            seconds = params.get("seconds", 1.0)
            time.sleep(seconds)
            return {"success": True, "detail": f"Waited {seconds}s"}

        return {"success": False, "detail": f"Unknown action: {action}"}

    def _notify(self, step_type: str, data: Dict[str, Any]):
        """Send a notification via the callback if set."""
        if self._callback:
            try:
                self._callback(step_type, data)
            except Exception:
                pass

    def _generate_summary(
        self, task: str, history: List[Dict[str, Any]], errors: List[str]
    ) -> str:
        """Generate a human-readable summary of the task execution."""
        parts = [f"Task: {task}"]
        parts.append(f"Steps executed: {len(history)}")

        if history:
            parts.append("Actions:")
            for h in history:
                plan = h.get("plan", {})
                action = plan.get("action", "?")
                reason = plan.get("reason", "")
                parts.append(f"  - {action}: {reason}")

        if errors:
            parts.append(f"Errors ({len(errors)}):")
            for e in errors:
                parts.append(f"  - {e}")

        success = len(errors) == 0
        parts.append(f"Result: {'SUCCESS' if success else 'PARTIAL SUCCESS'}")

        return "\n".join(parts)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for external LLM integration.

        Use this when you want to provide the tool schemas to an LLM
        and have the LLM decide which tools to call.
        """
        return get_hermes_tool_definitions()

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool by name.

        Use this when an external LLM has decided which tool to call.
        """
        return execute_hermes_action(tool_name, params)
