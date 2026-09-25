#!/usr/bin/env bash
# Neural-harness entry point for the Samvit checkout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/harness_reports}"

echo "neural-harness: validating 'samvit' from $ROOT"
nh validate samvit --root "$ROOT" --out "$OUT"
echo "Reports written to $OUT"