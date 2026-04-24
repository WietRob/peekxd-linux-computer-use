"""Agent module for peekxd Linux.

Provides high-level automation capabilities for AI agents:
- Screen analysis with bounding box markup
- Action sequences and macros
- Wait/retry logic for elements
- Screen diffing for change detection
- Hermes tool definitions for direct agent integration
"""

from .hermes_tools import get_hermes_tool_definitions, execute_hermes_action
from .orchestrator import AgentOrchestrator, TaskResult
from .actions import ActionSequence, WaitCondition, ScreenDiff
from .screen_markup import draw_bounding_boxes, analyze_screen_with_markup

__all__ = [
    "get_hermes_tool_definitions",
    "execute_hermes_action",
    "AgentOrchestrator",
    "TaskResult",
    "ActionSequence",
    "WaitCondition",
    "ScreenDiff",
    "draw_bounding_boxes",
    "analyze_screen_with_markup",
]
