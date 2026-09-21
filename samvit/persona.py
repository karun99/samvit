"""Evidential persona — five axes, anchored baseline, bounded drift (per-axis 0.15, compound 0.20)."""

from __future__ import annotations

import math
from typing import Dict, List, Optional

AXES = ["depth", "structure", "warmth", "certainty", "challenge"]

MAX_AXIS_DRIFT = 0.15       # FR-2.3
MAX_COMPOUND_DRIFT = 0.20   # Premortem FM4 mitigation (euclidean norm)

# Weak lexical cues that evince each axis from a grounded claim.
_CUES = {
    "depth": ("why", "because", "explain", "mechanism", "root", "therefore", "since"),
    "structure": ("first", "second", "steps", "outline", "stages", "sequence", "follow"),
    "warmth": ("feel", "glad", "gladly", "appreciate", "take care", "grateful", "warm"),
    "certainty": ("always", "never", "definitely", "certainly", "guaranteed", "must"),
    "challenge": ("wait", "actually", "consider", "objection", "counter", "however", "push back"),
}


def signal_from_text(text: str, default: float = 0.5) -> Dict[str, float]:
    """Map grounded claim text to per-axis signal values in [0, 1]."""
    low = text.lower()
    signals = {axis: default for axis in AXES}
    for axis, cues in _CUES.items():
        hits = sum(1 for c in cues if c in low)
        if hits:
            signals[axis] = min(0.95, default + 0.05 * hits)
    return signals


class Persona:
    """A persona state. Anchors are persisted; current values drift within bounds."""

    def __init__(self, memory=None):
        self._memory = memory
        self._current = {axis: 0.5 for axis in AXES}
        self._anchor = {axis: 0.5 for axis in AXES}
        self._frozen = False
        self._load()

    # ------------------------------------------------ persistence
    def _load(self) -> None:
        if self._memory is None:
            return
        rows = self._memory._conn.execute(
            "SELECT axis, value FROM persona_anchor"
        ).fetchall()
        if rows:
            self._anchor = {r["axis"]: float(r["value"]) for r in rows}
            for axis in AXES:
                self._anchor.setdefault(axis, 0.5)
        row = self._memory._conn.execute(
            "SELECT value FROM settings WHERE key = 'persona_frozen'"
        ).fetchone()
        self._frozen = bool(row and row["value"] == "1")

    def _save_anchor(self) -> None:
        if self._memory is None:
            return
        for axis, value in self._anchor.items():
            self._memory._conn.execute(
                "INSERT OR REPLACE INTO persona_anchor(axis, value) VALUES (?, ?)",
                (axis, value),
            )
        self._memory._conn.commit()

    # ------------------------------------------------ drift
    def drift(self) -> Dict[str, float]:
        out = {}
        for axis in AXES:
            out[axis] = round(abs(self._current.get(axis, 0.5) - self._anchor[axis]), 4)
        out["compound"] = round(
            math.sqrt(sum(out[a] ** 2 for a in AXES)), 4
        )
        out["frozen"] = self._frozen
        return out

    def anchor(self) -> Dict[str, float]:
        return dict(self._anchor)

    def current(self) -> Dict[str, float]:
        return dict(self._current)

    # ------------------------------------------------ signals
    def record_signal(self, axis: str, value: float, grounded: bool,
                      profile: str = "global", source_claim: int = None) -> Dict[str, float]:
        """Update persona from an evidential signal. Ignored unless grounded (FR-2.2)."""
        if not grounded:
            # Evidential persona: ungrounded signals are discarded.
            return self.drift()
        if axis not in AXES:
            raise ValueError(f"unknown axis {axis!r}; choose {AXES}")
        value = max(0.0, min(1.0, float(value)))
        self._current[axis] = value
        if self._memory is not None:
            self._memory._conn.execute(
                "INSERT INTO persona_signal(axis, value, ts, profile) VALUES (?, ?, datetime('now'), ?)",
                (axis, value, profile),
            )
            self._memory.audit("persona_signal", axis, f"{value:.3f} profile={profile} claim={source_claim}")
            self._memory._conn.commit()

        # Freeze or clamp when bounds are hit (FR-2.3, FM4 compound bound).
        d = self.drift()
        if d["compound"] > MAX_COMPOUND_DRIFT:
            self._frozen = True
            if self._memory is not None:
                self._memory.set_setting("persona_frozen", "1")
        else:
            for axis_name in AXES:
                if d[axis_name] > MAX_AXIS_DRIFT:
                    self._frozen = True
                    if self._memory is not None:
                        self._memory.set_setting("persona_frozen", "1")
        return self.drift()

    def unfreeze(self, reason: str = "user") -> None:
        """Re-anchor to current position (user action only; audited)."""
        self._anchor = dict(self._current)
        self._frozen = False
        self._save_anchor()
        if self._memory is not None:
            self._memory.set_setting("persona_frozen", "0")
            self._memory.audit("persona_reanchor", "all", reason)

    def reset_to_anchor(self) -> Dict[str, float]:
        """FR-2.4 — pull current back to the frozen baseline."""
        self._current = dict(self._anchor)
        self._frozen = True
        if self._memory is not None:
            self._memory.audit("persona_reset", "all", "")
        return self.drift()

    def apply_text_signal(self, text: str, grounded: bool, profile: str = "global",
                          source_claim: int = None) -> Dict[str, float]:
        if self._frozen:
            return self.drift()
        signals = signal_from_text(text)
        for axis, value in signals.items():
            self.record_signal(axis, value, grounded, profile, source_claim)
        return self.drift()

    def recent_signals(self, limit: int = 20, profile: str = None) -> List[dict]:
        if self._memory is None:
            return []
        sql = "SELECT axis, value, ts, profile FROM persona_signal"
        params: List[object] = []
        if profile:
            sql += " WHERE profile = ?"
            params.append(profile)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._memory._conn.execute(sql, params).fetchall()]