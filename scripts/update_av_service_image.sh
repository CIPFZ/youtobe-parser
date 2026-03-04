#!/usr/bin/env bash
set -euo pipefail

# 自动更新 av-service 镜像并重建容器
# 优化点：支持 UID/GID 注入，解决宿主机文件权限问题

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
SERVICE_NAME="${SERVICE_NAME:-av-service}"
# 修正镜像默认路径
AV_SERVICE_IMAGE="${AV_SERVICE_IMAGE:-ghcr.io/cipfz/youtobe-parser:latest}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8888/healthz}"

# 获取当前用户的 UID 和 GID
# 这对于 docker-compose.yml 中的 user: "${UID}:${GID}" 至关重要
USER_ID=$(id -u)
GROUP_ID=$(id -g)

export USER_ID
export GROUP_ID
export LOCAL_UID=$USER_ID
export LOCAL_GID=$GROUP_ID

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker 不存在" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose 插件不可用" >&2
  exit 1
fi

echo "[INFO] 当前运行用户: $(id -un) (UID: $USER_ID, GID: $GROUP_ID)"
echo "[INFO] 拉取最新镜像: ${AV_SERVICE_IMAGE}"
docker pull "${AV_SERVICE_IMAGE}"

echo "[INFO] 使用 compose 重建 ${SERVICE_NAME}"
# 显式传递变量并启动
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans "${SERVICE_NAME}"

echo "[INFO] 开始健康检查..."
for i in $(seq 1 30); do
  # 增加 -s 选项减少输出，-L 处理重定向
  if curl -fsSL "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "[OK] 健康检查通过，服务已就绪"
    echo "[INFO] 清理过期的旧镜像..."
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
  fi
  echo "[WAIT] 健康检查等待中 (${i}/30)..."
  sleep 2
done

echo "[ERROR] 健康检查失败，容器可能启动异常" >&2
echo "[INFO] 最近 50 行日志摘要:" >&2
docker compose -f "${COMPOSE_FILE}" logs --tail 50 "${SERVICE_NAME}" >&2 || true
exit 2