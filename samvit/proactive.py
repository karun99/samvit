"""Proactive watchers — tier-gated, user-invoked only (FR-9.x)."""

from __future__ import annotations

from typing import List, Optional

from .memory import Memory


def _watch_memory_growth(memory: Memory) -> dict:
    claims = memory.count_claims()
    recent = len(memory.recent(20))
    return {"name": "memory_growth", "claims": claims,
            "recent": recent, "tier": 1, "known_action": False}


def _watch_drift(memory: Memory, persona) -> dict:
    d = persona.drift()
    return {"name": "persona_drift", "drift": d, "tier": 1, "known_action": False}


def _watch_security_sweep(memory: Memory) -> dict:
    entries = memory.query_audit(limit=100, action="ultron_block")
    return {"name": "security_sweep", "recent_ultron_blocks": len(entries),
            "tier": 2, "known_action": False}


def _watch_desktop_inbox(memory: Memory) -> dict:
    # Placeholder watcher that demonstrates the Tier 3 boundary:
    # it reports, but never performs a Tier 3+ action autonomously (FR-9.5).
    return {"name": "desktop_inbox", "unread_estimate": None, "tier": 3,
            "known_action": False,
            "note": "would require a Tier 3 consent gate before real work"}


_WATCHERS = {
    "memory_growth": _watch_memory_growth,
    "persona_drift": _watch_drift,
    "security_sweep": _watch_security_sweep,
    "desktop_inbox": _watch_desktop_inbox,
}


def list_watchers() -> List[dict]:
    tiers = {
        "memory_growth": 1,
        "persona_drift": 1,
        "security_sweep": 2,
        "desktop_inbox": 3,
    }
    return [{"name": n, "tier": tiers[n]} for n in _WATCHERS]


def run_watcher(name: str, memory: Memory, persona=None) -> dict:
    """One watcher, explicit invocation only (FR-9.2). Never crashes (FR-9.4)."""
    fn = _WATCHERS.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown watcher {name!r}"}
    try:
        if name == "persona_drift":
            result = fn(memory, persona)
        else:
            result = fn(memory)
        memory.audit("watcher_run", name, "tier-gated, user-invoked")
        return {"ok": True, "result": result}
    except Exception as exc:
        memory.audit("watcher_error", name, repr(exc))
        return {"ok": False, "error": repr(exc)}


def run_all(memory: Memory, persona=None) -> List[dict]:
    """Run every watcher. Each reports independently; one failure cannot kill the run."""
    return [run_watcher(name, memory, persona) for name in _WATCHERS]