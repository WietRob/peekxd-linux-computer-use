"""Vision provider detector for peekxd Linux.

Automatically selects an available vision provider based on configuration
and environment variables.
"""

from typing import Optional

from peekxd.core.errors import ProviderNotAvailableError
from peekxd.vision.base import VisionProvider
from peekxd.vision.hermes import HermesVisionProvider
from peekxd.vision.openai import OpenAIVisionProvider
from peekxd.vision.anthropic import AnthropicVisionProvider
from peekxd.vision.ollama import OllamaVisionProvider


def get_vision_provider(provider_name: Optional[str] = None) -> VisionProvider:
    """Get the best available vision provider.

    If *provider_name* is given and that provider is available, it is
    returned.  Otherwise the function iterates through all known
    providers and returns the first one that reports ``available``.

    Args:
        provider_name: Optional provider name override (``"openai"``,
            ``"anthropic"``, or ``"ollama"``).

    Returns:
        A :class:`VisionProvider` instance ready for use.

    Raises:
        ProviderNotAvailableError: If the requested provider is not
            available or no provider can be found.
    """
    providers = {
        "hermes": HermesVisionProvider(),
        "openai": OpenAIVisionProvider(),
        "anthropic": AnthropicVisionProvider(),
        "ollama": OllamaVisionProvider(),
    }

    if provider_name and provider_name in providers:
        if providers[provider_name].available:
            return providers[provider_name]
        raise ProviderNotAvailableError(
            f"Vision provider '{provider_name}' not available."
        )

    for name, provider in providers.items():
        if provider.available:
            return provider

    raise ProviderNotAvailableError(
        "No vision provider available. "
        "Install/configure Hermes Agent, set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
        "or ensure Ollama is running."
    )
