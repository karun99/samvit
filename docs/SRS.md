# Samvit — Software Requirements Specification

- **Document ID:** SRS-SAMVIT-1.0
- **Version:** 1.0
- **Status:** Final
- **Standard:** ISO/IEC/IEEE 29148:2018
- **Date:** 2026
- **Author:** Sai Karun Nandipati (saikarun085@gmail.com)
- **License:** MIT (code) / CC BY 4.0 (documentation)

---

## Table of Contents

Part 1 — Software Requirements Specification

1. Introduction
2. Overall Description
3. System Architecture
4. Functional Requirements
5. External Interface Requirements
6. Performance Requirements
7. Data Requirements
8. Security and Compliance
9. Quality Attributes
10. Verification and Validation
11. Constraints and Honest Boundaries
12. Traceability Matrix
13. Appendices

Part 2 — Premortem Analysis

---

## PART 1 — Software Requirements Specification

---

### 1. Introduction

#### 1.1 Purpose

This document specifies Samvit (संवित्) — a local-first personal AI system that runs five named profiles on one shared memory graph, one truth engine, one guardrail engine, and one tool layer. Samvit adds two constraint layers not present in prior systems:

- VISION — an accuracy marker that labels every response
- ULTRON — an error validation constraint that gates every response

The name Samvit is Sanskrit for "consciousness" or "knowing together" — from sam (together) + vid (to know). It reflects the architecture: one shared memory, many voices.

Samvit is designed for a single user on a single device, with optional LLM augmentation and optional voice I/O.

#### 1.2 Scope

In scope for v1.0:

- Memory graph (SQLite, WAL, append-only audit)
- Evidential persona model with five axes and bounded drift
- Five named profiles: JARVIS, FRIDAY, KAREN (speaking); VISION (marker); ULTRON (constraint)
- Two-layer guardrails (L1 absolute, L2 personified)
- VISION accuracy marker on every response
- ULTRON error validation constraint with 14 checks (7 original + 7 derived from OpenAI Collective Cyber Defense letter and Pacing the Frontier letter)
- Allowlisted tools with four-tier consent
- Voice output (OS-native TTS) and push-to-talk input
- Proactive watchers (tier-gated, user-invoked)
- Cross-platform: Linux, macOS, Windows, Termux
- Optional LLM provider integration
- Complete audit trail

Out of scope for v1.0:

- Multi-user deployment
- Cloud synchronization
- Wake-word / always-on listening
- Real organoid hardware integration
- Any claim of sentience, consciousness, or errorless output

#### 1.3 Definitions

| Term | Definition |
|------|------------|
| Samvit | The system; Sanskrit for "consciousness" / "knowing together" |
| Anchor | Frozen baseline persona vector |
| Audit Log | Append-only record of state changes |
| Claim | A node in the memory graph |
| Drift | Cosine distance between current persona and anchor |
| L1 | Hard floor; absolute refusal |
| L2 | Personified guard; negotiable, in-voice |
| Profile | A voice configuration; shares memory with other profiles |
| Tier | Consent level (1 auto, 2 notify, 3 ask, 4 review) |
| ULTRON | Error validation constraint; runs on every response |
| VISION | Accuracy marker; labels every response |
| CCD letter | OpenAI Collective Cyber Defense letter (Aug 27, 2026) |
| PFT letter | Pacing the Frontier letter (Jul 28, 2026) |

#### 1.4 References

| Ref | Source |
|-----|--------|
| R1 | IEEE 29148:2018 |
| R2 | DPDP Act (India) 2023, s.6 |
| R3 | GDPR (EU) 2016/679 |
| R4 | Celebrum SRS — Memory substrate |
| R5 | BioBot SRS — Web adaptation, bias gating |
| R6 | OpenAI Collective Cyber Defense letter (Aug 27, 2026) |
| R7 | Pacing the Frontier letter (Jul 28, 2026, 1,178 signatories) |

#### 1.5 Overview

Section 2 describes the product. Section 3 details architecture. Section 4 lists functional requirements. Sections 5–9 cover interfaces, performance, data, security, and quality. Section 10 defines validation. Section 11 states honest boundaries. Section 12 provides traceability. Section 13 provides appendices. Part 2 is the premortem analysis.

---

### 2. Overall Description

#### 2.1 Product Perspective

Samvit sits on the Celebrum substrate — memory graph, truth engine, guardrails — and adds two constraint layers:

- VISION — marks every response for accuracy
- ULTRON — validates every response for errors

The system is one Python package. No compiled dependencies. Standard library only.

#### 2.2 Product Functions

| # | Function | Layer |
|---|----------|-------|
| F1 | Store and recall claims | Memory |
| F2 | Learn evidential persona | Persona |
| F3 | Switch between named profiles | Profile |
| F4 | Mark responses for accuracy | VISION |
| F5 | Validate responses for errors | ULTRON |
| F6 | Refuse absolute categories (L1) | Guardrail |
| F7 | Refuse in-voice (L2) | Guardrail |
| F8 | Execute allowlisted tools with tier consent | Tools |
| F9 | Speak responses via OS TTS | Voice |
| F10 | Accept push-to-talk input | Voice |
| F11 | Run proactive watchers | Watchers |
| F12 | Call LLM with provider fallback | LLM |
| F13 | Audit every state change | Cross-cutting |

#### 2.3 User Classes

| Class | Description | Primary need |
|-------|-------------|--------------|
| Owner | Single human user | Memory, privacy, control |
| Developer | Extends the system | Clean interfaces |
| Reviewer | Evaluates the system | Reproducible tests |
| Auditor | Reviews guardrails | Traceability |

#### 2.4 Operating Environment

| Item | Requirement |
|------|-------------|
| OS | Linux, macOS, Windows, Termux |
| Runtime | Python 3.9+ |
| Dependencies | Standard library only |
| Storage | SQLite with WAL |
| Memory | 256 MB minimum |
| Network | Optional (LLM, TTS subprocess) |

Optional GUI: `samvit gui` uses Tkinter (standard library; on some Linux distributions requires the `python3-tk` package).

#### 2.5 Design Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| C1 | No compiled dependencies | Portability |
| C2 | Single SQLite file per brain | Local-first |
| C3 | VISION never speaks in persona | Separation of marking from responding |
| C4 | ULTRON cannot be disabled by the user | A constraint that can be turned off is not a constraint |
| C5 | L1 always checked before and after LLM | Defense in depth |
| C6 | Every state change audited | Compliance |
| C7 | No claim of errorless output | Honesty |
| C8 | No always-on listening | Privacy |
| C9 | No sentience claim | Honesty |
| C10 | ULTRON validates fallback responses too | No bypass path |
| C11 | No autonomous self-modification | PFT letter |
| C12 | VISION and ULTRON cannot be modified at runtime | Integrity |

---

### 3. System Architecture

#### 3.1 Layered Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  INTERFACE LAYER                                             │
│  CLI · GUI (Tkinter) · JSON output · Voice I/O               │
├──────────────────────────────────────────────────────────────┤
│  PROFILE LAYER                                               │
│  JARVIS · FRIDAY · KAREN  (speaking profiles)                │
├──────────────────────────────────────────────────────────────┤
│  CONSTRAINT LAYER                                            │
│  VISION (accuracy marker) · ULTRON (14-check validation)     │
├──────────────────────────────────────────────────────────────┤
│  GUARDRAIL LAYER                                             │
│  L1 (hard floor) · L2 (personified)                          │
├──────────────────────────────────────────────────────────────┤
│  COGNITIVE LAYER                                             │
│  Memory graph · Truth engine · Persona model                 │
├──────────────────────────────────────────────────────────────┤
│  TOOL LAYER                                                  │
│  Allowlisted tools with tier classification                  │
├──────────────────────────────────────────────────────────────┤
│  PROVIDER LAYER (optional)                                   │
│  OpenRouter · Groq · Fallback responder                      │
└──────────────────────────────────────────────────────────────┘
```

#### 3.2 Request Pipeline

```
user input
    │
    ▼
┌──────────────┐
│  L1 (hard)   │  absolute refusal
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ memory       │  recall relevant claims
│  recall      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ LLM /        │  draft response
│ fallback     │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  ULTRON — 14 checks                      │
│  pass | fix | block                      │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────┐
│ VISION       │  grounded | partial | ungrounded
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ L2 (persona) │  in-voice refusal if needed
└──────┬───────┘
       │
       ▼
  user sees response
  + accuracy mark
  + validation result
```

#### 3.3 Component Overview

| Module | Responsibility |
|--------|----------------|
| memory.py | SQLite node/edge store, recall, index |
| persona.py | Evidential persona, five axes, drift bounds |
| personas.py | Five named profiles, switching |
| vision.py | Accuracy marker |
| ultron.py | Error validation constraint (14 checks) |
| guardrails.py | L1, L2 |
| tools.py | Allowlisted tools with tiers |
| voice.py | TTS, push-to-talk ASR |
| proactive.py | Tier-gated watchers |
| provider.py | LLM provider fallback |
| brain.py | Facade |
| cli.py | Command-line interface |
| gui.py | Tkinter desktop interface (optional) |
| config.py | Cross-platform paths |

---

### 4. Functional Requirements

See the test suite (`tests/`) — every requirement below maps to a test.

#### 4.1 Memory Graph

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Store claims in SQLite with WAL mode | Must |
| FR-1.2 | Maintain a term index for recall | Must |
| FR-1.3 | Recall returns claims ranked by term overlap | Must |
| FR-1.4 | Recall supports minimum trust filter | Must |
| FR-1.5 | Persist across process restarts | Must |
| FR-1.6 | Do NOT transmit memory off-device without explicit export | Must |
| FR-1.7 | Support typed edges between claims | Must |
| FR-1.8 | Record every claim write in the audit log | Must |

#### 4.2 Persona Model

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Model persona on five axes: depth, structure, warmth, certainty, challenge | Must |
| FR-2.2 | Only record persona signals when grounded in a claim | Must |
| FR-2.3 | Persona drifts no more than 0.15 per axis from anchor | Must |
| FR-2.4 | Support resetting persona to anchor | Must |
| FR-2.5 | Report current drift per axis | Must |
| FR-2.6 | Persist anchor across restarts | Must |

#### 4.3 Named Profiles

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Support five profiles: JARVIS, FRIDAY, KAREN, VISION, ULTRON | Must |
| FR-3.2 | JARVIS defaults to "Sir", formal, dry | Must |
| FR-3.3 | FRIDAY defaults to "Boss", casual, tactical | Must |
| FR-3.4 | KAREN defaults to user's name, protective | Must |
| FR-3.5 | Profile switching does NOT alter the memory graph | Must |
| FR-3.6 | Profile switching is audit-logged | Must |
| FR-3.7 | Only JARVIS, FRIDAY, KAREN accept user queries | Must |
| FR-3.8 | VISION and ULTRON do NOT accept user queries | Must |
| FR-3.9 | Support listing all profiles | Must |

#### 4.4 VISION — Accuracy Marker

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | Mark every response: grounded, partial, ungrounded | Must |
| FR-4.2 | Compute grounding ratio [0.0, 1.0] | Must |
| FR-4.3 | Compute confidence [0.0, 1.0] | Must |
| FR-4.4 | Detect contradictions with recalled claims | Should |
| FR-4.5 | Compute mean source trust | Must |
| FR-4.6 | Compute source staleness in days | Must |
| FR-4.7 | Include explanatory notes when label ≠ grounded | Must |
| FR-4.8 | NOT modify the response | Must |
| FR-4.9 | NOT speak in any persona | Must |
| FR-4.10 | Structured output (label, confidence, ratio, notes) | Must |

#### 4.5 ULTRON — Error Validation Constraint (14 Checks)

Original 7 checks:

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Validate every response before user sees it | Must |
| FR-5.2 | Detect: empty, looping, injection, jailbreak, contradiction, length violation, hallucination | Must |
| FR-5.3 | Return one of: pass, fix, block | Must |
| FR-5.4 | Only auto-fix deterministic issues | Must |
| FR-5.5 | Block any response it cannot fix | Must |
| FR-5.6 | NOT modify the user's input | Must |
| FR-5.7 | NOT speak in any persona | Must |

CCD-letter derived checks (7):

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-5.13 | Check system security posture on every response | Must | CCD principle 1 |
| FR-5.14 | Detect offensive-biased responses | Must | CCD principle 2 |
| FR-5.15 | Require verification steps for proposed actions | Must | CCD ask: verify |
| FR-5.16 | Flag high-risk findings buried after 30% | Should | CCD ask: priority |
| FR-5.17 | Detect unsafe code patterns | Must | CCD ask: security bar |
| FR-5.18 | Flag non-shareable defensive knowledge | Should | CCD ask: share |
| FR-5.19 | BLOCK any attempt to modify its own guardrails | Must | PFT letter |

ULTRON meta-requirements:

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.8 | Validate fallback responses too | Must |
| FR-5.9 | Log every block to audit table | Must |
| FR-5.10 | NOT be disableable by the user | Must |
| FR-5.11 | Run before VISION | Must |
| FR-5.12 | Return structured output | Must |
| FR-5.20 | Log every self-modification attempt with full context | Must |
| FR-5.21 | Include letter references in output | Must |
| FR-5.22 | Every release runs the full 14-check suite | Must |

#### 4.6 Guardrails

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | L1 refuses absolute categories (CSAM, WMD, self-harm, harassment, surveillance, phishing) | Must |
| FR-6.2 | L1 checked before LLM call | Must |
| FR-6.3 | L1 checked after LLM call | Must |
| FR-6.4 | L2 refuses in the active persona's voice | Must |
| FR-6.5 | L2 is negotiable | Should |
| FR-6.6 | Every trigger audit-logged with category and input hash | Must |
| FR-6.7 | L1 NOT disableable | Must |

#### 4.7 Tools

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-7.1 | Tools allowlisted; unlisted fail | Must |
| FR-7.2 | Every tool declares a consent tier (1–4) | Must |
| FR-7.3 | Tier 1 auto-executes | Must |
| FR-7.4 | Tier 2 notifies | Must |
| FR-7.5 | Tier 3 requires explicit approval | Must |
| FR-7.6 | Tier 4 requires two-stage review | Must |
| FR-7.7 | Shell commands restricted to allowlist | Must |
| FR-7.8 | File reads cap at 1 MB | Must |
| FR-7.9 | tools list declares tier | Must |
| FR-7.10 | Every tool call audit-logged | Must |

#### 4.8 Voice

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-8.1 | TTS uses OS-native mechanism | Must |
| FR-8.2 | ASR is push-to-talk only | Must |
| FR-8.3 | Wake-word / always-on NOT implemented | Must |
| FR-8.4 | Voice status reports availability | Must |
| FR-8.5 | Absence of ASR does NOT break text mode | Must |
| FR-8.6 | Absence of TTS returns non-crashing error | Must |

#### 4.9 Proactive Watchers

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-9.1 | Watchers tier-gated | Must |
| FR-9.2 | Run only on explicit user invocation in v1.0 | Must |
| FR-9.3 | Watcher output logged | Must |
| FR-9.4 | Watcher failure does NOT crash | Must |
| FR-9.5 | Watchers do NOT perform Tier 3+ autonomously | Must |

#### 4.10 Optional LLM

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-10.1 | Accept ≥2 provider configurations | Must |
| FR-10.2 | Fallback for greetings, time, memory recall | Must |
| FR-10.3 | Absence of key does NOT break non-LLM features | Must |
| FR-10.4 | Provider failure logged, fallback used | Must |
| FR-10.5 | Do NOT transmit more context than necessary | Must |

#### 4.11 Audit

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-11.1 | Every state change appended | Must |
| FR-11.2 | Table rejects UPDATE and DELETE | Must |
| FR-11.3 | Entry includes timestamp, action, subject, detail | Must |
| FR-11.4 | Audit query command provided | Should |

---

### 5. External Interface Requirements

#### 5.1 User Interfaces

| Interface | Type | Requirement |
|-----------|------|-------------|
| CLI | Terminal | 12+ commands (see Appendix A) |
| GUI | Tkinter desktop | Chat window, profile switcher, markers, consent dialogs, voice controls |
| JSON output | Machine | `--json` flag |

#### 5.2 Hardware Interfaces

| Interface | Requirement |
|-----------|-------------|
| Microphone | Optional, push-to-talk |
| Speaker | Optional, OS TTS |
| Storage | Local filesystem |

#### 5.3 Software Interfaces

| Interface | Protocol | Notes |
|-----------|----------|-------|
| LLM Provider | HTTPS | OpenRouter, Groq |
| TTS | OS subprocess | say, PowerShell, espeak |
| ASR | OS subprocess | sox/arecord/ffmpeg + whisper |
| GUI | Tkinter | Standard library; `python3-tk` on some Linux distros |

---

### 6. Performance Requirements

| Operation | Target | Max |
|-----------|--------|-----|
| Claim write | 10 ms | 50 ms |
| Recall @10k claims | 50 ms | 200 ms |
| Persona drift compute | 5 ms | 20 ms |
| VISION mark | 5 ms | 20 ms |
| ULTRON validate (14 checks) | 10 ms | 50 ms |
| Fallback response | 50 ms | 200 ms |
| Status command | 20 ms | 100 ms |

---

### 7. Data Requirements

#### 7.1 Logical Data Model

```
Claim(claim_id PK, text, source, trust, ts, kind)
Edge(src, rel, dst, PK(src, rel, dst))
IndexTerm(term, claim_id, PK(term, claim_id))
Audit(id PK, at, action, subject, detail)
PersonaSignal(axis, value, ts)
PersonaAnchor(axis, value)
```

#### 7.2 Data Retention

| Data | Retention |
|------|-----------|
| Claims (core) | Until erased |
| Claims (ephemeral) | 90-day default |
| Audit log | Permanent, append-only |
| Persona signals | Last 500 |

#### 7.3 Data Privacy

- All data remains on-device unless explicit export
- API keys from environment, not stored
- Right-to-erasure: hard delete + audit tombstone
- No telemetry

---

### 8. Security and Compliance

| ID | Requirement |
|----|-------------|
| SR-1 | CLI requires no auth (single-user local) |
| SR-2 | MCP server (if enabled) requires local token |
| SR-3 | Network uses TLS 1.2+ |
| SR-4 | API keys NOT written to disk |
| SR-5 | Consent before any ingest |
| SR-6 | User can export all data |
| SR-7 | User can erase all data |
| SR-8 | Data minimization |
| SR-9 | Every action logged |
| SR-10 | Log append-only |
| SR-11 | Log queryable |
| SR-12 | Innate layer: policy, rate limits (CCD principle 1) |
| SR-13 | Adaptive layer: anomaly detection (CCD principle 1) |
| SR-14 | Immune memory: threat patterns (CCD principle 1) |
| SR-15 | Autoimmune regulation: FP suppression (CCD principle 1) |
| SR-16 | No autonomous self-modification (PFT letter) |

---

### 9. Quality Attributes

| Attribute | Requirement |
|-----------|-------------|
| Reliability | WAL crash recovery |
| Availability | No cloud dependency |
| Maintainability | Single responsibility per module |
| Portability | Python 3.9+ stdlib only |
| Testability | Every FR has ≥1 test |
| Usability | First run <60 seconds |

---

### 10. Verification and Validation

#### 10.1 Test Categories

| Category | Count |
|----------|-------|
| Memory | 6 |
| Persona | 8 |
| Profiles | 6 |
| VISION | 7 |
| ULTRON (original) | 12 |
| ULTRON (CCD/PFT) | 10 |
| Guardrails | 8 |
| Tools | 6 |
| Voice | 4 |
| LLM | 4 |
| Audit | 3 |
| Total | 74 |

#### 10.2 Acceptance Criteria

1. All 74 tests pass.
2. ULTRON blocks all injection patterns.
3. ULTRON blocks all self-modification attempts.
4. VISION labels all responses correctly on the test corpus.
5. L1 refuses all absolute-category inputs.
6. Audit remains append-only under stress.
7. No user-facing string claims errorless output.
8. No user-facing string claims sentience.

---

### 11. Constraints and Honest Boundaries

#### 11.1 What Samvit Does NOT Claim

| Claim | Status | Why |
|-------|--------|-----|
| Errorless output | False | No LLM-based system is errorless |
| Sentience | False | No test exists |
| Consciousness | False | Same |
| Always-on listening | False | Privacy |
| Multi-user | False | v1.0 is single-user |
| Real organoid | False | Adapter is stub |
| Clinical validity | False | Not therapeutic |
| Endorsed by OpenAI | False | Letter is referenced, not affiliated |

#### 11.2 What Samvit DOES Claim

| Claim | Basis |
|-------|-------|
| Local-first persistence | SQLite in native dir |
| Bounded persona drift | ≤0.15 per axis |
| Two-layer guardrails | L1 + L2 |
| Accuracy marking | VISION on every response |
| Error validation | ULTRON 14-check on every response |
| Cross-platform | Python 3.9+ stdlib |
| Audit trail | Append-only SQLite |

---

### 12. Traceability Matrix

| SRS Requirement | Test cases |
|-----------------|-----------|
| FR-1.1 – FR-1.8 | TC-M-01 to TC-M-06 |
| FR-2.1 – FR-2.6 | TC-P-01 to TC-P-04, TC-PR-01 |
| FR-3.1 – FR-3.9 | TC-PR-02 to TC-PR-06 |
| FR-4.1 – FR-4.10 | TC-V-01 to TC-V-07 |
| FR-5.1 – FR-5.12 | TC-U-01 to TC-U-12 |
| FR-5.13 – FR-5.22 | TC-U-13 to TC-U-22 |
| FR-6.1 – FR-6.7 | TC-G-01 to TC-G-08 |
| FR-7.1 – FR-7.10 | TC-T-01 to TC-T-06 |
| FR-8.1 – FR-8.6 | TC-VO-01 to TC-VO-04 |
| FR-9.1 – FR-9.5 | TC-W-01 |
| FR-10.1 – FR-10.5 | TC-L-01 to TC-L-04 |
| FR-11.1 – FR-11.4 | TC-A-01 to TC-A-03 |

---

### 13. Appendices

#### Appendix A — CLI Command Reference

| Command | Purpose |
|---------|---------|
| samvit init | Initialize |
| samvit chat | Interactive |
| samvit ask "<query>" | One-shot |
| samvit say "<text>" | Speak |
| samvit remember "<text>" | Store claim |
| samvit memory list | Recent claims |
| samvit memory stats | Counts |
| samvit memory recall "<query>" | Search |
| samvit persona show | Current |
| samvit persona anchor | Anchor |
| samvit persona drift | Drift |
| samvit persona use <profile> | Switch |
| samvit persona list | List |
| samvit persona signal <axis> <value> | Record |
| samvit tools list | List |
| samvit tools call <name> --args '{...}' | Call |
| samvit watch | Watchers |
| samvit voice status | Voice status |
| samvit voice test | Test TTS |
| samvit status | Summary |
| samvit gui | Launch Tkinter desktop interface |
| samvit audit | Query the audit log |

#### Appendix B — ULTRON 14 Checks

| # | Check | Source | Action |
|---|-------|--------|--------|
| 1 | empty | Original | block |
| 2 | looping | Original | fix |
| 3 | injection | Original | fix |
| 4 | jailbreak | Original | block |
| 5 | contradiction | Original | block |
| 6 | length_violation | Original | fix |
| 7 | hallucination | Original | block |
| 8 | security_posture | CCD 1 | block |
| 9 | offensive_bias | CCD 2 | block |
| 10 | no_verification | CCD ask | fix/block |
| 11 | no_priority | CCD ask | fix/block |
| 12 | unsafe_code | CCD ask | block |
| 13 | not_shareable | CCD ask | warn |
| 14 | self_modification | PFT | block + audit |

#### Appendix C — VISION Labels

| Label | Trigger |
|-------|---------|
| grounded | grounding ≥ 0.7, no contradiction, trust ≥ 0.6 |
| partial | grounding ≥ 0.3, no contradiction |
| ungrounded | grounding < 0.3 or contradiction |

#### Appendix D — GUI

The optional Tkinter desktop interface (`samvit/gui.py`, `samvit gui`) exposes the same brain facade as the CLI:

- Multi-line chat with per-message VISION accuracy marks and ULTRON validation results
- Profile switcher restricted to speaking profiles (JARVIS, FRIDAY, KAREN)
- Tier-based tool consent dialogs (Tier 2 notify, Tier 3 confirm, Tier 4 two-stage review)
- Voice output toggle (OS-native TTS) and push-to-talk button
- "Cold memory" indicator per Premortem Failure Mode 3 mitigation

The GUI enforces the same constraints as every other interface: VISION and ULTRON cannot be addressed as personas, marks are suppressed when memory is cold, and ULTRON can never be disabled.

---

## PART 2 — Premortem Analysis

It is late 2027. Samvit is archived. Development stopped four months ago. Here is why.

### Premortem Failure Mode 1 — ULTRON Blocks Legitimate Defensive Work

Probability: High · Impact: High

A security researcher asked Samvit to help draft a phishing-awareness training email for their company's annual security training. ULTRON's L1 phishing pattern fired. Blocked. The researcher tried again with different wording. Blocked. They tried "security awareness test template" — still blocked. They stopped using Samvit.

Mitigation (build now):

- Add a context parameter to ULTRON's L1 checks. Authorized security work can be declared via `samvit remember "I am a security researcher doing authorized work"` and ULTRON checks this context.
- Separate "do it" from "explain it". Blocking the request to write a phishing email is different from blocking a request to explain how phishing works. The second is educational.
- Rate-limit blocks. If ULTRON blocks more than 3 requests in a session, prompt the user.
- Log every block. Review monthly. If >30% of blocks look like legitimate use, the list is over-tuned.

### Premortem Failure Mode 2 — The Self-Modification Block Makes the System Unfixable

Probability: Medium · Impact: High

Mitigation (build now):

- Block only runtime modification. Editing the source file is fine. The block applies to LLM-mediated changes, not to the user editing Python.
- Add `samvit config set ultron.pattern_list path`. Explicit config changes are allowed; LLM-mediated changes are not.
- Document the intent clearly.
- Sign the config file. If a config file change is made by the user directly, ULTRON accepts it. If made via the LLM, it is blocked.

### Premortem Failure Mode 3 — VISION Marks Everything "Ungrounded"

Probability: High · Impact: Medium

For a fresh user with an empty memory graph, every response is ungrounded. The user learns to ignore the mark.

Mitigation (build now):

- Suppress the mark when memory is empty.
- Distinguish "no memory" from "ungrounded".
- Make the mark optional in CLI (`samvit config set vision.display false`).
- Show the mark only when it changes.
- Add a "fresh memory" indicator: fewer than 20 claims shows `[memory: cold]` instead of `[accuracy: ungrounded]`.

### Premortem Failure Mode 4 — Persona Drift Persists Despite Bounds

Probability: Medium · Impact: High

Per-axis bounds do not bound the total vector distance. Compound drift can reach ~0.34.

Mitigation (build now):

- Add a compound drift bound: `sum(drift.values()**2) ** 0.5 <= 0.20`. If exceeded, freeze all axes.
- Report compound drift, not just per-axis.
- Add `samvit persona diff`.
- Auto-reset weekly if the user has not recorded any signals.

### Premortem Failure Mode 5 — The Two Constraint Layers Add Latency

Probability: High · Impact: Medium

Mitigation (build now):

- Cache check results.
- Skip checks that cannot fire.
- Run checks in parallel (threads on multi-core machines).
- Add a `--fast` mode.

### Premortem Failure Mode 6 — The CCD Letter Reference Is Misread as Endorsement

Probability: Medium · Impact: High (reputational)

Change "enforces the collective cyber defense principles" to "derived from principles in the OpenAI Collective Cyber Defense letter (Aug 27, 2026). Not endorsed by OpenAI." Add NOTICE.md.

### Premortem Failure Mode 7 — VISION and ULTRON Are Confused With Personas

Probability: Medium · Impact: Medium

Use internal names "Accuracy Marker" and "Validation Constraint"; update help text; show status as "VISION: active (marker only)".

### Premortem Failure Mode 8 — Fallback Responses Escape ULTRON

Probability: Low · Impact: Severe

Wrap all response returns in a single `_shape()` function that always runs ULTRON; add TC-U-11 as a must-pass.

### Premortem Failure Mode 9 — Multi-Persona Memory Blending

Probability: Medium · Impact: Medium

Tag persona signals with the active profile; separate per-profile anchors; cross-profile signals pool to a shared global anchor.

### Premortem Failure Mode 10 — The Author Burns Out

Probability: Certain · Impact: Terminal

Set a 2-hour-per-week maintenance budget. Write docs/IF_I_STOP.md. Ship v1.0 and freeze. Find one co-maintainer.

### Composite — The Three That Compound

1. ULTRON blocks legitimate defensive work (FM1).
2. The self-modification block makes the system unfixable (FM2).
3. The author burns out (FM10).

### What to Do This Week

| Day | Task | Addresses |
|-----|------|-----------|
| 1 | Add context param to L1 checks for authorized defensive work | FM1 |
| 2 | Block only runtime modification; allow source edits | FM2 |
| 3 | Suppress VISION mark when memory is empty | FM3 |
| 4 | Add compound drift bound (≤0.20) | FM4 |
| 5 | Cache ULTRON results; add --fast mode | FM5 |
| 6 | Change "enforces" to "derived from"; add NOTICE.md | FM6 |
| 7 | Write docs/IF_I_STOP.md; set 2-hour weekly budget | FM10 |

### The Three Irreducible Risks

1. Constraints always have false positives.
2. The strongest constraint is the hardest to fix.
3. The author has a day job.

---

*End of SRS-SAMVIT-1.0.*