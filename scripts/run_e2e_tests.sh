#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Run ./scripts/ubuntu_bootstrap.sh first." >&2
  exit 1
fi

echo "Running focused unit and regression tests..."
.venv/bin/python -m unittest discover -s testing/tests -p "test_*.py"

echo
echo "Running isolated QA harness..."
bash testing/qa/run_wsl.sh
