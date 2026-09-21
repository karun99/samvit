"""VISION — accuracy marker. Labels every shaped response grounded | partial | ungrounded | cold.

VISION never modifies the response (FR-4.8) and never speaks in persona (FR-4.9).
Per Premortem FM3, an empty/cold memory produces the distinct label `cold` rather
than a misleading `ungrounded`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from .memory import _tokenize

_STALE_DAYS = 180


class VisionMark:
    def __init__(self, label: str, grounding: float, confidence: float,
                 mean_trust: float, staleness_days: int,
                 notes: List[str], cold: bool):
        self.label = label
        self.grounding = round(grounding, 4)
        self.confidence = round(confidence, 4)
        self.mean_trust = round(mean_trust, 4)
        self.staleness_days = staleness_days
        self.notes = notes
        self.cold = cold

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "grounding": self.grounding,
            "confidence": self.confidence,
            "mean_trust": self.mean_trust,
            "staleness_days": self.staleness_days,
            "notes": self.notes,
            "cold": self.cold,
        }

    def banner(self) -> str:
        if self.cold:
            return "[memory: cold]"
        return f"[accuracy: {self.label}]"


def _negation_conflict(response_terms: set, claim_terms_dict: Dict[int, set]) -> bool:
    """Conservative heuristic: conflicting if a low-signal opinion term asserts the
    opposite of a claim term with certainty (e.g. 'never X' vs claim 'X')."""
    for terms in claim_terms_dict.values():
        for term in terms:
            for r in response_terms:
                if term == r:
                    continue
                if ("not" + term) == r or ("never" + term) == r or ("no" + term) == r:
                    return True
    return False


def mark(response_text: str, recalled_claims: List[dict],
         memory_claim_count: int = 0,
         cold_threshold: int = 20) -> VisionMark:
    """Compute the VISION mark for a shaped response.

    Labels per Appendix C:
      grounded   grounding >= 0.7, no contradiction, mean trust >= 0.6
      partial    grounding >= 0.3, no contradiction
      ungrounded grounding < 0.3 or contradiction
      cold       memory is empty/very small (FM3) — not 'ungrounded'
    """
    notes: List[str] = []
    cold = memory_claim_count < cold_threshold
    resp_terms = set(_tokenize(response_text))

    if not recalled_claims:
        grounding = 0.0
        mean_trust = 0.0
        staleness = 0
    else:
        mem_terms = set()
        total_trust = 0.0
        ages = []
        now = datetime.now().timestamp()
        for cl in recalled_claims:
            mem_terms.update(_tokenize(cl["text"]))
            total_trust += float(cl.get("trust", 1.0))
            try:
                ts = datetime.fromisoformat(cl["ts"]).timestamp()
                ages.append((now - ts) / 86400.0)
            except (ValueError, TypeError):
                pass
        overlap = len(resp_terms & mem_terms)
        grounding = overlap / len(resp_terms) if resp_terms else 0.0
        mean_trust = total_trust / len(recalled_claims)
        staleness = int(max(ages)) if ages else 0

    contradiction = bool(recalled_claims) and _negation_conflict(
        resp_terms, {cl["claim_id"]: set(_tokenize(cl["text"])) for cl in recalled_claims}
    )

    if cold and not recalled_claims:
        label = "cold"
        confidence = 0.0
        notes.append("fresh memory: no claims to ground against (FM3)")
    elif grounding < 0.3 or contradiction:
        label = "ungrounded"
        confidence = round(max(0.0, grounding), 4)
        if contradiction:
            notes.append("contradicts a recalled claim")
        notes.append("grounding below 0.3")
    elif grounding < 0.7:
        label = "partial"
        confidence = round(grounding, 4)
        notes.append("grounding between 0.3 and 0.7")
    elif mean_trust >= 0.6:
        label = "grounded"
        confidence = round(grounding, 4)
    else:
        label = "partial"
        confidence = round(grounding, 4)
        notes.append("grounded but mean source trust below 0.6")

    if staleness > _STALE_DAYS and not cold:
        notes.append(f"oldest recalled source is {staleness} days old")

    return VisionMark(
        label=label,
        grounding=grounding,
        confidence=confidence,
        mean_trust=mean_trust,
        staleness_days=staleness,
        notes=notes,
        cold=cold,
    )