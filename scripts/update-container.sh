#!/usr/bin/env bash
set -euo pipefail

# One-click updater for production host.
# Usage:
#   bash scripts/update-container.sh
# Optional env vars:
#   APP_IMAGE=ghcr.io/cipfz/youtobe-parser:latest
#   ENV_FILE=.env
#   GHCR_USERNAME=<github-username>
#   GHCR_TOKEN=<github-token-with-read:packages>
#   COMPOSE_PROFILES=pot          # default enables bundled pot-provider

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
APP_IMAGE="${APP_IMAGE:-ghcr.io/cipfz/youtobe-parser:latest}"
COMPOSE_PROFILES="${COMPOSE_PROFILES:-pot}"

COMPOSE_CMD=(docker compose
  --env-file "${ENV_FILE}"
  -f docker-compose.yml
  -f docker-compose.image.yml
)

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker is not installed" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose plugin is required" >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "[ERROR] env file not found: ${ENV_FILE}" >&2
  echo "        create it first (e.g. cp .env.example .env)" >&2
  exit 1
fi

cd "${REPO_DIR}"

if [ -n "${GHCR_USERNAME:-}" ] && [ -n "${GHCR_TOKEN:-}" ]; then
  echo "[INFO] Logging into GHCR as ${GHCR_USERNAME}"
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin
else
  echo "[INFO] GHCR credentials not provided, trying anonymous pull"
fi

echo "[INFO] Using compose profile(s): ${COMPOSE_PROFILES}"

echo "[INFO] Pulling latest images"
APP_IMAGE="${APP_IMAGE}" COMPOSE_PROFILES="${COMPOSE_PROFILES}" "${COMPOSE_CMD[@]}" pull

echo "[INFO] Recreating containers with latest image(s)"
APP_IMAGE="${APP_IMAGE}" COMPOSE_PROFILES="${COMPOSE_PROFILES}" "${COMPOSE_CMD[@]}" up -d --remove-orphans

echo "[INFO] Cleaning old dangling images"
docker image prune -f >/dev/null 2>&1 || true

wait_running() {
  local service="$1"
  local cid
  cid="$(APP_IMAGE="${APP_IMAGE}" COMPOSE_PROFILES="${COMPOSE_PROFILES}" "${COMPOSE_CMD[@]}" ps -q "${service}")"

  if [ -z "${cid}" ]; then
    echo "[WARN] service '${service}' not created (profile may be disabled)"
    return 0
  fi

  for _ in $(seq 1 30); do
    local status
    status="$(docker inspect -f '{{.State.Status}}' "${cid}" 2>/dev/null || true)"
    if [ "${status}" = "running" ]; then
      echo "[INFO] ${service} is running"
      return 0
    fi
    sleep 2
  done

  local status
  status="$(docker inspect -f '{{.State.Status}}' "${cid}" 2>/dev/null || true)"
  echo "[ERROR] ${service} failed to stay running (status=${status})" >&2
  echo "[INFO] Recent ${service} logs:" >&2
  docker logs --tail 120 "${cid}" >&2 || true
  return 1
}

wait_running app
wait_running redis
if [[ "${COMPOSE_PROFILES}" == *"pot"* ]]; then
  wait_running pot-provider
fi

echo "[DONE] Update completed"
