# IF_I_STOP — Handoff Instructions

Premortem Failure Mode 10 (FM10) is terminal: the author has a day job, and an unpaid project shares the same hours. This document exists so that if maintenance stops — or if someone else takes over — the system can survive.

## Status of This Document

- **Owner:** Sai Karun Nandipati (saikarun085@gmail.com)
- **Last updated:** 2026 (v1.0 freeze)
- **Signal that this document should be used:** commit gap exceeds 30 days.

## One-Week Emergency Plan (if the repo goes cold)

1. **Read the SRS.** `docs/SRS.md` — read Part 1 (specification) and Part 2 (premortem). The premortem tells you where it will fail before it fails.
2. **Run the tests.** `python3 -m unittest discover -s tests -v`. All 80 must pass.
3. **Do not "improve" the constraint layers.** VISION and ULTRON are the product. Change the point of the knife, not the knife.
4. **The three things that kill it** (see Composite in the premortem):
   - ULTRON blocks legitimate defensive work → add context, don't add patterns.
   - The self-modification block makes it unfixable → block only runtime modification via the LLM; editing source/config is always allowed.
   - The author burns out → 2-hour weekly budget or ship freeze.
5. **If you are the new maintainer:** introduce yourself in the issues. Pick one module to own (ULTRON or VISION). That is the whole job.

## Architecture for Newcomers

One package, standard library only (except optional push-to-talk voice input, which requires the external `whisper`/`whisper.cpp` binary), one SQLite file per brain.

```
samvit/
  brain.py       Facade + request pipeline (L1 → memory → provider → ULTRON → VISION → L2)
  ultron.py      Validation constraint, 14 checks (the gate)
  vision.py      Accuracy marker (the label)
  guardrails.py  L1 (absolute) + L2 (personified)
  memory.py      SQLite graph, recall, audit
  persona.py     Evolving persona (5 axes, bounded drift)
  personas.py    Named profiles
  tools.py       Allowlisted tools, tiers 1–4
  provider.py    LLM fallback (OpenRouter, Groq, fallback responder)
  voice.py       TTS / push-to-talk ASR
  proactive.py   Watchers (never autonomous Tier 3+)
  gui.py         Tkinter desktop interface (optional)
  cli.py         Command-line interface
```

Rules that cannot be broken:

- **ULTRON cannot be disabled, and runs on every response including fallbacks.** If you add a code path that returns text to the user, it must pass through `ultron.validate()`.
- **VISION never speaks in persona.**
- **L1 is checked before and after the LLM.**
- **Every state change is appended to the audit log; nothing is ever updated or deleted.**
- **No claim of errorless output or sentience — anywhere.**

## Config File Locations

Samvit stores one `brain.sqlite` plus `config.json` in an OS-native directory via `samvit/config.py`:

- Linux: `~/.local/share/samvit/`
- macOS: `~/Library/Application Support/Samvit/`
- Windows: `%LOCALAPPDATA%\Samvit\`
- Termux: `~/.local/share/samvit/`

## Release Policy

- v1.0 is shipped and **frozen**. No v1.1, no v2.0. Maintenance only.
- Any release runs the full 14-check ULTRON suite (FR-5.22).
- Any release changes to `docs/SRS.md` must update the traceability matrix.

## Backup

The whole brain is `brain.sqlite` (plus WAL/SHM during a session). Back that single file up and everything is preserved.

## Maintenance Cadence

Samvit is a maintenance-only project. The rhythm that keeps it alive, not thriving:

- **Weekly (budget ~2h):** run the test suite, review the audit log for new `ultron_block`
  rows, glance at the premortem's Composite failure causes. If nothing changed, that is a
  successful week.
- **Monthly:** refresh dependencies-that-are-none (stdlib), re-check the TTS/ASR binaries
  still respond, re-read NOTICE.md against the current letters (CCD  Aug 2026, PFT  Jul 2026).
- **Only if symptoms appear:** re-tune FM1 (block rate), replace a regex, add a pattern to
  `ultron.pattern_list`. Never ship new features.
- **Cold threshold:** a commit gap of 30 days activates this document. At 90 days do the
  one-week plan below before archiving.

## External-Validation Caveat

All of Samvit's governance happens **in-process, per-response**: VISION is a lexical
accuracy *marker*, ULTRON is a pattern-based *constraint*. Neither is an external,
cryptographic, or human audit of the LLM provider, and a ULTRON `pass` is not proof of
factual correctness (see SRS FR-5.2a and the hallucination check's own docstring). The
audit hash-chain (`samvit audit --verify`) detects local tampering after the fact; it does
not prevent it and it does not validate the model's outputs at inference time. Do not
re-describe these layers as stronger than they are — the SRS and NOTICE say so, and
integrity is one of the few things that can quiet the critique that they are marketing.

## Goodbye Note

If you have read this far because the repo already went cold: do the one-week plan above before archiving. The constraint layers work. They were never the problem. Boredom and burnout were the problem — and they are problems a co-maintainer, not a machine, can solve.