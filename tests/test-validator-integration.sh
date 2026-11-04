#!/usr/bin/env bash
# Explicit real-validator gate; no synthetic-provider fallback or silent skip.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${RHYTHM_VALIDATOR_SOURCE:-}" ]]; then
  echo 'UNAVAILABLE: set RHYTHM_VALIDATOR_SOURCE to a trusted stepmania-song-validator src directory; real-validator integration was NOT run.' >&2
  exit 1
fi
cd "$ROOT"
python3 tests/test-pack-validator-reporting.py
python3 tests/test-real-validator-transaction.py
