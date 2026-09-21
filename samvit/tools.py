"""Allowlisted tools with four-tier consent (FR-7.x). Unlisted tools always fail."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

MAX_FILE_READ = 1_000_000  # FR-7.8


class ToolError(Exception):
    pass


class TierGate:
    """Decision callback decided by the calling interface (CLI/GUI)."""

    def __init__(self, decide: Callable[[int, str, dict], bool], notify: Callable[[int, str, dict], None] = None):
        self._decide = decide
        self._notify = notify or (lambda *a: None)

    def permit(self, tier: int, name: str, args: dict) -> bool:
        if tier <= 2:
            self._notify(tier, name, args)
        if tier in (1, 2):
            return True
        return self._decide(tier, name, args)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tool_now(args: dict) -> dict:
    return {"result": _now().replace("+00:00", "Z")}


def _tool_time(args: dict) -> dict:
    now = datetime.now()
    iso = now.isoformat(timespec="seconds")
    weekday = now.strftime("%A")
    return {"result": {"iso": iso, "weekday": weekday, "unix": int(now.timestamp())}}


def _not_implemented(args: dict) -> dict:
    return {"result": None, "error": "not implemented in v1.0"}


_TOOL_SPECS: Dict[str, dict] = {
    "now": {
        "tier": 1,
        "help": "Current UTC timestamp.",
        "fn": _tool_now,
    },
    "time": {
        "tier": 1,
        "help": "Current local clock.",
        "fn": _tool_time,
    },
    "memory_recall": {
        "tier": 1,
        "help": "Search the memory graph by term overlap.",
        "fn": None,  # bound at registry build time
    },
    "fs_read": {
        "tier": 3,
        "help": f"Read a local file (cap {MAX_FILE_READ} bytes).",
        "fn": None,
    },
    "shell": {
        "tier": 4,
        "help": "Run an allowlisted shell command (two-stage review).",
        "fn": None,
    },
    "organoid_status": {
        "tier": 1,
        "help": "Organoid adapter status. Stub — returns README truth.",
        "fn": _not_implemented,
    },
}

_ALLOWED_SHELL = (
    "date",
    "uptime",
    "df -h",
    "free -h",
    "git status",
    "ls -la",
)


class ToolRegistry:
    def __init__(self, memory=None, gate: Optional[TierGate] = None):
        self._memory = memory
        self._gate = gate or TierGate(lambda tier, name, args: True)
        self._specs = {name: dict(spec) for name, spec in _TOOL_SPECS.items()}
        self._specs["memory_recall"]["fn"] = self._fn_recall
        self._specs["fs_read"]["fn"] = self._fn_fs_read
        self._specs["shell"]["fn"] = self._fn_shell

    # ----------------------------------------------------------- helpers
    def list(self) -> list:
        out = []
        for name, spec in self._specs.items():
            out.append({"name": name, "tier": spec["tier"], "help": spec["help"]})
        return sorted(out, key=lambda d: (d["tier"], d["name"]))

    def spec(self, name: str) -> dict:
        try:
            return self._specs[name]
        except KeyError:
            raise ToolError(f"unlisted tool {name!r}: not on the allowlist") from None

    def call(self, name: str, args: str, origin: str = "cli") -> dict:
        spec = self.spec(name)
        try:
            parsed = json.loads(args) if isinstance(args, str) else dict(args)
        except ValueError:
            raise ToolError("args must be JSON, e.g. --args '{\"k\":\"v\"}'") from None
        if not isinstance(parsed, dict):
            raise ToolError("args must be a JSON object")

        tier = spec["tier"]
        message = f"tool={name} tier={tier}"
        if self._memory is not None:
            self._memory.audit("tool_call_begin", name,
                               f"tier={tier} origin={origin} args={json.dumps(parsed)[:200]}")
        granted = self._gate.permit(tier, name, parsed)
        if self._memory is not None:
            self._memory.audit("tool_consent", name, f"tier={tier} granted={granted}")
        if not granted:
            return {"tool": name, "allowed": False, "reason": f"consent denied at tier {tier}"}

        try:
            result = spec["fn"](parsed)
        except ToolError:
            raise  # policy violations fail loudly (FR-7.1/7.7/7.8)
        except Exception as exc:
            result = {"error": f"{exc!r}"}
        if self._memory is not None:
            self._memory.audit("tool_call_end", name, json.dumps(result)[:200])
        result.setdefault("allowed", True)
        result["tool"] = name
        return result

    # ----------------------------------------------------------- implementations
    def _fn_recall(self, args: dict) -> dict:
        query = str(args.get("query", ""))
        if not query:
            raise ToolError("memory_recall requires 'query'")
        if self._memory is None:
            return {"result": []}
        limit = int(args.get("limit", 5))
        clips = self._memory.recall(query, limit=limit)
        return {"result": [{"text": c["text"], "trust": c["trust"]} for c in clips]}

    def _fn_fs_read(self, args: dict) -> dict:
        path = str(args.get("path", ""))
        if not path:
            raise ToolError("fs_read requires 'path'")
        size = os.path.getsize(path)
        if size > MAX_FILE_READ:
            raise ToolError(f"file {size} bytes exceeds 1 MB cap (FR-7.8)")
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(MAX_FILE_READ)
        return {"result": {"path": path, "bytes": size, "text": text}}

    def _fn_shell(self, args: dict) -> dict:
        cmd = str(args.get("cmd", ""))
        if cmd not in _ALLOWED_SHELL:
            raise ToolError(
                f"shell command {cmd!r} not on allowlist. Allowed: {list(_ALLOWED_SHELL)}"
            )
        import subprocess

        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return {"result": {"exit": proc.returncode, "stdout": proc.stdout[:4000],
                           "stderr": proc.stderr[:4000]}}