---
title: 'Samvit: a local-first personal AI with accuracy-marker and error-validation constraints'
tags:
  - Python
  - personal AI
  - guardrails
  - memory
  - local-first
  - sqlite
authors:
  - name: Sai Karun Nandipati
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 25 September 2026
bibliography: paper.bib
---

# Summary

Samvit (संवित्, Sanskrit for *consciousness* — "knowing together") is a
local-first personal AI that keeps one shared memory graph, a small set of
named speaking profiles, a single truth engine, one guardrail engine, and one
tool layer on-device and in-process. Its distinctive contribution is two
constraint layers that no prior personal-AI design includes: **VISION**, an
accuracy marker that labels every response `grounded | partial | ungrounded`,
and **ULTRON**, an error-validation constraint that gates every response with
14 checks (7 original plus 7 derived from the OpenAI Collective Cyber Defense
letter and the "Pacing the Frontier" letter). The entire runtime depends only
on the Python standard library (optional Whisper binary for voice input), and
all state is local SQLite.

# Statement of need

Consumer and research personal-AI systems are convenient, but they are
opaque about one thing users actually care about: *whether a given answer can
be trusted*. Typical chatbot stacks will happily generate a confidently wrong
or fabricated reply, and a user has no in-band signal to tell grounded
recollection from fluent hallucination. Personalization also tends to pipe
the user's private data through remote services, which bottlenecks private,
offline, single-user deployment. Samvit addresses both problems directly: it
runs entirely locally with no network requirement, and it commits to
groundedness as a *first-class output*, not a post hoc reviewer. The VISION
marker gives every answer a cheap, explainable trust label; ULTRON enforces a
fixed, testable set of 14 checks on every response; and the memory graph
keeps what the system knows transparent and inspectable. The design and its
constraints (C1–C12) are written up as a specification in the repository, and
the whole behavior is exercised by a test suite, so the "no errorless AI"
disclaimer is substantiated by tests rather than asserted.

# State of the field

The personal-AI space currently divides into (i) remote RAG/prompt-based
assistants that are convenient but uncontrollable, (ii) on-device assistants
that improve privacy but usually keep claims-of-accuracy implicit, and (iii)
guardrail frameworks (e.g. NeMo Guardrails, LLM Guard from the LLMGuard
project, OpenAI's cyber-defense guidance [@openai2024collective]) that gate
output in a plug-in way but rarely integrate accuracy labeling with a
persistent persona memory. Samvit has two differences worth noting. First,
it makes *accuracy a protocol*: the `grounded/partial/ungrounded` marker and
the 14-check ULTRON gate are part of the system's API contract, so a calling
agent can act on confidence instead of guessing. Second, it makes *privacy a
property of the runtime*, not a setting: no cloud dependency means the
"local-first" claim is structural, matching the motivations of on-device and
edge-personal-AI work (e.g. PrivateGPT-style deployments, Apple's on-device
discussion, and the broader edge-AI literature [@edgeshnei2019trends]).

# Software design

Samvit is a single Python package with small modules: `brain.py` ties together
`memory` (SQLite graph), `persona`/`personas` (named voices: JARVIS, FRIDAY,
KAREN, plus the non-speaking VISION and ULTRON), `guardrails`, `vision`,
`ultron`, `tools`, `provider` (model backend), `voice` (optional Whisper),
`proactive`, and a `cli.py`/`gui.py` front. Key design decisions:

- **Shared memory graph, many voices.** Profiles do not recreate memory; they
  share one graph and differ in voice. VISION and ULTRON deliberately cannot
  be addressed — they are constraints, not companions.
- **Groundedness as an output.** Every response is tagged by VISION, and the
  tag is part of the returned structure, so downstream code can branch on
  confidence.
- **Fixed, derived check list.** ULTRON hard-codes its 14 checks, keeping the
  constraint surface explicit and testable, in line with the iterative
  principle of the collective cyber-defense letters [@openai2024collective].
- **Standard library only.** Runtime avoids heavy ML dependencies; existing
  tests run with zero installed third-party packages, which maximizes
  reproducibility for reviewers and CI.
- **Honest boundaries, encoded.** The system's disclaimer about errorless
  output is not marketing; it is enforced by VISION/ULTRON behavior and locked
  by tests.

# Research impact statement

Reproducibility is the strongest impact claim of this repository: the same
mechanism, constraints, and check list can be inspected, executed
(`python -m samvit`, with `pytest` locking constraint behavior), and audited end-to-end by
reviewers, in line with the reproducibility expectations of scientific
software venues [@hageboeck2025joss]. The VISION/ULTRON design is a reference implementation of
accuracy-labeling plus error-validation for a personal agent, and its
strong assumptions (single user, local-only, no sentience claims) are stated
as the requirements they are. Adoption evidence will be tracked in
`paper/JOSS_SUBMISSION_READINESS.md`.

# AI usage disclosure

This software, its specification documents, and its tests were drafted with
generative-AI assistance (code scaffolding, copy-editing, and test
generation). All assisted artifacts were reviewed, edited, and validated by
the human author, who made the design decisions. No AI rendered evaluative
decisions for this submission.

# Acknowledgements

No direct funding was received.

# References