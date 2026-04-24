"""Anthropic Claude Vision provider for peekxd Linux."""

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


def _get_media_type(image_path: str) -> str:
    """Determine the media type from file extension."""
    ext = os.path.splitext(image_path)[1].lower()
    if ext == ".png":
        return "image/png"
    elif ext == ".gif":
        return "image/gif"
    elif ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    elif ext == ".webp":
        return "image/webp"
    return "image/png"


class AnthropicVisionProvider(VisionProvider):
    """Anthropic Claude Vision provider for image analysis."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("ANTHROPIC_VISION_MODEL", "claude-3-opus-latest")
        self._client = None

    def _get_client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise VisionError(
                    "Anthropic package not installed. Install it: pip install anthropic"
                ) from exc
            self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        return self._client

    def analyze(self, image_path: str, prompt: str) -> str:
        """Analyze an image using Anthropic Claude Vision.

        Args:
            image_path: Path to the image file.
            prompt: Text prompt describing what to analyze.

        Returns:
            The model's response as a string.

        Raises:
            VisionError: If the API call fails.
        """
        try:
            client = self._get_client()
            base64_image = _encode_image(image_path)
            media_type = _get_media_type(image_path)
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return response.content[0].text
        except Exception as exc:
            raise VisionError(f"Anthropic vision analysis failed: {exc}") from exc

    def find_element(self, image_path: str, description: str) -> Optional[Tuple[int, int]]:
        """Find an element described by text within an image.

        Asks the model to return coordinates as JSON: ``{"x": N, "y": N}``.

        Args:
            image_path: Path to the image file.
            description: Description of the element to locate.

        Returns:
            (x, y) tuple of element center coordinates, or None if not found.

        Raises:
            VisionError: If the API call or JSON parsing fails.
        """
        prompt = (
            f"Find the location of this element on the screen: {description}\n"
            'Return ONLY a JSON object with "x" and "y" integer coordinates, '
            'e.g. {"x": 100, "y": 200}. If not found, return {"x": -1, "y": -1}.'
        )
        try:
            result = self.analyze(image_path, prompt)
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
                f"Failed to parse coordinates from Anthropic response: {exc}"
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
        return "anthropic"

    @property
    def available(self) -> bool:
        """Check if Anthropic API key is set and the package is importable."""
        if "ANTHROPIC_API_KEY" not in os.environ:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False
