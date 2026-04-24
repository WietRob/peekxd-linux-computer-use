"""Base vision provider interface for peekxd Linux."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple


class VisionProvider(ABC):
    """Abstract base class for vision providers.

    All vision providers must implement these methods to support image
    analysis, element location, and question answering capabilities.
    """

    @abstractmethod
    def analyze(self, image_path: str, prompt: str) -> str:
        """Analyze an image with a given prompt.

        Args:
            image_path: Path to the image file.
            prompt: Text prompt describing what to analyze.

        Returns:
            The model's response as a string.
        """
        ...

    @abstractmethod
    def find_element(self, image_path: str, description: str) -> Optional[Tuple[int, int]]:
        """Find an element described by text within an image.

        Args:
            image_path: Path to the image file.
            description: Description of the element to locate.

        Returns:
            (x, y) tuple of element center coordinates, or None if not found.
        """
        ...

    @abstractmethod
    def answer_question(self, image_path: str, question: str) -> str:
        """Answer a question about an image.

        Args:
            image_path: Path to the image file.
            question: Question about the image content.

        Returns:
            The model's answer as a string.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name identifier."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Return True if the provider is available (API key set, service reachable)."""
        ...
