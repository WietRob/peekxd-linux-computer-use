"""Vision module for peekxd Linux.

Provides unified image analysis across multiple AI vision providers:
OpenAI GPT-4o, Anthropic Claude, and local Ollama models.
"""

from peekxd.vision.base import VisionProvider
from peekxd.vision.hermes import HermesVisionProvider
from peekxd.vision.openai import OpenAIVisionProvider
from peekxd.vision.anthropic import AnthropicVisionProvider
from peekxd.vision.ollama import OllamaVisionProvider
from peekxd.vision.detector import get_vision_provider

__all__ = [
    "VisionProvider",
    "HermesVisionProvider",
    "OpenAIVisionProvider",
    "AnthropicVisionProvider",
    "OllamaVisionProvider",
    "get_vision_provider",
]
