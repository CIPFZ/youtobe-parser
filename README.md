# Youtobe Parser

一个基于 **FastAPI + yt-dlp + Redis** 的 YouTube 解析与字幕转换服务，支持：

1. YouTube 视频信息解析（多格式）
2. 可选 PO Token Provider 接入（用于增强可用性）
3. SRT/VTT 字幕翻译并转换为 ASS

---

## 功能概览

- **异步任务模型**：创建任务后返回 `task_id`，通过轮询查询进度与结果
- **Redis 任务存储**：默认使用 Redis；若 Redis 不可用可回退为内存存储
- **OpenAI 兼容翻译接口**：支持 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`
- **ASS 文件下载**：翻译完成后可通过接口直接下载生成的字幕文件
- **容器化部署**：支持 Docker Compose 一键启动
- **镜像更新脚本**：支持拉取 GHCR 镜像并自动更新容器

---

## 项目结构

```text
.
├── app/
│   ├── api/routes.py              # API 路由
│   ├── core/worker.py             # YouTube 解析任务
│   ├── core/translator.py         # SRT/VTT -> 翻译 -> ASS
│   ├── core/task_store.py         # Redis/InMemory 任务存储
│   ├── config.py                  # 环境变量配置
│   └── main.py                    # FastAPI 应用入口
├── frontend/                      # 前端源码（Vue + Vite）
├── Dockerfile                     # 多阶段构建镜像
├── docker-compose.yml             # 本地构建运行（app + redis）
├── docker-compose.image.yml       # 远端镜像覆盖配置
├── scripts/update-container.sh    # 一键拉取镜像并更新容器
└── docs/DEPLOY.md                 # 部署说明
```

---

## 快速开始（Docker Compose）

### 1) 准备环境变量

```bash
cp .env.example .env
```

根据实际情况填写 `.env`：

- `OPENAI_API_KEY`：字幕翻译时使用
- `OPENAI_BASE_URL`：OpenAI 兼容网关地址
- `OPENAI_MODEL`：模型名
- `REDIS_URL`：默认 `redis://redis:6379/0`
- `PO_TOKEN_SERVER`：默认内置 `pot-provider`，也可改成外部 provider 地址

### 2) 启动服务

```bash
docker compose --profile pot up -d --build
```



如果你不需要内置 POT 服务，也可以只启动默认服务并把 `PO_TOKEN_SERVER` 指向外部地址：

```bash
docker compose up -d --build
```

### 3) 健康检查

```bash
curl http://localhost:8000/health
```

---

## API 说明

统一前缀：`/v1`

### 1. 提交视频解析任务

`POST /v1/analyze`

```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

返回示例：

```json
{
  "task_id": "abc123def456",
  "task_type": "analyze",
  "status": "pending"
}
```

### 2. 提交字幕翻译任务

`POST /v1/translate`

```json
{
  "path": "test_en.srt"
}
```

> `path` 支持本地路径或 http/https 链接。

返回示例：

```json
{
  "task_id": "abc123def456",
  "task_type": "translate",
  "status": "pending"
}
```

### 3. 查询任务状态

`GET /v1/tasks/{task_id}`

返回示例：

```json
{
  "task_id": "abc123def456",
  "task_type": "translate",
  "status": "completed",
  "progress": 100,
  "result": {
    "output_path": "/app/downloads/test_en_xxxxxx.ass",
    "output_name": "test_en_xxxxxx.ass",
    "source_path": "test_en.srt",
    "format": "ass"
  },
  "error": null
}
```

### 4. 下载 ASS 字幕

`GET /v1/translate/download/{task_id}`

任务完成后可直接下载生成文件。

---

## 使用远端镜像自动更新

如果你通过 GHCR 发布镜像，可在服务器执行：

```bash
COMPOSE_PROFILES=pot bash scripts/update-container.sh
```

可选环境变量：

- `APP_IMAGE`：默认 `ghcr.io/cipfz/youtobe-parser:latest`
- `GHCR_USERNAME` / `GHCR_TOKEN`：私有镜像拉取时需要

示例：

```bash
GHCR_USERNAME=yourname \
GHCR_TOKEN=ghp_xxx \
APP_IMAGE=ghcr.io/cipfz/youtobe-parser:latest \
COMPOSE_PROFILES=pot \
bash scripts/update-container.sh
```

---

## 常见问题

### 1) 翻译没有变中文

如果 `OPENAI_API_KEY` 为空，系统会跳过 LLM 调用并保留原文。

### 2) Redis 连接失败

服务会回退到内存任务存储（重启后任务会丢失），建议生产环境确保 Redis 可用。

### 3) 无法访问 YouTube

请配置 `GLOBAL_PROXY`，并按需接入 `PO_TOKEN_SERVER`。

---

## License

仅供学习与个人项目使用，请遵守 YouTube 及相关服务条款。


> Troubleshooting: If pot-provider logs `protocol mismatch`, set `POT_PROXY` to a valid **HTTP/HTTPS** proxy or leave it empty.


> If pot-provider is slow to mint token, increase `PO_TOKEN_TIMEOUT_SECONDS` (e.g. 45~90).


For local debugging, pot-provider is exposed on host port `4416`, so you can test it with:

```bash
curl http://127.0.0.1:4416/health
```
