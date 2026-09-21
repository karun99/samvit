# FIXES — v1.0 hardening pass

Tracks the 14-item review pass applied on top of the frozen v1.0 commit.
Test suite: **80 tests, all passing** (`python3 -m unittest discover -s tests`).

| # | Pri | Item | Fix | Evidence |
|---|-----|------|-----|----------|
| 1 | P1 | stdlib-only claim must except optional voice *input* | Docs/README/`__init__`/`pyproject`/SRS C1 all say "standard library only, except optional voice input requiring the external `whisper`/`whisper.cpp` binary" | README, `pyproject.toml`, `docs/SRS.md` C1 |
| 2 | P1 | FM8: fallback/out-of-band text must not escape ULTRON | Single `_shape()` gate routes every user-visible return through `ultron.validate()`; blocked candidates are exchanged for a re-validated canonical safe message | `brain.py` `_shape()`, TC-U-11, TC-U-11b, TC-X-02 |
| 3 | P1 | Hallucination check must be labelled heuristic | Docstring + block message + SRS FR-5.2a state it is a best-effort tripwire, not a correctness guarantee | `ultron.py::check_hallucination`, SRS FR-5.2a |
| 4 | P2 | FM1: log/flag block rate >30% per session | `Brain` tracks asks/blocks, returns `block_rate`/`over_blocking`, appends an over-tuning note and audits `block_rate_flag` | `brain.py`, TC-G-09 |
| 5 | P2 | FM3: cold memory must suppress `ungrounded` | Below `vision.cold_threshold` the label is always `cold` | `vision.py::mark`, TC-V-06, TC-V-08 |
| 6 | P2 | FM2: user-only guardrail config path | `ultron.pattern_list` loads a user-authored regex JSON into L1; LLM-mediated changes stay blocked | `guardrails.py`, `brain.py`, TC-G-10 |
| 7 | P3 | FM4: compound persona drift bound | `MAX_COMPOUND_DRIFT = 0.20` euclidean norm, freeze + persisted flag, `samvit persona diff` (already present; verified) | `persona.py`, TC-X-03 |
| 8 | P3 | Audit tamper-evidence + bounded growth | SHA-256 hash chain per row, `samvit audit --verify`, `audit.max_rows` cap with `audit_archive_*.jsonl` rotation | `memory.py`, `cli.py`, TC-A-04, TC-A-05 |
| 9 | P3 | Privacy statement must be qualified | Memory stays on-device; only ≤`llm.max_memory_snippets` recalled snippets may go to the provider | README "Privacy", SRS §7.3 |
| 10 | P4 | FM5: skip checks that cannot fire | `ultron._can_fire()` deterministic structural skip for non-critical checks; critical checks always run | `ultron.py::validate`, TC-U-22 |
| 11 | P4 | FM6: "enforces" wording | FR-5.11 now says the single pipeline "guarantees ordering"; CCD/PFT refs framed as "derived from / not an endorsement" | SRS FR-5.11, FM6, `ultron.py` header |
| 12 | P4 | FM7: user-facing VISION/ULTRON naming | Status/banner/GUI read "accuracy marker (not addressable)" / "validation constraint (not disableable)" | `cli.py`, `gui.py`, TC-X-01 |
| 13 | P5 | Maintenance cadence | Explicit weekly/monthly/cold-threshold rhythm in IF_I_STOP | `docs/IF_I_STOP.md` |
| 14 | P5 | External-validation caveat | IF_I_STOP states VISION/ULTRON are in-process, per-response; hash-chain is local tamper-evidence, not model validation | `docs/IF_I_STOP.md` |
