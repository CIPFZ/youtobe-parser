# youtobe-parser (纯 Python 重构版)

从 0 开始重构，仅保留核心业务流程：

1. 链接解析 + 下载音频/视频（`yt-dlp`）
2. `fast-whisper` 音频识别，生成 `SRT`
3. 翻译字幕并转换成 `ASS`
4. `ASS + 音频 + 视频` 合并成最终 `MP4`

## 设计目标

- **高效**：全链路纯 Python，减少多服务通信开销。
- **快捷**：单命令跑完整流程。
- **可迁移**：`ffmpeg` 使用 `imageio-ffmpeg` 自动下载项目专用二进制。
- **GPU 兼容**：`faster-whisper` 原生支持 CUDA 场景。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## 环境变量（可选）

复制 `.env.example` 到 `.env` 后按需修改：

- `WHISPER_MODEL`（默认 `large-v3`）
- `WHISPER_DEVICE`（默认 `auto`，GPU 推荐 `cuda`）
- `WHISPER_COMPUTE_TYPE`（默认 `auto`）
- `WHISPER_LANGUAGE`（默认 `en`）
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`
- `TARGET_LANGUAGE`（默认 `zh-CN`）
- `WORK_DIR`（默认 `runtime`）
- `OUTPUT_NAME`（默认 `final_output`）

> 不配置 `OPENAI_API_KEY` 时，翻译阶段会跳过（直接使用原文）。

## 运行

```bash
python main.py "https://www.youtube.com/watch?v=..."
# 或
yp-run "https://www.youtube.com/watch?v=..."
```

输出目录：

- `runtime/downloads/`：下载的音视频
- `runtime/subtitles/*.srt`：识别字幕
- `runtime/subtitles/*.ass`：翻译后 ASS
- `runtime/output/*.mp4`：最终成片

## 代码结构

- `app/pipeline.py`：总流程编排
- `app/downloader.py`：下载与媒体定位
- `app/transcriber.py`：fast-whisper 封装
- `app/translator.py`：字幕翻译
- `app/subtitles.py`：SRT/ASS 读写
- `app/ffmpeg_tools.py`：项目内 ffmpeg 调用

## 仓库清理说明

已删除历史遗留的 `server/`、`scripts/`、`docs/`、`docker-compose.yml`、旧 CI 工作流与旧 lock 文件，仅保留当前纯 Python 流程所需代码。
