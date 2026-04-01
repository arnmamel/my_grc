#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

if [ ! -d .venv ]; then
  echo "Virtual environment .venv is missing. Run ./scripts/ubuntu_bootstrap.sh first."
  exit 1
fi

source .venv/bin/activate

python -m aws_local_audit.cli init-db
python -m unittest discover -s testing/tests -p "test_*.py"
python -m aws_local_audit.cli maturity enterprise-score
