"""Ollama local vision provider for peekxd Linux."""

import base64
import json
import os
from typing import Optional, Tuple

from peekxd.core.errors import VisionError
from peekxd.vision.base import VisionProvider


def _encode_image(image_path: str) -> str:
    """Encode an image file as a base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class OllamaVisionProvider(VisionProvider):
    """Ollama local vision provider for image analysis."""

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or os.environ.get("OLLAMA_VISION_MODEL", "llava")
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        # Remove trailing slash
        self.host = self.host.rstrip("/")

    def _request(self, image_path: str, prompt: str) -> str:
        """Send a generation request to the Ollama API.

        Args:
            image_path: Path to the image file.
            prompt: Text prompt for the model.

        Returns:
            The model's response string.

        Raises:
            VisionError: If the request fails.
        """
        try:
            import requests
        except ImportError as exc:
            raise VisionError(
                "requests package not installed. Install it: pip install requests"
            ) from exc

        try:
            base64_image = _encode_image(image_path)
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [base64_image],
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.exceptions.ConnectionError as exc:
            raise VisionError(
                f"Cannot connect to Ollama at {self.host}. Is it running?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise VisionError(
                f"Ollama request timed out after 120s"
            ) from exc
        except Exception as exc:
            raise VisionError(f"Ollama vision analysis failed: {exc}") from exc

    def analyze(self, image_path: str, prompt: str) -> str:
        """Analyze an image using a local Ollama vision model.

        Args:
            image_path: Path to the image file.
            prompt: Text prompt describing what to analyze.

        Returns:
            The model's response as a string.
        """
        return self._request(image_path, prompt)

    def find_element(self, image_path: str, description: str) -> Optional[Tuple[int, int]]:
        """Find an element described by text within an image.

        Asks the model to return coordinates as JSON: ``{"x": N, "y": N}``.

        Args:
            image_path: Path to the image file.
            description: Description of the element to locate.

        Returns:
            (x, y) tuple of element center coordinates, or None if not found.

        Raises:
            VisionError: If the request or JSON parsing fails.
        """
        prompt = (
            f"Find the location of this element on the screen: {description}\n"
            'Return ONLY a JSON object with "x" and "y" integer coordinates, '
            'e.g. {"x": 100, "y": 200}. If not found, return {"x": -1, "y": -1}.'
        )
        try:
            result = self._request(image_path, prompt)
            # Extract JSON from the response (handle markdown code blocks)
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
            raise VisionError(
                f"Failed to parse coordinates from Ollama response: {exc}"
            ) from exc

    def answer_question(self, image_path: str, question: str) -> str:
        """Answer a question about an image.

        Args:
            image_path: Path to the image file.
            question: Question about the image content.

        Returns:
            The model's answer as a string.
        """
        return self.analyze(image_path, question)

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            import requests  # noqa: F401
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            resp = requests.get(f"{host}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False
