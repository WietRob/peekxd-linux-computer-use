"""OpenAI-compatible vision provider for local runtimes (llama.cpp / ODS).

The canonical local model route on this machine is the llama.cpp server
(OpenAI-compatible ``/v1/chat/completions``) serving the accepted Qwen3.8
multimodal GGUF. It requires no API key and exposes no Ollama-style
``/api/tags``, so neither the OpenAI nor the Ollama provider detects it.

Configuration:
- ``OPENAI_COMPAT_BASE_URL`` (default ``http://127.0.0.1:11434/v1``)
- ``OPENAI_COMPAT_VISION_MODEL``
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from peekxd.core.errors import VisionError
from peekxd.vision.base import VisionProvider


def _encode_image(image_path: str) -> str:
    mime = (
        "image/png" if image_path.lower().endswith(".png")
        else "image/webp" if image_path.lower().endswith(".webp")
        else "image/jpeg"
    )
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class OpenAICompatVisionProvider(VisionProvider):
    """Vision via any local OpenAI-compatible chat endpoint (llama.cpp/ODS)."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or os.environ.get(
            "OPENAI_COMPAT_VISION_MODEL", "local-vision"
        )
        self.base_url = (
            base_url
            or os.environ.get("OPENAI_COMPAT_BASE_URL", "http://127.0.0.1:11434/v1")
        ).rstrip("/")

    @property
    def name(self) -> str:
        """Return the provider name identifier."""
        return "openai-compat"

    @property
    def available(self) -> bool:
        try:
            import requests
        except ImportError:
            return False
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=2)
            if resp.status_code != 200:
                return False
            models = resp.json().get("data", [])
            return bool(models)
        except Exception:
            return False

    def analyze(self, image_path: str, prompt: str) -> str:
        import requests

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": _encode_image(image_path)},
                            },
                        ],
                    }
                ],
                "max_tokens": 512,
            },
            timeout=180,
        )
        resp.raise_for_status()
        choices = resp.json().get("choices", [])
        if not choices:
            raise VisionError("empty response from vision endpoint")
        return choices[0].get("message", {}).get("content", "")

    def find_element(self, image_path: str, description: str) -> Optional[tuple]:
        """Ask the multimodal model for element coordinates."""
        prompt = (
            f"Locate '{description}' in this screenshot. Reply ONLY with JSON "
            '{{"x": <int>, "y": <int>}} for the center coordinates, '
            'or {"x": null, "y": null} if not present.'
        )
        text = self.analyze(image_path, prompt).strip()
        import json as _json

        # Accept several model answer shapes: {"x":..,"y":..}, a list of
        # {"bbox_2d":[x1,y1,x2,y2]} objects, or plain JSON wrapped in fences.
        candidates: list = []
        try:
            candidates.append(
                _json.loads(text[text.find("{"):text.rfind("}") + 1]))
        except Exception:
            pass
        try:
            candidates.append(
                _json.loads(text[text.find("["):text.rfind("]") + 1]))
        except Exception:
            pass
        for data in candidates:
            if isinstance(data, list):
                data = data[0] if data else {}
            if not isinstance(data, dict):
                continue
            if data.get("x") is not None and data.get("y") is not None:
                return (int(data["x"]), int(data["y"]))
            bbox = data.get("bbox_2d")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                x = int((float(bbox[0]) + float(bbox[2])) / 2)
                y = int((float(bbox[1]) + float(bbox[3])) / 2)
                return (x, y)
        return None

    def answer_question(self, image_path: str, question: str) -> str:
        return self.analyze(image_path, question)
