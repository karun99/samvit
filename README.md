# Samvit (संवित्)

**Local-first personal AI** — one shared memory graph, five named profiles, one truth engine, one guardrail engine, one tool layer. Plus two constraint layers present in no prior system:

| Layer | Role |
|-------|------|
| **VISION** | Accuracy marker that labels every response `grounded \| partial \| ungrounded` |
| **ULTRON** | Error validation constraint that gates every response with **14 checks** (7 original + 7 derived from the OpenAI Collective Cyber Defense letter and Pacing the Frontier letter) |

Samvit is Sanskrit for *"consciousness"* / *"knowing together"* — *sam* (together) + *vid* (to know). One shared memory, many voices.

---

## Profiles

| Profile | Default address | Voice |
|---------|-----------------|-------|
| `JARVIS` | "Sir" | formal, dry |
| `FRIDAY` | "Boss" | casual, tactical |
| `KAREN` | user's name | protective |
| `VISION` | — | **marker only, cannot be addressed** |
| `ULTRON` | — | **constraint only, cannot be addressed** |

Speaking profiles (`JARVIS`, `FRIDAY`, `KAREN`) accept user queries. `VISION` and `ULTRON` do not.

## Honest Boundaries

Samvit makes no claim of errorless output, sentience, consciousness, always-on listening, multi-user support, clinical validity, or OpenAI endorsement. These are constraints, not bugs — see the Design Constraints (C1–C12) in the SRS.

## Privacy

Your memory graph, persona, and audit log stay **on-device** (a local SQLite file); nothing is exported or transmitted without an explicit command. Qualification: when the *local-friendly* provider is unavailable, only a small bounded set of `recalled` memory snippets (default 5, `llm.max_memory_snippets`) is sent alongside your message to the selected LLM provider to help generate a response. The full memory graph, API keys, config, and shell history are never sent. Full detail in SRS §7.3.

## Quick Start

```bash
python3 -m samvit init
python3 -m samvit chat
python3 -m samvit ask "what do you remember about me?"
python3 -m samvit persona use friday
python3 -m samvit status
```

Requires Python 3.9+, **standard library only — except optional voice input**, one SQLite file per brain, minimal ~256 MB.

Voice output uses OS-native TTS (a system binary such as `espeak-ng`, `say`, or `spd-say`). Voice *input* (push-to-talk) is **optional** and requires the external `whisper`/`whisper.cpp` binary — it is not part of the base install. Every core feature (memory, persona, guardrails, VISION, ULTRON, tools, watchers, TTY text mode) runs on the standard library alone.

## Docs

- **[docs/SRS.md](docs/SRS.md)** — Full ISO/IEC/IEEE 29148:2018-style Software Requirements Specification (SRS-SAMVIT-1.0), including the complete premortem analysis and the ten failure modes.
- **[docs/IF_I_STOP.md](docs/IF_I_STOP.md)** — Handoff instructions per Premortem Failure Mode 10.
- **[docs/NOTICE.md](docs/NOTICE.md)** — External reference relationships (no endorsement implied).

## License

MIT (code) / CC BY 4.0 (documentation).