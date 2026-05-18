"""Hermes native vision provider for peekxd Linux.

This provider reuses the local Hermes Agent vision tool instead of talking to
OpenAI/Anthropic directly. It lets peekxd benefit from whichever auxiliary
vision backend Hermes is configured to use (Codex/OpenRouter/Nous/custom/etc.)
without requiring a separate API key in the peekxd environment.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from peekxd.core.errors import VisionError
from peekxd.vision.base import VisionProvider


class HermesVisionProvider(VisionProvider):
    """Vision provider backed by Hermes Agent's ``vision_analyze_tool``."""

    def __init__(self, model: Optional[str] = None, hermes_agent_dir: Optional[str] = None):
        self.model = model or os.environ.get("HERMES_VISION_MODEL")
        self.hermes_agent_dir = hermes_agent_dir

    def _hermes_agent_dir(self) -> Path:
        """Return the local Hermes Agent checkout/import directory."""
        configured = self.hermes_agent_dir or os.environ.get("PEEKXD_HERMES_AGENT_DIR")
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".hermes" / "hermes-agent"

    def _vision_tools_path(self) -> Path:
        return self._hermes_agent_dir() / "tools" / "vision_tools.py"

    def _call_hermes(self, image_path: str, prompt: str) -> str:
        """Call Hermes' vision tool and return its analysis text."""
        agent_dir = self._hermes_agent_dir()
        if not self._vision_tools_path().is_file():
            raise VisionError(
                "Hermes Agent vision tools not found. Set PEEKXD_HERMES_AGENT_DIR "
                "to the Hermes Agent checkout."
            )

        agent_dir_str = str(agent_dir)
        inserted = False
        if agent_dir_str not in sys.path:
            sys.path.insert(0, agent_dir_str)
            inserted = True

        try:
            from tools.vision_tools import vision_analyze_tool

            async def _run() -> str:
                return await vision_analyze_tool(
                    image_url=image_path,
                    user_prompt=prompt,
                    model=self.model,
                )

            try:
                raw = asyncio.run(_run())
            except RuntimeError as exc:
                # This provider is synchronous. If a caller embeds peekxd inside
                # an already-running event loop, make the failure explicit rather
                # than silently deadlocking or nesting loops.
                if "asyncio.run() cannot be called" in str(exc):
                    raise VisionError(
                        "Hermes vision provider cannot run inside an existing "
                        "asyncio event loop; call it from a sync context."
                    ) from exc
                raise

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise VisionError(f"Hermes vision returned invalid JSON: {raw[:200]}") from exc

            if not payload.get("success"):
                raise VisionError(payload.get("analysis") or "Hermes vision analysis failed")
            return payload.get("analysis", "") or ""
        except VisionError:
            raise
        except Exception as exc:
            raise VisionError(f"Hermes vision analysis failed: {exc}") from exc
        finally:
            if inserted:
                try:
                    sys.path.remove(agent_dir_str)
                except ValueError:
                    pass

    def analyze(self, image_path: str, prompt: str) -> str:
        """Analyze an image using Hermes Agent's configured vision backend."""
        return self._call_hermes(image_path, prompt)

    def find_element(self, image_path: str, description: str) -> Optional[Tuple[int, int]]:
        """Find an element described by text within an image."""
        prompt = (
            f"Find the location of this element on the screen: {description}\n"
            'Return ONLY a JSON object with "x" and "y" integer coordinates, '
            'e.g. {"x": 100, "y": 200}. If not found, return {"x": -1, "y": -1}.'
        )
        try:
            result = self.analyze(image_path, prompt)
            text = result.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                text = "\n".join(lines)
            data = json.loads(text)
            x, y = int(data["x"]), int(data["y"])
            if x < 0 or y < 0:
                return None
            return (x, y)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise VisionError(f"Failed to parse coordinates from Hermes response: {exc}") from exc

    def answer_question(self, image_path: str, question: str) -> str:
        """Answer a question about an image."""
        return self.analyze(image_path, question)

    @property
    def name(self) -> str:
        return "hermes"

    @property
    def available(self) -> bool:
        """Return True when local Hermes Agent vision tools are importable."""
        return self._vision_tools_path().is_file()
