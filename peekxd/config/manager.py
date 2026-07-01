"""JSON-based configuration manager for peekxd Linux."""

import copy
import json
import os
from pathlib import Path
from typing import Any, Optional

from ..core import get_config_dir, ConfigurationError

DEFAULT_CONFIG = {
    "screenshot": {
        "default_output": "~/Pictures/peekxd",
        "format": "png",
        "quality": 95
    },
    "vision": {
        "providers": ["hermes", "openai", "anthropic", "ollama"],
        "default_provider": "hermes",
        "openai_model": "gpt-4o",
        "anthropic_model": "claude-3-opus-20240229",
        "ollama_model": "llava:latest",
        "ollama_host": "http://localhost:11434"
    },
    "input": {
        "delay_ms": 10
    },
    "mcp": {
        "transport": "stdio",
        "port": 3000
    }
}


class ConfigManager:
    """Manages JSON-based configuration for peekxd."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_dir = get_config_dir()
        self.config_path = Path(config_path) if config_path else self.config_dir / "config.json"
        self._config = {}
        self.load()

    def load(self) -> dict:
        """Load config from file or return defaults."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = {**copy.deepcopy(DEFAULT_CONFIG), **json.load(f)}
        else:
            self._config = copy.deepcopy(DEFAULT_CONFIG)
        return self._config

    def save(self) -> None:
        """Save current config to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key (e.g., 'vision.openai_model')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set config value by dot-notation key."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def init(self) -> None:
        """Create default config file if it doesn't exist."""
        if not self.config_path.exists():
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            self.save()

    def show(self) -> str:
        """Return pretty-printed config."""
        return json.dumps(self._config, indent=2)
