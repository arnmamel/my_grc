#!/bin/sh
set -eu

APP_DIR="/app"
DATA_DIR="${MY_GRC_DATA_DIR:-${APP_DIR}/data}"
SECRET_DIR="${ALA_SECRET_FILES_DIR:-${DATA_DIR}/secrets}"
DB_URL="${ALA_DATABASE_URL:-sqlite:///${DATA_DIR}/audit_manager.db}"

mkdir -p "${DATA_DIR}" "${SECRET_DIR}"

export ALA_DATABASE_URL="${DB_URL}"
export ALA_SECRET_FILES_DIR="${SECRET_DIR}"
export PYTHONPATH="${APP_DIR}/src"

python -m aws_local_audit.cli init-db >/tmp/my_grc-init.log 2>&1 || cat /tmp/my_grc-init.log

exec streamlit run workspace/app.py --server.address=0.0.0.0 --server.port=8501
