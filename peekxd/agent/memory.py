"""Session memory for peekxd Linux.

Provides persistent context across tasks:
- Cached element positions ("Submit button was at 500,400 last time")
- Screen state history
- Task outcomes
- Element fingerprints for re-identification
"""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.utils import get_cache_dir


@dataclass
class ElementMemory:
    """Remembered element with position and context."""

    description: str
    position: Tuple[int, int]
    size: Tuple[int, int]
    confidence: float = 1.0
    last_seen: float = field(default_factory=time.time)
    hit_count: int = 1
    source: str = "vision"  # vision, atspi, manual
    screenshot_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.last_seen

    @property
    def is_fresh(self, threshold_hours: float = 1.0) -> bool:
        return self.age_seconds < threshold_hours * 3600


class AgentMemory:
    """Session memory for the peekxd agent.

    Remembers element positions, screen states, and task outcomes
    to improve subsequent interactions.

    Example:
        memory = AgentMemory()

        # After finding an element
        memory.remember_element("Submit button", (500, 400), (80, 30))

        # Later: get cached position (with freshness check)
        pos = memory.recall_element("Submit button")
        if pos:
            # Use cached position
            input.click(pos[0], pos[1])
        else:
            # Re-find with vision
            ...
    """

    def __init__(self, session_id: Optional[str] = None, persist: bool = False):
        self.session_id = session_id or f"mem_{int(time.time())}"
        self.elements: Dict[str, ElementMemory] = {}
        self.screen_history: List[Dict[str, Any]] = []
        self.task_results: List[Dict[str, Any]] = []
        self._persist = persist
        self._cache_path = get_cache_dir() / "memory" / f"{self.session_id}.json"

        if persist:
            self._load()

    # --- Element Memory ---

    def remember_element(
        self,
        description: str,
        position: Tuple[int, int],
        size: Tuple[int, int] = (0, 0),
        confidence: float = 1.0,
        source: str = "vision",
        screenshot_hash: str = "",
    ):
        """Store or update an element's position.

        Args:
            description: Human-readable element description.
            position: (x, y) coordinates.
            size: (width, height) in pixels.
            confidence: Detection confidence 0.0-1.0.
            source: How the element was found (vision, atspi, manual).
            screenshot_hash: Hash of the screen when element was found.
        """
        key = self._normalize_key(description)

        if key in self.elements:
            # Update existing
            existing = self.elements[key]
            existing.position = position
            existing.size = size
            existing.confidence = confidence
            existing.last_seen = time.time()
            existing.hit_count += 1
            existing.source = source
            if screenshot_hash:
                existing.screenshot_hash = screenshot_hash
        else:
            # Create new
            self.elements[key] = ElementMemory(
                description=description,
                position=position,
                size=size,
                confidence=confidence,
                source=source,
                screenshot_hash=screenshot_hash,
            )

    def recall_element(
        self,
        description: str,
        max_age_hours: float = 1.0,
        min_confidence: float = 0.5,
    ) -> Optional[Tuple[int, int]]:
        """Recall a previously found element's position.

        Args:
            description: Element description to look up.
            max_age_hours: Maximum age for cached position to be valid.
            min_confidence: Minimum confidence threshold.

        Returns:
            (x, y) tuple if found and fresh, None otherwise.
        """
        key = self._normalize_key(description)
        elem = self.elements.get(key)

        if elem is None:
            return None
        if elem.confidence < min_confidence:
            return None
        if elem.age_seconds > max_age_hours * 3600:
            return None

        return elem.position

    def recall_with_fallback(
        self,
        description: str,
        find_fn: callable,
        max_age_hours: float = 1.0,
    ) -> Optional[Tuple[int, int]]:
        """Try cached position first, fall back to find function.

        This is the primary method — it uses memory when available
        and only calls the (expensive) vision model when needed.

        Args:
            description: Element to find.
            find_fn: Function that finds the element (e.g., vision.find_element).
            max_age_hours: Cache validity.

        Returns:
            (x, y) coordinates or None.
        """
        cached = self.recall_element(description, max_age_hours)
        if cached:
            return cached

        # Cache miss — use finder
        result = find_fn(description)
        if result:
            self.remember_element(description, result)
        return result

    def forget_element(self, description: str):
        """Remove an element from memory."""
        key = self._normalize_key(description)
        self.elements.pop(key, None)

    def get_all_elements(self) -> List[ElementMemory]:
        """Return all remembered elements, sorted by recency."""
        return sorted(self.elements.values(), key=lambda e: e.last_seen, reverse=True)

    def recall_similar(self, description: str) -> List[ElementMemory]:
        """Find elements with similar descriptions."""
        words = set(description.lower().split())
        matches = []
        for elem in self.elements.values():
            elem_words = set(elem.description.lower().split())
            overlap = len(words & elem_words)
            if overlap > 0:
                matches.append((overlap, elem))
        matches.sort(key=lambda x: -x[0])
        return [m[1] for m in matches[:5]]

    # --- Screen State History ---

    def record_screen(self, screenshot_path: str, analysis: str = ""):
        """Record a screen state snapshot."""
        entry = {
            "timestamp": time.time(),
            "screenshot_path": screenshot_path,
            "analysis": analysis,
        }
        self.screen_history.append(entry)
        # Keep only last 20
        if len(self.screen_history) > 20:
            self.screen_history = self.screen_history[-20:]

    def last_screen(self) -> Optional[Dict[str, Any]]:
        """Get the most recent screen state."""
        return self.screen_history[-1] if self.screen_history else None

    # --- Task Results ---

    def record_task(self, task: str, success: bool, summary: str = ""):
        """Record a completed task outcome."""
        self.task_results.append({
            "task": task,
            "success": success,
            "summary": summary,
            "timestamp": time.time(),
        })
        if len(self.task_results) > 50:
            self.task_results = self.task_results[-50:]

    def similar_tasks(self, task: str) -> List[Dict[str, Any]]:
        """Find previously completed similar tasks."""
        words = set(task.lower().split())
        matches = []
        for tr in self.task_results:
            tr_words = set(tr["task"].lower().split())
            overlap = len(words & tr_words)
            if overlap > len(words) * 0.3:  # 30% word overlap
                matches.append(tr)
        return matches[:3]

    # --- Persistence ---

    def save(self):
        """Save memory to disk."""
        if not self._persist:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "elements": {k: v.to_dict() for k, v in self.elements.items()},
            "screen_history": self.screen_history[-10:],
            "task_results": self.task_results[-20:],
        }
        with open(self._cache_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self):
        """Load memory from disk."""
        if not self._cache_path.exists():
            return
        try:
            with open(self._cache_path) as f:
                data = json.load(f)
            for key, edata in data.get("elements", {}).items():
                self.elements[key] = ElementMemory(**edata)
            self.screen_history = data.get("screen_history", [])
            self.task_results = data.get("task_results", [])
        except (json.JSONDecodeError, TypeError):
            pass

    # --- Utilities ---

    @staticmethod
    def _normalize_key(description: str) -> str:
        """Normalize element description for consistent lookup."""
        return hashlib.md5(description.lower().strip().encode()).hexdigest()[:16]

    def summary(self) -> str:
        """Human-readable memory summary."""
        fresh = sum(1 for e in self.elements.values() if e.is_fresh)
        lines = [
            f"Memory: {len(self.elements)} elements ({fresh} fresh), "
            f"{len(self.screen_history)} screens, {len(self.task_results)} tasks"
        ]
        for elem in list(self.elements.values())[:10]:
            age_m = elem.age_seconds / 60
            lines.append(f"  [{elem.description[:40]}] at {elem.position} ({age_m:.0f}m ago)")
        return "\n".join(lines)
