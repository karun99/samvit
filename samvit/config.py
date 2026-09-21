"""Cross-platform paths and persistent configuration (standard library only)."""

from __future__ import annotations

import json
import os
import sys


def _is_termux() -> bool:
    return "TERMUX_VERSION" in os.environ or os.path.exists("/data/data/com.termux")


def _home() -> str:
    return os.path.expanduser("~")


def data_dir() -> str:
    """OS-native data directory for one Samvit brain."""
    if _is_termux():
        base = os.path.join(_home(), ".local", "share", "samvit")
    elif sys.platform == "darwin":
        base = os.path.join(_home(), "Library", "Application Support", "Samvit")
    elif os.name == "nt":
        base = os.path.join(os.environ.get("LOCALAPPDATA", _home()), "Samvit")
    else:  # linux and friends
        base = os.path.join(os.getenv("XDG_DATA_HOME", os.path.join(_home(), ".local", "share")), "samvit")
    os.makedirs(base, exist_ok=True)
    return base


def brain_path() -> str:
    return os.path.join(data_dir(), "brain.sqlite")


def config_path() -> str:
    return os.path.join(data_dir(), "config.json")


_DEFAULTS = {
    "profile": "jarvis",
    "vision": {"display": True, "cold_threshold": 20},
    "audit": {"max_rows": 10000},
    "ultron": {
        "max_response_chars": 4000,
        "block_rate_limit": 3,
        "fast": False,
        "pattern_list": None,
    },
    "llm": {
        "providers": ["openrouter", "groq"],
        "providers_required": 2,
        "max_memory_snippets": 5,
    },
}


class Config:
    """Persistent JSON config. API keys are read from environment, never stored."""

    def __init__(self, path: str = None):
        self.path = path or config_path()
        self.data = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self._deep_merge(self.data, loaded)
        except (OSError, ValueError):
            pass

    @staticmethod
    def _deep_merge(base: dict, extra: dict) -> None:
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)

    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self.save()


def api_keys() -> dict:
    """Read LLM API keys from environment only (never written to disk)."""
    keys = {}
    if os.environ.get("OPENROUTER_API_KEY"):
        keys["openrouter"] = os.environ["OPENROUTER_API_KEY"].strip()
    if os.environ.get("GROQ_API_KEY"):
        keys["groq"] = os.environ["GROQ_API_KEY"].strip()
    return keys