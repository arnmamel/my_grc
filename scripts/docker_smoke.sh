#!/usr/bin/env sh
set -eu

IMAGE="${1:-my_grc:alpine}"
CONTAINER_NAME="${2:-my_grc_smoke}"
PORT="${3:-18501}"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

docker build -t "${IMAGE}" .
docker run -d --rm --name "${CONTAINER_NAME}" -p "${PORT}:8501" "${IMAGE}" >/dev/null
sleep 15
curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" >/dev/null
echo "Container smoke test passed for ${IMAGE} on port ${PORT}."
