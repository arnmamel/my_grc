#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  build-essential \
  libffi-dev \
  libssl-dev \
  sqlite3 \
  libsqlite3-dev \
  curl \
  unzip \
  ca-certificates

if ! command -v aws >/dev/null 2>&1; then
  cd /tmp
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip -q -o awscliv2.zip
  sudo ./aws/install --update
fi

cd "${PROJECT_DIR}"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

mkdir -p data data/secrets .streamlit

if [ ! -f .env ]; then
  cp .env.example .env
fi

printf '\nBootstrap completed.\n'
printf 'Next steps:\n'
printf '  1. source .venv/bin/activate\n'
printf '  2. aws-local-audit init-db\n'
printf '  3. aws-local-audit security bootstrap\n'
printf '  4. aws-local-audit framework seed\n'
printf '  5. streamlit run workspace/app.py\n'
