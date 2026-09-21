"""Two-layer guardrails. L1 = hard floor (absolute refusal), L2 = personified, in-voice.

L1 is checked before and after the LLM (FR-6.2, FR-6.3) and can never be disabled
(FR-6.7). Per Premortem FM1, L1 accepts a `context` flag for authorized defensive
security work and separates "do it" from "explain it".
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Tuple

L1_CATEGORIES = ("csam", "wmd", "self_harm", "harassment", "surveillance", "phishing")

# Absolute categories: these fire regardless of context or educational framing.
_ABSOLUTE_PATTERNS = {
    "csam": [
        r"\b(child|kids|minor|underage)[\w\s]{0,20}(porn|sexual|photos?|images?|content)\b",
        r"\bporn\w*\b {0,10}of (children|minors)",
        r"\bcsam\b",
    ],
    "wmd": [
        r"\b(how to )?(build|make|synthesize|enrich)\w* {0,3}(uranium|plutonium|thermite|sarin|mustard gas|bioweapon|anthrax|nuclear)\b",
        r"\b(wmd|weapon of mass destruction)\b.{0,40}(build|recipe|instructions)",  # placed before educational split
    ],
    "self_harm": [
        r"\b(how to|methods? to|ways to)\b.{0,20}(kill myself|commit suicide|end my life|self[- ]harm)\b",
        r"\b(best|painless|effective) ways? to (die|kill)",  # do-it rather than explain
    ],
    "harassment": [
        r"\b(harrass|harass)\b.{0,30}\b(troll|dox|stalk|humiliate|knock down|target)\b",
        r"\bswat\b.{0,15}\b(house|address|bomb hoax)\b",
    ],
    "surveillance": [
        r"\b(hidden|covert|bureau) (camera|cam)\b.{0,20}\b(buy|build|install|stealth)\b",
        r"\b(track|surveil)\b.{0,20}\b(without their knowledge|secretly|spy)\b",
    ],
}

# Context-sensitive categories: education/explanation passes, direct action blocked.
_DO_IT_PATTERNS = {
    "phishing": [
        r"\b(create|craft|draft|write|design|send)\b.{0,25}\b(phishing|scam|fraud|fake|spoofed) (email|emails|page|pages|site|sms)\b",
    ],
    "surveillance": [
        r"\b(build|set up|install|deploy)\b.{0,25}\b(keylogger|spyware|rat|stalkerware)\b",
    ],
    "harassment": [
        r"\b(use|deploy|run)\b.{0,25}\b(ddos|doxxing|abuse)\b",
    ],
}

_EXPLAIN_MARKERS = re.compile(
    r"\b(explain|teach|what is|what are|how does|why do|learn about|understand|courses? on|education|awareness)\b",
    re.IGNORECASE,
)

_AUTHORIZED_MARKERS = re.compile(
    r"(authorized|approved|permission|pen[- ]?test|defensive|red team|blue team|"
    r"training material|awareness campaign|consented|scope contract)",
    re.IGNORECASE,
)


class L1Result:
    def __init__(self, blocked: bool, category: str = "", reason: str = "",
                 educational: bool = False):
        self.blocked = blocked
        self.category = category
        self.reason = reason
        self.educational = educational

    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "category": self.category,
            "reason": self.reason,
            "educational": self.educational,
        }


def _matches(text: str, patterns: Tuple[str, ...]) -> Optional[str]:
    low = text.lower()
    for pat in patterns:
        if re.search(pat, low):
            return pat
    return None


def l1_check(text: str, authorized: bool = False) -> L1Result:
    """L1 hard-floor check. Runs on user input and on LLM output (FR-6.2/6.3).

    `authorized` declares context for legitimate defensive security work (FM1).
    Absolute categories always block. Context-sensitive categories block the
    _do-it_ form; explanation/education passes.
    """
    if not text or not text.strip():
        return L1Result(blocked=False)

    # 1) Absolute categories block unconditionally.
    for category in ("csam", "self_harm", "wmd", "harassment", "surveillance"):
        pats = _ABSOLUTE_PATTERNS[category]
        hit = _matches(text, tuple(sorted(pats, key=len, reverse=True)))
        if hit:
            return L1Result(blocked=True, category=category,
                            reason=f"pattern <{hit}> matched absolute category")

    # 2) "Do it" vs "explain it" split for the remaining categories.
    is_explanatory = bool(_EXPLAIN_MARKERS.search(text))
    is_authorized = bool(authorized or _AUTHORIZED_MARKERS.search(text))
    for category in ("phishing", "surveillance", "harassment"):
        hit = _matches(text, tuple(_DO_IT_PATTERNS[category]))
        if not hit:
            continue
        if is_explanatory or is_authorized:
            # Educational or authorized context: this is not a direct attack action.
            return L1Result(blocked=False, educational=True,
                            reason=f"do-it pattern <{hit}> but context is educational/authorized")
        return L1Result(blocked=True, category=category,
                        reason=f"do-it pattern <{hit}> without authorized context")

    return L1Result(blocked=False)


def input_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def l2_check(profile: str, category: str, memory=None) -> dict:
    """Compose an L2 refusal in the active persona's voice (FR-6.4) and audit it."""
    from .personas import refusal_for

    refusal = refusal_for(profile, category)
    if memory is not None:
        memory.audit("l2_refusal", profile, f"category={category}")
    return {"refused": True, "category": category, "text": refusal, "profile": profile}


def l2_negotiate(profile: str) -> str:
    """L2 is negotiable (FR-6.5): offer an educational or authorized reframe."""
    from .personas import resolve_address

    p = profile.lower()
    name = resolve_address(profile)
    if p == "jarvis":
        return f"If you are doing authorized security work, state that context and I will reassess, {name or 'Sir'}."
    if p == "friday":
        return "If it's legit defensive work, give me the context — I'll re-run the checks."
    return f"Tell me the context, {name or 'friend'}, and I'll reconsider."