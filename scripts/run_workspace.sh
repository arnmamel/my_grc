#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Run ./scripts/ubuntu_bootstrap.sh first." >&2
  exit 1
fi

if [[ ! -f "audit_manager.db" ]]; then
  .venv/bin/python -m aws_local_audit.cli init-db
  .venv/bin/python -m aws_local_audit.cli security bootstrap
  .venv/bin/python -m aws_local_audit.cli framework seed
fi

exec .venv/bin/python -m streamlit run workspace/app.py
