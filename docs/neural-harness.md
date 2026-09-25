# Neural-harness integration

This repository is evaluated by the shared **neural-harness** engine
(`github.com/karun99/neural-harness`), which measures information-handling and
neural-synthesis accuracy on the data artifacts this project produces.

## Run

```bash
pip install neural-harness      # shared engine (CLI: `nh`)
./scripts/nh_validate.sh        # writes harness_reports/
```

or directly:

```bash
nh validate samvit --root "$(pwd)/.." --out harness_reports
```

## What it checks

- **Information handling** — provenance traceability, round-trip fidelity,
  schema conformance, cross-module agreement, identity stability.
- **Neural synthesis** — faithfulness to source, identity preservation,
  interpolation soundness, consistency span, paraphrasing (non-verbatim).
- **Integration accuracy** — a fused score with a consistency penalty across
  the project's memory/synthesis/recall stages.

Results are written as both human-readable markdown (prose, not AI-flavored
template text) and machine-readable JSON for downstream review.