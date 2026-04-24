"""Tests for the configuration manager."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from peekxd.config import ConfigManager, DEFAULT_CONFIG


class TestConfigManager:
    """Test suite for ConfigManager."""

    def test_default_config(self):
        """ConfigManager uses defaults when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            cm = ConfigManager(str(config_path))
            assert cm._config == DEFAULT_CONFIG

    def test_load_existing_config(self):
        """ConfigManager loads existing config and merges with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            custom = {"screenshot": {"format": "jpg", "quality": 80}}
            with open(config_path, "w") as f:
                json.dump(custom, f)

            cm = ConfigManager(str(config_path))
            assert cm.get("screenshot.format") == "jpg"
            assert cm.get("screenshot.quality") == 80
            # Default keys are preserved through merge
            assert "vision" in cm._config
            assert cm.get("vision.default_provider") == "openai"

    def test_save_and_reload(self):
        """Config can be saved and reloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            cm = ConfigManager(str(config_path))
            cm.set("vision.openai_model", "gpt-4o-mini")
            cm.save()

            cm2 = ConfigManager(str(config_path))
            assert cm2.get("vision.openai_model") == "gpt-4o-mini"

    def test_get_dot_notation(self):
        """get() works with dot-notation keys."""
        cm = ConfigManager.__new__(ConfigManager)
        cm._config = DEFAULT_CONFIG.copy()
        assert cm.get("screenshot.format") == "png"
        assert cm.get("vision.default_provider") == "openai"
        assert cm.get("vision.ollama_host") == "http://localhost:11434"

    def test_get_missing_key_returns_default(self):
        """get() returns default for missing keys."""
        cm = ConfigManager.__new__(ConfigManager)
        cm._config = DEFAULT_CONFIG.copy()
        assert cm.get("nonexistent.key", "fallback") == "fallback"
        assert cm.get("screenshot.nonexistent", 42) == 42

    def test_set_dot_notation(self):
        """set() works with dot-notation keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            cm = ConfigManager(str(config_path))
            cm.set("screenshot.format", "webp")
            assert cm.get("screenshot.format") == "webp"

    def test_set_nested_key_creates_path(self):
        """set() creates intermediate dicts for nested keys."""
        cm = ConfigManager.__new__(ConfigManager)
        cm._config = {}
        cm.set("a.b.c", 123)
        assert cm._config == {"a": {"b": {"c": 123}}}

    def test_init_creates_file(self):
        """init() creates default config file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            cm = ConfigManager(str(config_path))
            assert not config_path.exists()
            cm.init()
            assert config_path.exists()
            with open(config_path) as f:
                data = json.load(f)
            assert data == DEFAULT_CONFIG

    def test_init_does_not_overwrite(self):
        """init() does not overwrite existing config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            with open(config_path, "w") as f:
                json.dump({"screenshot": {"format": "gif"}}, f)

            cm = ConfigManager(str(config_path))
            cm.init()
            with open(config_path) as f:
                data = json.load(f)
            assert data["screenshot"]["format"] == "gif"

    def test_show_returns_json_string(self):
        """show() returns a pretty-printed JSON string."""
        cm = ConfigManager.__new__(ConfigManager)
        cm._config = {"key": "value"}
        shown = cm.show()
        assert json.loads(shown) == {"key": "value"}
