#!/usr/bin/env sh
set -eu

IMAGE="${1:-my_grc:alpine}"

if command -v trivy >/dev/null 2>&1; then
  trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "${IMAGE}"
  exit 0
fi

if command -v grype >/dev/null 2>&1; then
  grype "${IMAGE}" --fail-on high
  exit 0
fi

if docker scout version >/dev/null 2>&1; then
  docker scout quickview "${IMAGE}"
  exit 0
fi

echo "Install Trivy, Grype, or Docker Scout to scan ${IMAGE}."
exit 1
