# JOSS submission readiness — Samvit

Transparent ledger of which JOSS gates are already met and which need time.

## Already met

- **OSI-approved license**: `LICENSE` (MIT), plain text, also declared in
  `pyproject.toml`.
- **Open repository**: GitHub `karun99/samvit`, browsable and clonable,
  public issues.
- **Obvious research application**: a local-first personal AI with explicit
  accuracy-marker and error-validation constraints — a research-testable
  architecture, stated in `paper/paper.md`.
- **Installable packaging**: `pyproject.toml` (setuptools), `pip install .`,
  console script `samvit`; standard library only at runtime.
- **Automated tests**: `pytest` — 80 tests pass with no third-party install
  (verified 2026-09-25).
- **Documentation**: README with purpose/features/privacy/honest boundaries,
  `FIXES.md` engineering log, `docs/`.
- **`paper.md` / `paper.bib`**: all required sections present.
- **AI usage disclosure**: included per JOSS AI usage policy.

## Gates that need time / evidence

| Gate | Status | What turns it green |
|---|---|---|
| Six months of public history | Not met (repo made public recently) | Continue open development > 6 months with iterative commits |
| Tagged releases | Not met | Cut a `v1.0.0` release tag |
| Demonstrated research impact | Early | Record external adopters or a preprint; show `samvit validate` used as an evaluation reference |
| Community engagement | None yet | Open issues/prs over time |

**Note on citations**: placeholder entries for edge-AI survey and the
cyber-defense letter should be replaced with verified, findable references
(authors/URLs) before submission. Everything else in the paper can be
confirmed against this repository.

## Suggested path

1. Fix the `license = { text = "MIT" }` metadata to the modern
   `license = "MIT"` PEP 639-style key (optional, cosmetic).
2. Tag a `v1.0.0` release; add a `CHANGELOG.md`.
3. Replace placeholder bib entries with verified citations.
4. Keep tests green in CI (add GitHub Actions workflow if absent).
5. Allow > 6 months of public history, then submit.