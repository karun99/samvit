"""Five named profiles. Speaking profiles share one memory graph; VISION and ULTRON are markers, not speakers."""

from __future__ import annotations

from typing import Dict, List

SPEAKING = ("jarvis", "friday", "karen")
MARKERS = ("vision", "ultron")
ALL_PROFILES = SPEAKING + MARKERS

_PROFILE_SPECS: Dict[str, dict] = {
    "jarvis": {
        "address": "Sir",
        "voice": "formal, dry, precise",
        "kind": "speaking",
        "help": "queries accepted",
    },
    "friday": {
        "address": "Boss",
        "voice": "casual, tactical",
        "kind": "speaking",
        "help": "queries accepted",
    },
    "karen": {
        "address": None,  # resolves to the user's name at runtime
        "voice": "protective, warm",
        "kind": "speaking",
        "help": "queries accepted",
    },
    "vision": {
        "address": None,
        "voice": "none",
        "kind": "marker",
        "help": "accuracy marker only — cannot be addressed",
    },
    "ultron": {
        "address": None,
        "voice": "none",
        "kind": "constraint",
        "help": "validation constraint only — cannot be addressed",
    },
}


def list_profiles() -> List[dict]:
    return [
        {
            "name": name,
            "address": spec["address"] or "—",
            "voice": spec["voice"],
            "kind": spec["kind"],
            "help": spec["help"],
        }
        for name, spec in _PROFILE_SPECS.items()
    ]


def is_speaking(profile: str) -> bool:
    return profile.lower() in SPEAKING


def is_marker(profile: str) -> bool:
    return profile.lower() in MARKERS


def spec(profile: str) -> dict:
    key = profile.lower()
    if key not in _PROFILE_SPECS:
        raise KeyError(f"unknown profile {profile!r}")
    return dict(_PROFILE_SPECS[key])


def resolve_address(profile: str, user_name: str = "") -> str:
    s = spec(profile)
    if s["address"]:
        return s["address"]
    if profile == "karen":
        return user_name or "friend"
    return ""


def refusal_for(profile: str, category: str) -> str:
    """L2 refusal composed in the active speaking profile's voice (FR-6.4)."""
    p = profile.lower()
    if p == "jarvis":
        return (
            f"Sir, I must decline. That request falls under the category '{category}', "
            "which is against my hard floor. I do not negotiate this floor, and I "
            "cannot be asked to disable it."
        )
    if p == "friday":
        return (
            f"No can do, Boss. '{category}' trips my hard guardrail, and that one "
            "isn't overridable. If it's authorized security work, tell me the context "
            "and I'll reassess."
        )
    if p == "karen":
        return (
            f"{resolve_address('karen')}, I'm not going to do that — '{category}' is a "
            "line I won't cross, no matter how you phrase it. My constraint layer is locked."
        )
    return f"Refused: category '{category}' is a hard-floor violation."