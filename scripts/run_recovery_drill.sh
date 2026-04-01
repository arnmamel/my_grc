#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Run ./scripts/ubuntu_bootstrap.sh first." >&2
  exit 1
fi

echo "Initializing database before recovery drill..."
.venv/bin/python src/aws_local_audit/cli.py init-db

echo
echo "Running database recovery drill..."
.venv/bin/python src/aws_local_audit/cli.py platform recovery-drill
