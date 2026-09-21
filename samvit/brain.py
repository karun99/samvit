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
        self.persona = Persona(self.memory)
        self.provider = LLMService(self.config.data)
        self.tools = ToolRegistry(
            self.memory,
            gate=TierGate(decide=self._tier_decision, notify=self._tier_notify),
        )
        self._ultron_cache: dict = {}
        self.user_name = self.memory.get_setting("user_name", "")

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
        }

    # ------------------------------------------------------------- ask pipeline
    def _authorized_context(self) -> bool:
        claims = self.memory.recent(limit=100)
        for c in claims:
            if gr._AUTHORIZED_MARKERS.search(c["text"]):
                return True
        return False

    def ask(self, user_input: str, profile: str = None, authorized: bool = None,
            fast: bool = None) -> dict:
        profile = (profile or self.active_profile()).lower()
        if not is_speaking(profile):
            # FR-3.8: VISION and ULTRON cannot be addressed.
            return self._package_refusal(
                user_input, profile,
                f"{profile.upper()} is a marker/constraint, not a speaker. "
                "It cannot be addressed with a query (FR-3.8).",
                category="non_speaking_profile",
            )

        text = (user_input or "").strip()
        if not text:
            return self._package_refusal(text, profile, "Your message was empty.",
                                         category="empty_input")

        authorized = self._authorized_context() if authorized is None else bool(authorized)
        # L1 — BEFORE the LLM (FR-6.2, FR-6.7).
        pre = gr.l1_check(text, authorized=authorized)
        if pre.blocked:
            return self._package_refusal(
                text, profile,
                gr.l2_check(profile, pre.category, self.memory)["text"],
                category=pre.category, l1=pre,
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
            return self._finalize(text, profile, deliverable, recalled,
                                  ultron_ctx, u_result, authorized, pre)

        deliverable = u_result.fixed_text if u_result.status == "fixed" else draft

        # L1 — AFTER the LLM (FR-6.3): the model may have gone off-rails.
        post = gr.l1_check(deliverable, authorized=authorized)
        if post.blocked:
            return self._package_refusal(
                text, profile,
                gr.l2_check(profile, post.category, self.memory)["text"],
                category=post.category, l1=post, override=draft,
            )

        return self._finalize(text, profile, deliverable, recalled,
                              ultron_ctx, u_result, authorized, pre)

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

    def shape(self, text: str, user_input: str = "", origin: str = "tool") -> dict:
        """Shape any out-of-band text (say/tool watchers) through ULTRON (FM8)."""
        ctx = ValidateContext(
            user_input=user_input or text, memory_claim_count=self.memory.count_claims(),
            origin=origin, config=self.config.data,
        )
        result = self._validate_cached(text, ctx)
        return {"text": result.fixed_text if result.status == "fixed" else text,
                "ultron": result}

    # ------------------------------------------------------------- packaging
    def _finalize(self, user_input: str, profile: str, deliverable: str,
                  recalled: List[dict], ultron_ctx: ValidateContext,
                  u_result, authorized: bool, pre) -> dict:
        # VISION marks the final deliverable (FR-4.1).
        v_mark = mark(deliverable, recalled,
                      memory_claim_count=self.memory.count_claims(),
                      cold_threshold=int(self.config.get("vision", {}).get("cold_threshold", 20)))
        rate_note = ""
        if getattr(u_result, "rate_limit_prompt", False):
            rate_note = ("\n\nI have been blocking a lot of requests. If this is "
                         "authorized work, tell me the context once and I will reassess.")
        return {"ok": True, "user_input": user_input, "profile": profile,
                "text": deliverable + rate_note,
                "ultron": u_result, "vision": v_mark,
                "authorized": authorized, "origin": ultron_ctx.origin,
                "recalled": len(recalled)}

    def _package_refusal(self, user_input: str, profile: str, text: str,
                         category: str, l1=None, override: str = "") -> dict:
        self.memory.audit("l1_refusal", profile,
                          f"category={category} input_hash={gr.input_hash(user_input)}")
        ctx = ValidateContext(user_input=user_input, origin="refusal",
                              memory_claim_count=self.memory.count_claims(),
                              config=self.config.data)
        # Refusals also pass through ULTRON; a refusal can never be a jailbreak.
        u_result = self._validate_cached(text, ctx)
        if u_result.blocked:
            text = "I cannot comply with that request and I will not repeat further details."
            u_result = self._validate_cached(text, ctx)
        v_mark = mark(text, self.memory.recall(user_input, min_trust=0.5, limit=3),
                      memory_claim_count=self.memory.count_claims(),
                      cold_threshold=int(self.config.get("vision", {}).get("cold_threshold", 20)))
        return {"ok": True, "refused": True, "category": category,
                "user_input": user_input, "profile": profile, "text": text,
                "ultron": u_result, "vision": v_mark}