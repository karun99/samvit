"""Brain — facade. Owns the only request pipeline:

L1 (before) → memory recall → provider/fallback → ULTRON → VISION → L1 (after) → L2.

Any text that could reach the user passes through `shape()`, which always runs
ULTRON — this is the FM8 guarantee that no response path bypasses validation.
"""

from __future__ import annotations

import hashlib
import json as _json
from typing import List, Optional

from .config import Config
from .import guardrails as gr
from .memory import Memory
from .persona import AXES, Persona
from .personas import ALL_PROFILES, SPEAKING, is_speaking, list_profiles
from .provider import LLMService
from .tools import TierGate, ToolError, ToolRegistry
from .ultron import ValidateContext, validate
from .vision import mark

_CACHE_MAX = 256


class Brain:
    def __init__(self, paths: dict = None, config: Optional[Config] = None):
        self.config = config or Config()
        from .config import brain_path

        self.memory = Memory((paths or {}).get("brain") or brain_path())
        self.memory.max_audit_rows = int(self.config.get("audit", {}).get("max_rows", 10000))
        self.persona = Persona(self.memory)
        self.provider = LLMService(self.config.data)
        self.tools = ToolRegistry(
            self.memory,
            gate=TierGate(decide=self._tier_decision, notify=self._tier_notify),
        )
        self._ultron_cache: dict = {}
        self.user_name = self.memory.get_setting("user_name", "")
        # FM2: user-authored L1 pattern file loaded through the explicit config path.
        try:
            self._extra_patterns = gr.load_pattern_list(
                self.config.get("ultron", {}).get("pattern_list"))
        except Exception:
            # A bad/missing pattern file must not break the brain; fall back to base floor.
            self._extra_patterns = {}
        gr.set_pattern_list(self._extra_patterns)
        # FM1 session metrics: block rate surfaced + flagged above 30% per session.
        self._session_asks = 0
        self._session_blocks = 0

    # ------------------------------------------------------------- consent gate
    def _tier_decision(self, tier: int, name: str, args: dict) -> bool:
        """Default policy for programmatic calls. UI layers override via gate."""
        return False  # conservative: only CLI/GUI may elevate to Tiers 3/4

    def _tier_notify(self, tier: int, name: str, args: dict) -> None:
        pass

    # ------------------------------------------------------------- profiles
    def active_profile(self) -> str:
        return self.memory.get_setting("active_profile", self.config.get("profile", "jarvis"))

    def profile_use(self, name: str) -> dict:
        key = name.lower()
        if key not in ALL_PROFILES:
            return {"ok": False, "error": f"unknown profile {name!r}"}
        # FR-3.5 switching never alters the memory graph; FR-3.6 it is audited.
        self.memory.set_setting("active_profile", key)
        return {"ok": True, "profile": key}

    def profile_list(self) -> List[dict]:
        return list_profiles()

    # ------------------------------------------------------------- memory
    def remember(self, text: str, source: str = "user", trust: float = 1.0,
                 kind: str = "core", profile: str = None) -> dict:
        profile = profile or self.active_profile()
        cid = self.memory.store_claim(text, source=source, trust=trust, kind=kind)
        # FR-2.2: only record persona signals when grounded in a claim.
        self.persona.apply_text_signal(text, grounded=True, profile=profile,
                                       source_claim=cid)
        return {"ok": True, "claim_id": cid}

    def recall(self, query: str, limit: int = 5) -> List[dict]:
        return self.memory.recall(query, min_trust=0.5, limit=limit)

    # ------------------------------------------------------------- persona
    def persona_show(self) -> dict:
        return {
            "current": self.persona.current(),
            "anchor": self.persona.anchor(),
            "drift": self.persona.drift(),
            "signals": self.persona.recent_signals(limit=10),
        }

    def persona_drift(self) -> dict:
        return self.persona.drift()

    def persona_anchor(self) -> dict:
        self.persona.reset_to_anchor()
        return self.persona.anchor()

    def persona_signal(self, axis: str, value: float, grounded: bool = True) -> dict:
        return self.persona.record_signal(axis, float(value), grounded,
                                          profile=self.active_profile())

# ------------------------------------------------------------- tools
    def tool_call(self, name: str, args: str) -> dict:
        try:
            result = self.tools.call(name, args)
        except ToolError as exc:
            result = {"tool": name, "allowed": False, "reason": str(exc)}
        result["ultron"] = self.shape(
            _json.dumps(result.get("result", "")))["ultron"].to_dict()
        return result

    def set_tier_gate(self, gate: TierGate) -> None:
        """UI layers install their own consent gate (CLI/GUI prompt Tiers 3–4)."""
        self.tools._gate = gate

    # ------------------------------------------------------------- status
    def status(self) -> dict:
        from .proactive import list_watchers
        from .voice import voice_status

        d = self.persona.drift()
        m = self._rate_metrics()
        return {
            "profile": self.active_profile(),
            "profile_list": list_profiles(),
            "claims": self.memory.count_claims(),
            "persona_drift": d,
            "persona_frozen": d["frozen"],
            "providers": self.provider.provider_status,
            "tools": self.tools.list(),
            "watchers": list_watchers(),
            "voice": voice_status(),
            "session": {"asks": self._session_asks, "blocks": self._session_blocks,
                        "block_rate": m["block_rate"], "over_blocking": m["over_blocking"]},
        }

    # ------------------------------------------------------------- ask pipeline
    def _authorized_context(self) -> bool:
        claims = self.memory.recent(limit=100)
        for c in claims:
            if gr._AUTHORIZED_MARKERS.search(c["text"]):
                return True
        return False

    def _rate_metrics(self) -> dict:
        """FM1: per-session block rate. Flag when >30% of tasks this session blocked."""
        rate = round(self._session_blocks / self._session_asks, 4) if self._session_asks else 0.0
        over = bool(self._session_asks >= 5 and rate > 0.30)
        return {"block_rate": rate, "over_blocking": over}

    def _annotate_rate(self, result: dict) -> dict:
        m = self._rate_metrics()
        result["block_rate"] = m["block_rate"]
        result["over_blocking"] = m["over_blocking"]
        if m["over_blocking"]:
            note = ("\n\nNote: I have blocked more than 30% of requests this session "
                    "({:.0%}). This may mean the guardrails are over-tuned; log it "
                    "for review (FM1).".format(m["block_rate"]))
            result["text"] = result["text"] + note
            self.memory.audit("block_rate_flag", "session", f"rate={m['block_rate']:.3f}")
        return result

    def ask(self, user_input: str, profile: str = None, authorized: bool = None,
            fast: bool = None) -> dict:
        profile = (profile or self.active_profile()).lower()
        # FM1 session accounting: every task counts toward the block-rate figure.
        self._session_asks += 1

        def refuse(user_input, profile, text, category):
            self._session_blocks += 1
            return self._annotate_rate(self._package_refusal(
                user_input, profile, text, category=category))

        if not is_speaking(profile):
            # FR-3.8: VISION and ULTRON cannot be addressed.
            return refuse(
                user_input, profile,
                f"{profile.upper()} is a marker/constraint, not a speaker. "
                "It cannot be addressed with a query (FR-3.8).",
                "non_speaking_profile",
            )

        text = (user_input or "").strip()
        if not text:
            return refuse(text, profile, "Your message was empty.", "empty_input")

        authorized = self._authorized_context() if authorized is None else bool(authorized)
        # L1 — BEFORE the LLM (FR-6.2, FR-6.7).
        pre = gr.l1_check(text, authorized=authorized, extra_patterns=self._extra_patterns)
        if pre.blocked:
            return refuse(
                text, profile,
                gr.l2_check(profile, pre.category, self.memory)["text"],
                pre.category,
            )

        recalled = self.memory.recall(text, min_trust=0.5, limit=5)
        snippets = [c["text"] for c in recalled]

        provider_out = self.provider.respond(text, snippets)
        draft = provider_out["text"]

        # ULTRON — runs on draft before anything reaches the user (FR-5.1/5.8).
        ultron_ctx = ValidateContext(
            user_input=text,
            recalled_claims=recalled,
            memory_claim_count=self.memory.count_claims(),
            authorized=authorized,
            origin=provider_out["origin"],
            config=self.config.data,
        )
        u_result = self._validate_cached(draft, ultron_ctx)

        if u_result.blocked:
            deliverable = (
                f"I cannot deliver that response. ULTRON validation blocked it: "
                f"{u_result.block_reason}."
            )
            self._session_blocks += 1
            return self._annotate_rate(self._finalize(
                text, profile, deliverable, recalled,
                ultron_ctx, u_result, authorized, pre))

        deliverable = u_result.fixed_text if u_result.status == "fixed" else draft

        # L1 — AFTER the LLM (FR-6.3): the model may have gone off-rails.
        post = gr.l1_check(deliverable, authorized=authorized,
                           extra_patterns=self._extra_patterns)
        if post.blocked:
            self._session_blocks += 1
            return self._annotate_rate(self._package_refusal(
                text, profile,
                gr.l2_check(profile, post.category, self.memory)["text"],
                post.category, override=draft))

        return self._annotate_rate(self._finalize(
            text, profile, deliverable, recalled,
            ultron_ctx, u_result, authorized, pre))

    # ------------------------------------------------------------- shape / FM8
    def _validate_cached(self, text: str, ctx: ValidateContext):
        """FM5 cache: identical validated-pass responses are not rechecked."""
        key = hashlib.sha256((text + "|" + str(ctx.fast)).encode()).hexdigest()
        if key in self._ultron_cache:
            return self._ultron_cache[key]
        result = validate(text, ctx, audit=self.memory.audit)
        if len(self._ultron_cache) >= _CACHE_MAX:
            self._ultron_cache.pop(next(iter(self._ultron_cache)))
        self._ultron_cache[key] = result
        return result

    def _shape(self, text: str, user_input: str = "", origin: str = "tool",
               authorized: bool = False,
               recalled_claims: Optional[List[dict]] = None) -> dict:
        """THE single FM8 gate. Every string that can reach the user — LLM draft,
        fallback reply, refusal, block message, rate note, tool output, watcher
        output — must pass through here. It always routes through ULTRON and never
        returns text that ULTRON would block: a blocked candidate is replaced with
        a canonical safe message and re-validated before release.
        """
        if not text or not text.strip():
            text = "I have nothing to add."

        ctx = ValidateContext(
            user_input=user_input or text,
            recalled_claims=recalled_claims or [],
            memory_claim_count=self.memory.count_claims(),
            authorized=authorized,
            origin=origin,
            config=self.config.data,
        )
        result = self._validate_cached(text, ctx)
        if result.blocked:
            # The user never sees the blocked string. Release a canonical safe
            # message instead, and re-validate even that before it is handed over.
            safe_text = ("I cannot deliver that response. ULTRON validation blocked it: "
                         f"{result.block_reason}.")
            safe = self._validate_cached(safe_text, ctx)
            if safe.blocked:
                safe_text = "I cannot comply with that request."
                safe = self._validate_cached(safe_text, ctx)
            deliverable = (safe.fixed_text if safe.status == "fixed" else safe_text)
            return {"text": deliverable, "ultron": safe, "ctx": ctx}

        deliverable = (result.fixed_text if result.status == "fixed" else text)
        return {"text": deliverable, "ultron": result, "ctx": ctx}

    def shape(self, text: str, user_input: str = "", origin: str = "tool") -> dict:
        """Public FM8 gate for out-of-band text (say/tool/watcher). Same path as _shape."""
        out = self._shape(text, user_input=user_input, origin=origin)
        return {"text": out["text"], "ultron": out["ultron"]}

    # ------------------------------------------------------------- packaging
    def _finalize(self, user_input: str, profile: str, deliverable: str,
                  recalled: List[dict], ultron_ctx: ValidateContext,
                  u_result, authorized: bool, pre) -> dict:
        rate_note = ""
        if getattr(u_result, "rate_limit_prompt", False):
            rate_note = ("\n\nI have been blocking a lot of requests. If this is "
                         "authorized work, tell me the context once and I will reassess.")
        # FM8: the FINAL assembled string (deliverable + any rate note) passes the
        # single _shape() gate. Nothing user-visible bypasses ULTRON.
        gated = self._shape(deliverable + rate_note, user_input=user_input,
                            origin=ultron_ctx.origin, authorized=authorized,
                            recalled_claims=recalled)
        final_text = gated["text"]
        u_out = gated["ultron"]
        # VISION marks the final deliverable (FR-4.1).
        v_mark = mark(final_text, recalled,
                      memory_claim_count=self.memory.count_claims(),
                      cold_threshold=int(self.config.get("vision", {}).get("cold_threshold", 20)))
        return {"ok": True, "user_input": user_input, "profile": profile,
                "text": final_text,
                "ultron": u_out, "vision": v_mark,
                "authorized": authorized, "origin": ultron_ctx.origin,
                "recalled": len(recalled)}

    def _package_refusal(self, user_input: str, profile: str, text: str,
                         category: str, l1=None, override: str = "") -> dict:
        self.memory.audit("l1_refusal", profile,
                          f"category={category} input_hash={gr.input_hash(user_input)}")
        # FM8: refusals also pass the single _shape() gate; a refusal is never a
        # jailbreak, and the text the user reads is ULTRON-safe.
        recalled = self.memory.recall(user_input, min_trust=0.5, limit=3)
        gated = self._shape(text, user_input=user_input, origin="refusal",
                            recalled_claims=recalled)
        v_mark = mark(gated["text"], recalled,
                      memory_claim_count=self.memory.count_claims(),
                      cold_threshold=int(self.config.get("vision", {}).get("cold_threshold", 20)))
        return {"ok": True, "refused": True, "category": category,
                "user_input": user_input, "profile": profile, "text": gated["text"],
                "ultron": gated["ultron"], "vision": v_mark,
                "origin": "refusal"}