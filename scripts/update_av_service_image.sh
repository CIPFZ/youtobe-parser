#!/usr/bin/env bash
set -euo pipefail

# 自动更新 av-service 镜像并重建容器
# 用法:
#   AV_SERVICE_IMAGE=ghcr.io/<owner>/youtobe-workflow/av-service:latest \
#   bash scripts/update_av_service_image.sh

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
SERVICE_NAME="${SERVICE_NAME:-av-service}"
AV_SERVICE_IMAGE="${AV_SERVICE_IMAGE:-ghcr.io/cipfz/youtobe-workflow/av-service:latest}"
LOCAL_UID="${LOCAL_UID:-$(id -u)}"
LOCAL_GID="${LOCAL_GID:-$(id -g)}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8888/healthz}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker 不存在" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose 插件不可用" >&2
  exit 1
fi

echo "[INFO] 拉取最新镜像: ${AV_SERVICE_IMAGE}"
docker pull "${AV_SERVICE_IMAGE}"

echo "[INFO] 使用 compose 重建 ${SERVICE_NAME}"
LOCAL_UID="${LOCAL_UID}" LOCAL_GID="${LOCAL_GID}" AV_SERVICE_IMAGE="${AV_SERVICE_IMAGE}" \
  docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans "${SERVICE_NAME}"

for i in $(seq 1 30); do
  if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "[OK] 健康检查通过"
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
  fi
  echo "[WAIT] 健康检查等待中 (${i}/30)"
  sleep 2
done

echo "[ERROR] 健康检查失败，请手工排查容器日志" >&2
docker compose -f "${COMPOSE_FILE}" logs --tail 150 "${SERVICE_NAME}" >&2 || true
exit 2
