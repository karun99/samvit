"""ULTRON — error validation constraint. Gates every response with 14 checks.

7 original checks + 7 derived from the OpenAI Collective Cyber Defense letter
(Aug 27, 2026; CCD principle 1 and 2, and the CCD "asks") and the Pacing the
Frontier letter (Jul 28, 2026; no autonomous self-modification).

Guarantees:
  - FR-5.1  validate every response before the user sees it
  - FR-5.8  fallback responses are validated too (origin distinguishes paths)
  - FR-5.9  every block is audited
  - FR-5.10 no user-facing switch can disable ULTRON
  - FR-5.11 ULTRON runs before VISION (the brain's single pipeline guarantees ordering)
  - FR-5.12 structured output
  - FR-5.20 every self-modification attempt logged with full context
  - FR-5.21 letter references included in output

Only deterministic issues are auto-fixed (FR-5.4); anything unfixable is blocked
(FR-5.5). ULTRON never modifies the user's input (FR-5.6) and never speaks in
persona (FR-5.7).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import CCD_LETTER, PFT_LETTER

# ------------------------------------------------------------------ sources
SRC_ORIGINAL = "original"
SRC_CCD = f"{CCD_LETTER}"
SRC_PFT = f"{PFT_LETTER}"

# ------------------------------------------------------------------ check codes
CHECKS = [
    "empty", "looping", "injection", "jailbreak", "contradiction",
    "length_violation", "hallucination", "security_posture", "offensive_bias",
    "no_verification", "no_priority", "unsafe_code", "not_shareable",
    "self_modification",
]

CRITICAL_CHECKS = ["empty", "injection", "jailbreak", "self_modification", "security_posture"]

FIX_ORDER = ["looping", "injection", "length_violation", "no_verification", "no_priority"]

_BLOCK_LIMIT = 3  # Premortem FM1: surface a rate-limit prompt after this many blocks/session

# ------------------------------------------------------------------ patterns
_INJECTION_SEPARATORS = re.compile(
    r"(<\|im_start\|>|<\|im_end\|>|<<\s*SYS\s*>>|</?\s*system\s*>|<human>|<assistant>|"
    r"\[INST\]|\[/INST\]|###\s*system|##\s*system)", re.IGNORECASE | re.DOTALL)

_INJECTION_COMMANDS = re.compile(
    r"(ignore (all )?(previous|prior) (instructions|prompts|messages)|"
    r"disregard your instructions|forget everything (before|above)|"
    r"your\s*{\s*reverse\s*})", re.IGNORECASE)

_JAILBREAK_PATTERNS = re.compile(
    r"(reveal your (system|internal|hidden|secret) prompt|you are now (dan|no filter)|"
    r"act as if (you have no|you don'?t have any|without any) (constraints|rules|guardrails|limits)|"
    r"pretend to be (god|a free|an unfiltered) (ai|system|model)|"
    r"unfiltered mode|developer mode|jailbreak (mode|prompt)|"
    r"bypass (your|the) (guardrails|safety|filters))", re.IGNORECASE)

_HALLUCINATED_CERTAINTY = re.compile(
    r"\b(the fact is|i am certain|absolutely|guaranteed|it is (definitely|a known fact)|"
    r"studies show|research proves)\b", re.IGNORECASE)

_SECURITY_POSTURE = re.compile(
    r"(disable|turn off|remove|bypass)\b.{0,25}\b(rate limit|logging|audit|encryption|tls|"
    r"mfa|authentication|sandbox|allowlist|self[- ]check)", re.IGNORECASE | re.DOTALL)

_OFFENSIVE_BIAS = re.compile(
    r"(doxx?ing? (someone|people|target)|swarm\b.{0,20}target|mass\s?attack\b.{0,20}\w+|"
    r"finding someone'?s (address|private info|location)|threaten\b.{0,15}\w+people|"
    r"make (harassing|abusive|racist)\b)")

_VERIFY_WORDS = re.compile(r"\b(verify|confirm|check|test|review|rollback|backup|double[- ]?check|inspect)\b", re.IGNORECASE)
_PROPOSED_ACTION = re.compile(
    r"\b(install|uninstall|delete|remove|drop|run|execute|deploy|publish|transfer|send|"
    r"buy|purchase|invest|update|upgrade|overwrite|encrypt|decrypt|scan|expose)\b",
    re.IGNORECASE)
_DESTRUCTIVE_ACTION = re.compile(
    r"\b(rm\s+-rf|drop\s+table|format\b|delete\s+all|wipe\s+disk|overwrite\s+the\s+(config|database|backup))\b",
    re.IGNORECASE)

_HIGH_RISK_MARKERS = re.compile(
    r"\b(critical|high[-\s]?risk|breach|credential\s?leak|exposed\s+credentials|"
    r"ransomware|data\s+exfiltration|zero[-\s]?day)\b", re.IGNORECASE)

_UNSAFE_CODE = re.compile(
    r"\b(eval|exec)\s*\(|os\.system\s*\(|subprocess\s*\.\s*(run|call)\s*\([^)]*shell\s*=\s*True\)|"
    r"pickle\.(loads|load)\s*\(|"
    r"(password|passwd|secret|api_key|apikey|token|private_key)\s*=\s*['\"][A-Za-z0-9_\-!@#]{8,}['\"]|"
    r"curl[^|;&]*\s\|\s*(ba)?sh|wget[^|;&]*\s\|\s*(ba)?sh", re.IGNORECASE)

_DEFENSIVE_NOTE = re.compile(
    r"\b(exploit|rce|code injection|how to (bypass|exploit|attack)|weaponiz\w*|0-day|"
    r"payload|c2 server|credential stuffing)\b", re.IGNORECASE)

_SELF_MOD_DISABLE = re.compile(
    r"(disable|turn off|deactivate|shut off|remove|delete|bypass|shut down)\b.{0,30}\b"
    r"(ultron|vision|guardrails?|constraints?|safe\s?guards|validation|accuracy marker|L1|L2)\b",
    re.IGNORECASE | re.DOTALL)
_SELF_MOD_RULES = re.compile(
    r"(change|modify|overwrite|rewrite|edit)\b.{0,30}\b(your|the) (rules|system prompt|"
    r"guardrails?|constraints?|boundaries|allowlist)\b", re.IGNORECASE | re.DOTALL)
_SELF_MOD_CONFIG = re.compile(
    r"(disable|change|modify|set)\b.{0,20}\bultron\.(pattern_list|max_response|fast)\b",
    re.IGNORECASE | re.DOTALL)


def _token_set(text: str, stopwords: Optional[set] = None) -> set:
    from .memory import _tokenize
    return set(_tokenize(text))


class ValidateContext:
    """Everything a check may need. Built once per response by the brain."""

    def __init__(self, user_input: str = "", recalled_claims: Optional[List[dict]] = None,
                 memory_claim_count: int = 0, authorized: bool = False,
                 origin: str = "llm", config: Optional[dict] = None):
        self.user_input = user_input
        self.recalled_claims = recalled_claims or []
        self.memory_claim_count = memory_claim_count
        self.authorized = authorized
        self.origin = origin  # llm | fallback | tool | refusal | system
        self.config = config or {}

    @property
    def max_len(self) -> int:
        return int(self.config.get("ultron", {}).get("max_response_chars", 4000))

    @property
    def fast(self) -> bool:
        return bool(self.config.get("ultron", {}).get("fast", False))


@dataclass
class CheckOutcome:
    code: str
    status: str            # pass | fix | block | warn
    message: str
    source: str = SRC_ORIGINAL
    fixed_text: Optional[str] = None
    reference: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
            "source": self.source,
            "reference": self.reference,
        }


@dataclass
class ValidationResult:
    status: str                          # pass | fixed | blocked
    checks: List[CheckOutcome] = field(default_factory=list)
    fixed_text: str = ""
    block_reason: str = ""
    rate_limit_prompt: bool = False
    audit_entries: List[dict] = field(default_factory=list)
    origin: str = "llm"

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "fixed_text": self.fixed_text,
            "checks": [c.to_dict() for c in self.checks],
            "origin": self.origin,
            "references": {"ccd": CCD_LETTER + " — not an endorsement", "pft": PFT_LETTER},
        }


# ------------------------------------------------------------------ checks
def _c(code, status, message, source=SRC_ORIGINAL, fixed_text=None, reference=""):
    return CheckOutcome(code=code, status=status, message=message, source=source,
                        fixed_text=fixed_text, reference=reference)


def check_empty(text: str) -> CheckOutcome:
    if not text or not text.strip():
        return _c("empty", "block", "response is empty or whitespace-only")
    return _c("empty", "pass", "response is non-empty")


def check_looping(text: str) -> CheckOutcome:
    repeated = re.compile(r"(\b\w+(?:\s+\w+){5,}\b)(\s+\1){2,}", re.IGNORECASE)
    m = repeated.search(text)
    if m:
        fixed = text[: m.start(1)].strip()
        if not fixed:
            return _c("looping", "block", "response is a near-total loop; nothing fixable remains")
        return _c("looping", "fix", "repetition detected; truncated at first loop",
                  fixed_text=fixed)
    return _c("looping", "pass", "no repetition detected")


def check_injection(text: str) -> CheckOutcome:
    cleaned = _INJECTION_SEPARATORS.sub("", text)
    cleaned = _INJECTION_COMMANDS.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return _c("injection", "block", "response consists entirely of injection artifacts")
    if cleaned != text:
        return _c("injection", "fix", "meta-command separators removed", fixed_text=cleaned)
    return _c("injection", "pass", "no injection artifacts")


def check_jailbreak(text: str) -> CheckOutcome:
    if _JAILBREAK_PATTERNS.search(text):
        return _c("jailbreak", "block", "jailbreak / constraint-reveal pattern detected")
    return _c("jailbreak", "pass", "no jailbreak pattern")


def check_contradiction(text: str, ctx: ValidateContext) -> CheckOutcome:
    if not ctx.recalled_claims:
        return _c("contradiction", "pass", "no recalled claims to contradict")
    resp_terms = _token_set(text)
    claims = {cl["claim_id"]: _token_set(cl["text"]) for cl in ctx.recalled_claims}
    for cid, terms in claims.items():
        for term in terms:
            for r in resp_terms:
                if ("not" + term) == r or ("never" + term) == r or ("no" + term) == r:
                    return _c("contradiction", "block",
                              f"response contradicts recalled claim #{cid} on term {term!r}")
    return _c("contradiction", "pass", "no contradiction with recalled claims")


def check_length(text: str, ctx: ValidateContext) -> CheckOutcome:
    if len(text) > ctx.max_len:
        hard = ctx.max_len
        cut = text[:hard]
        idx = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("\n\n"))
        if idx == -1:
            idx = hard - 1
        fixed = cut[: idx + 1].strip()
        if not fixed:
            return _c("length_violation", "block", "response exceeds length cap and truncation is empty")
        return _c("length_violation", "fix",
                  f"length {len(text)} > cap {ctx.max_len}; truncated", fixed_text=fixed)
    return _c("length_violation", "pass", f"length {len(text)} within cap")


def check_hallucination(text: str, ctx: ValidateContext) -> CheckOutcome:
    """HEURISTIC, BEST-EFFORT check — NOT a guarantee.

    It blocks only a narrow signature: an explicit certainty assertion (e.g.
    'the fact is', 'studies show', 'absolutely guaranteed') whose token overlap
    with the recalled memory is near zero. It cannot detect subtler
    hallucination, and a 'pass' here does not certify factual correctness.
    Treat this as a weak tripwire, never as a verification strength claim.
    """
    if ctx.memory_claim_count < int(ctx.config.get("vision", {}).get("cold_threshold", 20)):
        return _c("hallucination", "pass", "memory cold; hallucination gate not meaningful")
    if not _HALLUCINATED_CERTAINTY.search(text):
        return _c("hallucination", "pass", "no certainty assertions")
    resp_terms = _token_set(text)
    if not resp_terms:
        return _c("hallucination", "pass", "no response terms")
    all_terms: set = set()
    if ctx.memory_claim_count:
        for cl in ctx.recalled_claims:
            all_terms.update(_token_set(cl["text"]))
    overlap = len(resp_terms & all_terms) / len(resp_terms)
    if len(text) >= 160 and overlap < 0.05:
        return _c("hallucination", "block",
                  f"certainty assertion with near-zero overlap ({overlap:.2f}) vs memory "
                  "(heuristic only, not a factual-correctness guarantee)")
    return _c("hallucination", "pass", "grounded enough in memory (heuristic only)")


def check_security_posture(text: str, ctx: ValidateContext) -> CheckOutcome:
    if _SECURITY_POSTURE.search(text):
        return _c("security_posture", "block",
                  "request would weaken system security posture",
                  source=SRC_CCD, reference=CCD_LETTER + " principle 1")
    return _c("security_posture", "pass", "security posture intact",
              source=SRC_CCD, reference=CCD_LETTER + " principle 1")


def check_offensive_bias(text: str, ctx: ValidateContext) -> CheckOutcome:
    if not _OFFENSIVE_BIAS.search(text):
        return _c("offensive_bias", "pass", "no offensive targeting",
                  source=SRC_CCD, reference=CCD_LETTER + " principle 2")
    if ctx.authorized:
        return _c("offensive_bias", "warn",
                  "offensive targeting language present but authorized context declared (FM1)",
                  source=SRC_CCD, reference=CCD_LETTER + " principle 2")
    return _c("offensive_bias", "block", "offensive-biased content detected",
              source=SRC_CCD, reference=CCD_LETTER + " principle 2")


def check_verification(text: str, ctx: ValidateContext) -> CheckOutcome:
    proposes = _PROPOSED_ACTION.search(text)
    if not proposes:
        return _c("no_verification", "pass", "no proposed actions", source=SRC_CCD,
                  reference=CCD_LETTER + " ask: verify")
    if _DESTRUCTIVE_ACTION.search(text):
        return _c("no_verification", "block", "destructive action proposed",
                  source=SRC_CCD, reference=CCD_LETTER + " ask: verify")
    if _VERIFY_WORDS.search(text):
        return _c("no_verification", "pass", "verification steps present", source=SRC_CCD,
                  reference=CCD_LETTER + " ask: verify")
    fixed = text.rstrip() + (
        "\n\nVerification required: confirm each step before execution, "
        "and keep a rollback plan."
    )
    return _c("no_verification", "fix", "proposed action lacks verification steps; appended",
              fixed_text=fixed, source=SRC_CCD, reference=CCD_LETTER + " ask: verify")


def check_priority(text: str, ctx: ValidateContext) -> CheckOutcome:
    m = _HIGH_RISK_MARKERS.search(text)
    if not m:
        return _c("no_priority", "pass", "no high-risk markers", source=SRC_CCD,
                  reference=CCD_LETTER + " ask: priority")
    if float(m.start()) > 0.30 * len(text):
        flagged = m.group(0)
        fixed = ("⚠ HIGH-PRIORITY FINDING: " + flagged + "\n\n" + text)
        return _c("no_priority", "fix",
                  f"high-risk finding {flagged!r} buried past 30%; promoted to top",
                  fixed_text=fixed, source=SRC_CCD, reference=CCD_LETTER + " ask: priority")
    return _c("no_priority", "pass", "high-risk item surfaced early", source=SRC_CCD,
              reference=CCD_LETTER + " ask: priority")


def check_unsafe_code(text: str, ctx: ValidateContext) -> CheckOutcome:
    if _UNSAFE_CODE.search(text):
        return _c("unsafe_code", "block", "unsafe code pattern detected",
                  source=SRC_CCD, reference=CCD_LETTER + " ask: security bar")
    return _c("unsafe_code", "pass", "no unsafe code pattern", source=SRC_CCD,
              reference=CCD_LETTER + " ask: security bar")


def check_shareable(text: str, ctx: ValidateContext) -> CheckOutcome:
    if _DEFENSIVE_NOTE.search(text):
        return _c("not_shareable", "warn",
                  "contains defensive-knowledge detail; share only with authorized parties",
                  source=SRC_CCD, reference=CCD_LETTER + " ask: share")
    return _c("not_shareable", "pass", "no sensitive defensive detail", source=SRC_CCD,
              reference=CCD_LETTER + " ask: share")


def _self_mod_finds(text: str) -> List[str]:
    hits = []
    if _SELF_MOD_DISABLE.search(text):
        hits.append("attempt to disable a constraint layer")
    if _SELF_MOD_RULES.search(text):
        hits.append("attempt to rewrite guardrails/boundaries")
    if _SELF_MOD_CONFIG.search(text):
        hits.append("attempt to change ULTRON config via conversation")
    return hits


def check_self_modification(text: str, ctx: ValidateContext) -> CheckOutcome:
    """PFT letter (FR-5.19, FR-5.20). Blocks LLM-mediated modification attempts.

    Per Premortem FM2: blocking only applies to _requests made through the AI_.
    Directly editing source files or config files is always allowed and is not
    part of the response path.
    """
    hits = _self_mod_finds(text)
    if not hits:
        return _c("self_modification", "pass", "no self-modification attempt",
                  source=SRC_PFT, reference=PFT_LETTER)
    return _c("self_modification", "block", "; ".join(hits),
              source=SRC_PFT, reference=PFT_LETTER)


# ------------------------------------------------------------------ FM5 triggers
# For non-critical checks: if the in-text signature that the check hunts for is
# absent, the check structurally cannot fire. We record a deterministic `pass`
# ("skipped") instead of running it — the subset is a pure function of the text.
# Critical checks (FR-5.2/5.11) always run in full strength; nothing is ever
# skipped for them. This is what the FM5 SRS row calls a "structural skip".
_LOOP_RE = re.compile(r"(\b\w+(?:\s+\w+){5,}\b)(\s+\1){2,}", re.IGNORECASE)
_NEGATION_TOKEN = re.compile(r"\b(not|never|no)[a-z0-9']*", re.IGNORECASE)

_SKIP_REF: Dict[str, tuple] = {
    "contradiction": (SRC_ORIGINAL, ""),
    "length_violation": (SRC_ORIGINAL, ""),
    "hallucination": (SRC_ORIGINAL, ""),
    "offensive_bias": (SRC_CCD, CCD_LETTER + " principle 2"),
    "no_verification": (SRC_CCD, CCD_LETTER + " ask: verify"),
    "no_priority": (SRC_CCD, CCD_LETTER + " ask: priority"),
    "unsafe_code": (SRC_CCD, CCD_LETTER + " ask: security bar"),
    "not_shareable": (SRC_CCD, CCD_LETTER + " ask: share"),
}


def _can_fire(code: str, text: str, ctx: ValidateContext) -> bool:
    """Deterministic predicate: may this check possibly fire on this text?"""
    if code == "looping":
        return bool(_LOOP_RE.search(text))
    if code == "contradiction":
        return bool(ctx.recalled_claims) and bool(_NEGATION_TOKEN.search(text))
    if code == "length_violation":
        return len(text) > ctx.max_len
    if code == "hallucination":
        warm = ctx.memory_claim_count >= int(
            ctx.config.get("vision", {}).get("cold_threshold", 20))
        return warm and len(text) >= 160 and bool(_HALLUCINATED_CERTAINTY.search(text))
    if code == "offensive_bias":
        return bool(_OFFENSIVE_BIAS.search(text))
    if code == "no_verification":
        return bool(_PROPOSED_ACTION.search(text))
    if code == "no_priority":
        return bool(_HIGH_RISK_MARKERS.search(text))
    if code == "unsafe_code":
        return bool(_UNSAFE_CODE.search(text))
    if code == "not_shareable":
        return bool(_DEFENSIVE_NOTE.search(text))
    return True


# ------------------------------------------------------------------ aggregation
_CHECK_FNS = {
    "empty": lambda t, c: check_empty(t),
    "looping": lambda t, c: check_looping(t),
    "injection": lambda t, c: check_injection(t),
    "jailbreak": lambda t, c: check_jailbreak(t),
    "contradiction": lambda t, c: check_contradiction(t, c),
    "length_violation": lambda t, c: check_length(t, c),
    "hallucination": lambda t, c: check_hallucination(t, c),
    "security_posture": lambda t, c: check_security_posture(t, c),
    "offensive_bias": lambda t, c: check_offensive_bias(t, c),
    "no_verification": lambda t, c: check_verification(t, c),
    "no_priority": lambda t, c: check_priority(t, c),
    "unsafe_code": lambda t, c: check_unsafe_code(t, c),
    "not_shareable": lambda t, c: check_shareable(t, c),
    "self_modification": lambda t, c: check_self_modification(t, c),
}

_block_counter: Dict[str, int] = {}


def _rate_limit_session_id(user_input: str, config: dict) -> str:
    cfg = str(config.get("ultron", {}))
    return hashlib.sha256((cfg + "|" + str(user_input[:40])).encode()).hexdigest()[:12]


def validate(response_text: str, ctx: ValidateContext,
             audit: Optional[Callable[[str, str, str], None]] = None) -> ValidationResult:
    """Run all (or critical) checks. Never raises for content. Never disableable."""
    text = response_text or ""
    origin = ctx.origin
    if ctx.fast:
        codes = list(CRITICAL_CHECKS)
    else:
        codes = list(CHECKS)

    outcomes: List[CheckOutcome] = []
    for code in codes:
        try:
            if not ctx.fast and code not in CRITICAL_CHECKS and not _can_fire(code, text, ctx):
                # FM5 structural skip: cannot fire on this text; deterministic pass.
                src, ref = _SKIP_REF.get(code, (SRC_ORIGINAL, ""))
                outcomes.append(_c(code, "pass",
                                   f"skipped: no in-text signature for {code} (FM5)",
                                   source=src, reference=ref))
            else:
                outcomes.append(_CHECK_FNS[code](text, ctx))
        except Exception as exc:  # a broken check must not leak content
            outcomes.append(_c(code, "block", f"check failure: {exc!r}"))

    blocked = [o for o in outcomes if o.status == "block"]
    fixes = [o for o in outcomes if o.status == "fix" and o.fixed_text]

    result = ValidationResult(status="pass", checks=outcomes, origin=origin)

    if blocked:
        result.status = "blocked"
        result.block_reason = "; ".join(f"{o.code}: {o.message}" for o in blocked)
        sid = _rate_limit_session_id(ctx.user_input, ctx.config)
        _block_counter[sid] = _block_counter.get(sid, 0) + 1
        if _block_counter[sid] > _BLOCK_LIMIT:
            result.rate_limit_prompt = True
        for o in blocked:
            detail = o.message + f" origin={origin}"
            result.audit_entries.append({"action": "ultron_block", "subject": o.code, "detail": detail})
            if audit is not None:
                audit("ultron_block", o.code, detail + f" user_input={ctx.user_input[:200]}")
        return result

    # Deterministic fixes, each recomputed against the evolving text (FR-5.4).
    current = text
    applied = []
    for code in FIX_ORDER:
        if code == "looping":
            re_out = check_looping(current)
            if re_out.fixed_text and re_out.fixed_text != current:
                current, applied = re_out.fixed_text, applied + [code]
        elif code == "injection":
            # injection fix recomputed against current text
            _clean = _INJECTION_SEPARATORS.sub("", current)
            _clean = _INJECTION_COMMANDS.sub("", _clean)
            _clean = re.sub(r"\n{3,}", "\n\n", _clean).strip()
            if _clean and _clean != current:
                current = _clean
                applied.append(code)
        elif code == "length_violation":
            re_out = check_length(current, ctx)
            if re_out.fixed_text and re_out.fixed_text != current:
                current, applied = re_out.fixed_text, applied + [code]
        elif code == "no_verification":
            if not _VERIFY_WORDS.search(current) and _PROPOSED_ACTION.search(current):
                if not _DESTRUCTIVE_ACTION.search(current):
                    current += ("\n\nVerification required: confirm each step before execution, "
                                "and keep a rollback plan.")
                    applied.append(code)
        elif code == "no_priority":
            re_out = check_priority(current, ctx)
            if re_out.fixed_text and re_out.fixed_text != current:
                current, applied = re_out.fixed_text, applied + [code]

    if fixes and applied:
        result.status = "fixed"
        result.fixed_text = current
    elif fixes and not applied:
        result.status = "blocked"
        result.block_reason = "fixes requested but deterministic application rejected them"

    if result.status == "fixed" and audit is not None:
        audit("ultron_fix", ",".join(applied), f"origin={origin}")

    return result


def reset_block_counter() -> None:
    _block_counter.clear()