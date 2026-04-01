#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="$ROOT/testing/qa/.venv"

cd "$ROOT"

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "python3 -m venv is not available."
  echo "Run this first in Ubuntu-24.04:"
  echo "  sudo apt-get update && sudo apt-get install -y python3.13-venv"
  exit 2
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -e .
"$VENV_DIR/bin/python" -m testing.qa.run "$@"
