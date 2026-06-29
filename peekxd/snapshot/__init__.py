"""Snapshot storage and detection scaffolding for semantic computer use."""

from .detector import HybridDetector
from .element import SemanticElement
from .store import SnapshotStore

__all__ = ["HybridDetector", "SemanticElement", "SnapshotStore"]
