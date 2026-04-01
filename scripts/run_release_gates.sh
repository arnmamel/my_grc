#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Run ./scripts/ubuntu_bootstrap.sh first." >&2
  exit 1
fi

echo "Running syntax validation..."
.venv/bin/python -m compileall src workspace testing/tests

echo
echo "Running full regression and QA suite..."
bash scripts/run_e2e_tests.sh

if .venv/bin/python -m pip_audit --version >/dev/null 2>&1; then
  echo
  echo "Running dependency vulnerability audit..."
  .venv/bin/python -m pip_audit --progress-spinner off
else
  echo
  echo "Skipping pip-audit because it is not installed in this environment."
fi
