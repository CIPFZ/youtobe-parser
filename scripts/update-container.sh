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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
APP_IMAGE="${APP_IMAGE:-ghcr.io/cipfz/youtobe-parser:latest}"

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

echo "[INFO] Pulling app image: ${APP_IMAGE}"
APP_IMAGE="${APP_IMAGE}" docker compose \
  --env-file "${ENV_FILE}" \
  -f docker-compose.yml \
  -f docker-compose.image.yml \
  pull app

echo "[INFO] Recreating containers with latest image"
APP_IMAGE="${APP_IMAGE}" docker compose \
  --env-file "${ENV_FILE}" \
  -f docker-compose.yml \
  -f docker-compose.image.yml \
  up -d --remove-orphans

echo "[INFO] Cleaning old dangling images"
docker image prune -f >/dev/null 2>&1 || true

echo "[DONE] Update completed"
