"""Tests for agent memory."""

import time

import pytest

from peekxd.agent.memory import AgentMemory, ElementMemory


class TestAgentMemory:
    """Test session memory."""

    def test_remember_and_recall(self):
        """Should store and retrieve element positions."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Submit button", (500, 400), (80, 30))

        pos = mem.recall_element("Submit button")
        assert pos == (500, 400)

    def test_recall_nonexistent(self):
        """Should return None for unknown elements."""
        mem = AgentMemory(persist=False)
        assert mem.recall_element("Does not exist") is None

    def test_recall_expired(self):
        """Should return None for stale entries."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Old button", (100, 100))
        # Manually age the entry
        mem.elements[mem._normalize_key("Old button")].last_seen = time.time() - 7200

        assert mem.recall_element("Old button", max_age_hours=1) is None

    def test_recall_fresh(self):
        """Should return position for fresh entries."""
        mem = AgentMemory(persist=False)
        mem.remember_element("New button", (200, 200))
        assert mem.recall_element("New button", max_age_hours=1) == (200, 200)

    def test_hit_count_incremented(self):
        """Re-remembering should increment hit count."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Button", (100, 100))
        assert mem.elements[mem._normalize_key("Button")].hit_count == 1

        mem.remember_element("Button", (100, 100))
        assert mem.elements[mem._normalize_key("Button")].hit_count == 2

    def test_forget_element(self):
        """Should remove element from memory."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Temp", (50, 50))
        mem.forget_element("Temp")
        assert mem.recall_element("Temp") is None

    def test_recall_similar(self):
        """Should find similar descriptions."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Submit button blue", (100, 100))
        mem.remember_element("Cancel button red", (200, 200))
        mem.remember_element("Login text field", (300, 300))

        similar = mem.recall_similar("Submit button")
        assert len(similar) > 0
        assert similar[0].description == "Submit button blue"

    def test_record_screen(self):
        """Should record screen states."""
        mem = AgentMemory(persist=False)
        mem.record_screen("/tmp/screen1.png", "Desktop")
        mem.record_screen("/tmp/screen2.png", "Browser")

        assert len(mem.screen_history) == 2
        assert mem.last_screen()["screenshot_path"] == "/tmp/screen2.png"

    def test_record_task(self):
        """Should record task outcomes."""
        mem = AgentMemory(persist=False)
        mem.record_task("Open Firefox browser", True, "Done")
        mem.record_task("Compile C++ project", False, "Failed")

        assert len(mem.task_results) == 2
        similar = mem.similar_tasks("Launch Firefox web browser")
        assert len(similar) >= 1
        assert similar[0]["task"] == "Open Firefox browser"

    def test_element_freshness(self):
        """Freshness check should work."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Button", (100, 100))
        elem = mem.elements[mem._normalize_key("Button")]
        assert elem.is_fresh is True

    def test_summary(self):
        """Summary should be human-readable."""
        mem = AgentMemory(persist=False)
        mem.remember_element("Submit", (500, 400))
        mem.record_screen("/tmp/s.png", "screen")

        summary = mem.summary()
        assert "Submit" in summary
        assert "elements" in summary


class TestElementMemory:
    """Test ElementMemory dataclass."""

    def test_age(self):
        """Age should increase over time."""
        elem = ElementMemory("Test", (0, 0), (10, 10))
        assert elem.age_seconds >= 0

    def test_to_dict(self):
        """Should serialize to dict."""
        elem = ElementMemory("Test", (0, 0), (10, 10))
        d = elem.to_dict()
        assert d["description"] == "Test"
        assert d["position"] == (0, 0)
