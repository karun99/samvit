"""Samvit GUI — optional Tkinter desktop interface (Appendix D).

Same brain facade as the CLI, same constraints: VISION/ULTRON cannot be
addressed as personas, the accuracy mark is suppressed when memory is cold,
and ULTRON can never be disabled.
"""

from __future__ import annotations

import threading
from typing import Optional


class SamvitGUI:
    """Tkinter chat front-end. Constructed lazily so `samvit gui` can give a
    friendly error when Tkinter is missing (some Linux distros need python3-tk)."""

    def __init__(self, brain):
        self.brain = brain
        self.root = None
        self._widgets = {}
        self._tk = None
        self._ttk = None
        self._scrolledtext = None
        self._messagebox = None

        # VISION and ULTRON are active on every response; only speaking profiles
        # are selectable.
        self.profile_var = None
        self.status_var = None
        self.ultron_var = None
        self.cold_var = None

    # ------------------------------------------------------------- build
    def _import_tk(self):
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk

        self._tk = tk
        self._ttk = ttk
        self._scrolledtext = scrolledtext
        self._messagebox = messagebox
        return True

    def run(self) -> int:
        try:
            if not self._import_tk():
                return 1
        except Exception as exc:
            print(f"samvit gui needs Tkinter. Install it: "
                  f"(Debian/Ubuntu: sudo apt install python3-tk) error={exc!r}")
            return 1

        tk = self._tk
        try:
            self.root = tk.Tk()
        except Exception as exc:
            print(f"samvit gui could not open a display: {exc!r} "
                  f"(no DISPLAY here? use `samvit chat` in a terminal)")
            return 1
        self.root.title("Samvit — one memory, five voices")
        self.root.geometry("820x560")
        self.root.minsize(640, 420)

        self.profile_var = tk.StringVar(value=self.brain.active_profile())
        self.status_var = tk.StringVar(value="VISION: active (marker only)")
        self.ultron_var = tk.StringVar(value="ULTRON: active (constraint only)")
        self.cold_var = tk.StringVar(value="")

        self._build_top(tk)
        self._build_chat(tk)
        self._build_input(tk)

        # FM3: cold-memory indicator — never show a misleading `ungrounded`.
        claims = self.brain.memory.count_claims()
        threshold = int(self.brain.config.get("vision", {}).get("cold_threshold", 20))
        if claims < threshold:
            self.cold_var.set(f"memory: cold ({claims}/{threshold} claims — marks suppressed)")

        # Install the GUI consent gate for tool tiers 3 and 4 (FR-7.5/7.6).
        from .tools import TierGate

        self.brain.set_tier_gate(TierGate(decide=self._decide, notify=self._notify))

        self.root.mainloop()
        return 0

    def _build_top(self, tk) -> None:
        top = self._ttk.Frame(self.root, padding=(8, 6))
        top.pack(fill="x")

        self._ttk.Label(top, text="Profile:").pack(side="left")
        menu = self._ttk.OptionMenu(
            top, self.profile_var, self.brain.active_profile(),
            *("jarvis", "friday", "karen"), command=self._on_profile)
        menu.pack(side="left", padx=(4, 12))

        vl = self._ttk.Label(top, textvariable=self.status_var, foreground="#1a6bb8")
        vl.pack(side="left", padx=6)
        ul = self._ttk.Label(top, textvariable=self.ultron_var, foreground="#b8321a")
        ul.pack(side="left", padx=6)
        cl = self._ttk.Label(top, textvariable=self.cold_var, foreground="#b8860b")
        cl.pack(side="left", padx=6)

    def _build_chat(self, tk) -> None:
        chat = self._scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled", font=("Helvetica", 11),
            bg="#fbfbfb")
        chat.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        chat.tag_config("user", foreground="#1a3a6b", font=("Helvetica", 11, "bold"))
        chat.tag_config("bot", foreground="#111111")
        chat.tag_config("meta", foreground="#777777")
        chat.tag_config("block", foreground="#b8321a")
        chat.tag_config("fix", foreground="#b8860b")
        chat.tag_config("pass", foreground="#1a8f3c")
        chat.tag_config("cold", foreground="#b8860b")
        chat.tag_config("warn", foreground="#b8860b")
        chat.tag_config("sys", foreground="#444444")
        self._chat = chat

    def _build_input(self, tk) -> None:
        bar = self._ttk.Frame(self.root, padding=(8, 6))
        bar.pack(fill="x")

        entry = tk.Entry(bar, font=("Helvetica", 11))
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self._send())
        self.entry = entry

        self._ttk.Button(bar, text="Send", command=self._send).pack(side="left", padx=4)
        self._ttk.Button(bar, text="Speak", command=self._speak_last).pack(side="left", padx=2)
        self._ttk.Button(bar, text="Talk", command=self._push_to_talk).pack(side="left", padx=2)
        self._ttk.Button(bar, text="Status", command=self._show_status).pack(side="left", padx=2)

    # ------------------------------------------------------------- helpers
    def _append(self, text: str, tag: str = "bot") -> None:
        self._chat.configure(state="normal")
        self._chat.insert("end", text + "\n", tag)
        self._chat.see("end")
        self._chat.configure(state="disabled")

    def _on_profile(self, profile) -> None:
        out = self.brain.profile_use(profile)
        if out.get("ok"):
            self._append(f"[profile] switched to {profile}", "sys")

    def _send(self) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        profile = self.profile_var.get()
        self._append(f"you ({profile}): {text}", "user")
        self._append("[…samvit thinking…]", "meta")

        def work():
            return self.brain.ask(text, profile=profile)

        self._thread(work, self._render_answer)

    def _thread(self, work, render) -> None:
        def runner():
            try:
                out = work()
            except Exception as exc:
                out = {"ok": False, "text": f"internal error: {exc!r}"}
            self.root.after(0, lambda: render(out))

        threading.Thread(target=runner, daemon=True).start()

    def _render_answer(self, out: dict) -> None:
        # Drop the placeholder line written by _send.
        self._chat.configure(state="normal")
        self._chat.delete("end-2l", "end-1l")
        self._chat.configure(state="disabled")

        marker = out.get("vision")
        ultron = out.get("ultron")

        if marker is not None and not marker.cold:
            color = {"grounded": "pass", "partial": "warn", "ungrounded": "block",
                     "cold": "cold"}.get(marker.label, "meta")
            self._append(marker.banner(), color)
        elif marker is not None and marker.cold:
            self._append("[memory: cold]", "cold")

        if out.get("refused"):
            self._append(out["text"], "block")
        else:
            self._append(out.get("text", ""), "bot")

        if ultron is not None:
            st = ultron.status
            color = "pass" if st == "pass" else ("fix" if st == "fixed" else "block")
            suffix = f" — {ultron.block_reason}" if ultron.block_reason else ""
            self._append(f"[ultron: {st}]{suffix}", color)

    def _speak_last(self) -> None:
        from .voice import speak

        last = self._chat.get("end-4l", "end-1l").strip()
        if not last:
            return
        self._thread(lambda: speak(last), lambda r: None)

    def _push_to_talk(self) -> None:
        from .voice import asr_push_to_talk, voice_status

        def work():
            st = voice_status()
            if not st["asr_recorder"] or not st["asr_engine"]:
                return st
            return asr_push_to_talk()

        def render(resp):
            if resp.get("ok"):
                self._messagebox.showinfo("Push-to-talk", resp.get("note", "record and transcribe"))
            else:
                self._messagebox.showerror("Voice unavailable", resp.get("error", "unknown"))

        self._thread(work, render)

    def _show_status(self) -> None:
        out = self.brain.status()
        import json

        self._thread(lambda: json.dumps(out, indent=2, default=str), self._show_status_result)

    def _show_status_result(self, text: str) -> None:
        self._append("system status:\n" + text, "sys")

    # ------------------------------------------------------------- consent gate
    def _notify(self, tier: int, name: str, args: dict) -> None:
        # Tier 2 (FR-7.4): notify, then run automatically.
        self._append(f"[tool] tier {tier} {name} executed automatically", "meta")

    def _decide(self, tier: int, name: str, args: dict) -> bool:
        # Tier 3 (FR-7.5): explicit user approval.
        # Tier 4 (FR-7.6): two-stage review.
        if tier == 3:
            return self._messagebox.askyesno(
                "Tool consent (Tier 3)",
                f"Allow tool '{name}' with args {args}?", default="no")
        if tier == 4:
            first = self._messagebox.askyesno(
                "Tool consent — Stage 1/2 (Tier 4)",
                f"Stage one: run '{name}'? This cannot be undone easily.")
            if not first:
                return False
            return self._messagebox.askyesno(
                "Tool consent — Stage 2/2 (Tier 4)",
                f"Stage two confirmation: '{name}' will execute with {args}.")
        return True


def launch(brain) -> int:
    gui = SamvitGUI(brain)
    return gui.run()