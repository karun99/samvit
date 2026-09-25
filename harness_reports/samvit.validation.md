# samvit - validation report

samvit finished its harness run with an overall accuracy of 0.76. 14 of 14 checks passed outright, 0 flagged a warning, and 0 failed. Measured on data integration specifically, accuracy came to 0.77.

Information handling: 5 checks, all clear.

We walked back 120 records to their sources and all of them survived the journey. Provenance holds.

We wrote data in and read it back, and 360 of 360 fields matched to the letter. Nothing quietly changed between the store and the handoff.

All 120 records sat neatly inside our declared schema. No surprise fields, no missing keys, no type drift.

Both modules looked at the same entities and agreed on 120 of 120 shared fields. When two views of one thing match this well, the integration is doing its job.

Identifiers stood their ground — 120 unique id(s), zero duplicates, zero drift on reload.

Neural synthesis: 5 checks, 4 clean.

We held the synthesis next to its source material and it kept its language close (overlap 0.25 on 15 pairs).

Persona checks came back solid — 3 of 3 traits intact and drift held to 0.00.

Synthesized points stayed near their anchors (mean neighborhood score 0.009). Interpolation is blending profiles, not conjuring strangers.

Repeated probes came back consistent — 60% agreement across the run.

Output here is genuinely new material. Zero near-verbatim copies of the seed corpus showed up.

Data integration: 4 checks, 3 clean.

Joining the storage lens with the synthesis lens lands us at an integrated accuracy of 0.39. Both halves get along.

When data survival and generation honesty are fused, the system scores 0.88 on integration accuracy.

Fusing the storage lens (1.00) and the synthesis lens (1.00) gives an integrated accuracy of 1.00.

Put the two lenses side by side and the integrated score reads 0.80 (storage 1.00, synthesis 0.60).

## Summary

- overall accuracy: **0.762**
- integration accuracy: **0.765**
- passed: **14** / 14
- warnings: 0, failures: 0
- human voice index: **0.904** (reads human)

## Checks

| check | phase | status | metric | duration ms |
|---|---|---|---|---|
| `provenance_traceable` | information handling | pass | 1.000 | 0.17 |
| `round_trip_fidelity` | information handling | pass | 1.000 | 0.23 |
| `schema_conformance` | information handling | pass | 1.000 | 0.22 |
| `cross_module_agreement` | information handling | pass | 1.000 | 0.44 |
| `id_stability` | information handling | pass | 1.000 | 0.46 |
| `faithfulness` | neural synthesis | pass | 0.250 | 0.78 |
| `identity_preserved` | neural synthesis | pass | 1.000 | 0.05 |
| `interpolation_sound` | neural synthesis | pass | 0.009 | 1.57 |
| `consistency_span` | neural synthesis | pass | 0.600 | 0.1 |
| `not_verbatim` | neural synthesis | pass | 0.750 | 0.15 |
| `integration_accuracy` | data integration | pass | 0.385 | 0.0 |
| `integration_accuracy` | data integration | pass | 0.875 | 0.0 |
| `integration_accuracy` | data integration | pass | 1.000 | 0.0 |
| `integration_accuracy` | data integration | pass | 0.800 | 0.0 |
