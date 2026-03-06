# youtobe-parser (纯 Python 重构版)

从 0 开始重构，仅保留核心业务流程：

1. 链接解析 + 下载音频/视频（`yt-dlp`）
2. `fast-whisper` 音频识别，生成 `SRT`
3. 翻译字幕并转换成 `ASS`
4. `ASS + 音频 + 视频` 合并成最终 `MP4`

## 设计目标

- **高效**：全链路纯 Python，减少多服务通信开销。
- **快捷**：单命令跑完整流程。
- **可迁移**：默认可使用 `imageio-ffmpeg` 自动下载项目专用二进制，也支持自定义 `ffmpeg` 路径。
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
- `WHISPER_MODEL_SOURCE`（`huggingface` 或 `modelscope`，默认 `huggingface`）
- `WHISPER_MODELSCOPE_REPO`（当 source=modelscope 时必填）
- `WHISPER_MODEL_CACHE_DIR`（模型下载缓存目录，默认 `runtime/models`）
- `WHISPER_DOWNLOAD_PROXY`（Whisper 模型下载代理）
- `WHISPER_MODEL_FALLBACK_TO_MODELSCOPE`（默认 `true`，HF 失败时自动回退）
- `WHISPER_DEVICE`（默认 `auto`，会自动选择 GPU/CPU；可强制为 `cuda` 或 `cpu`）
- `WHISPER_COMPUTE_TYPE`（默认 `auto`）
- `WHISPER_LANGUAGE`（默认 `en`）
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`
- `TARGET_LANGUAGE`（默认 `zh-CN`）
- `WORK_DIR`（默认 `runtime`）
- `OUTPUT_NAME`（默认 `final_output`）
- `METADATA_DIRNAME`（默认 `metadata`，保存视频基础信息 JSON）
- `FFMPEG_PATH`（可选，自定义 ffmpeg 可执行文件绝对路径）
- `YTDLP_PROXY`（可选，视频解析与下载代理，例如 `socks5://127.0.0.1:7897`）
- `PLAYLIST_STRATEGY`（默认 `first`，合集链接仅下载当前视频/首个视频）
- `LOG_LEVEL`（日志级别，默认 `INFO`）
- `LOG_FILE`（日志文件路径，默认 `runtime/logs/pipeline.log`）

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
- `runtime/metadata/*.video_info.json`：视频解析基础信息

## 代码结构

- `app/pipeline.py`：总流程编排
- `app/downloader.py`：下载与媒体定位
- `app/transcriber.py`：fast-whisper 封装
- `app/translator.py`：字幕翻译
- `app/subtitles.py`：SRT/ASS 读写
- `app/ffmpeg_tools.py`：项目内 ffmpeg 调用

## 仓库清理说明

已删除历史遗留的 `server/`、`scripts/`、`docs/`、`docker-compose.yml`、旧 CI 工作流与旧 lock 文件，仅保留当前纯 Python 流程所需代码。


## 代理示例

如果你本地使用代理（如 clash/v2ray），可在 `.env` 中配置：

```env
YTDLP_PROXY=socks5://127.0.0.1:7897
```

该代理会用于 `yt-dlp` 的链接解析和媒体下载。


## 测试

分阶段测试脚本：

```bash
python tests/run_stage_checks.py
```

全量单元测试：

```bash
python -m unittest discover -s tests -v
```

说明：测试已覆盖下载、转写、翻译、字幕生成、ffmpeg 调用和整条 Pipeline 编排（通过 mock 进行端到端流程验证）。


## 日志

流程会输出到控制台并写入日志文件。

默认日志文件：`runtime/logs/pipeline.log`

你可以通过 `.env` 配置：

```env
LOG_LEVEL=INFO
LOG_FILE=runtime/logs/pipeline.log
```


## 合集链接策略

针对如下链接：

`https://www.youtube.com/watch?v=DFdh8BrzJ_Y&list=RDDFdh8BrzJ_Y&start_radio=1`

当前默认策略是 `PLAYLIST_STRATEGY=first`：
- 自动归一化为 `https://www.youtube.com/watch?v=DFdh8BrzJ_Y`
- 只处理当前视频（不整单播放列表）

这样可以保证主流程（单视频→单字幕→单输出）稳定可控。后续如果你要“整合集批处理”，我们可以再扩展 `all` 模式。


## Whisper 模型下载源

默认使用 HuggingFace（`WHISPER_MODEL_SOURCE=huggingface`）。

如果 HuggingFace 网络不稳定，可以切换到 ModelScope：

```env
WHISPER_MODEL_SOURCE=modelscope
WHISPER_MODELSCOPE_REPO=你的模型仓库ID
WHISPER_MODEL_CACHE_DIR=runtime/models
```

说明：
- `modelscope` 会先把模型下载到本地缓存目录，再由 `faster-whisper` 从本地路径加载。
- 如果你直接把 `WHISPER_MODEL` 设成本地目录路径，则优先使用本地模型路径。


### HF 网络失败建议

如果你遇到 `huggingface_hub ... Network is unreachable`：

1. 先配置下载代理（可与 `YTDLP_PROXY` 一致）：

```env
WHISPER_DOWNLOAD_PROXY=socks5://127.0.0.1:7897
```

2. 或直接改为 ModelScope：

```env
WHISPER_MODEL_SOURCE=modelscope
WHISPER_MODELSCOPE_REPO=你的模型仓库ID
```

3. 默认已开启 `WHISPER_MODEL_FALLBACK_TO_MODELSCOPE=true`，当 HF 拉取失败且配置了 ModelScope repo 时会自动回退。


## 下载命名与格式策略

- 文件名使用 `video_id`（例如 `abc123.mp4`、`abc123.m4a`），避免超长标题带来的路径问题。
- 视频优先下载 `bestvideo[ext=mp4]`，音频优先下载 `bestaudio[ext=m4a]`。
- 若目标扩展不可用，会自动回退到该视频 ID 的可用格式并记录 warning 日志。


## 预下载 fast-whisper 模型

在正式跑主流程前，可以先执行：

```bash
python tests/download_fast_whisper_model.py
```

该脚本会按 `.env` 里的 `WHISPER_MODEL_SOURCE` / `WHISPER_MODELSCOPE_REPO` / `WHISPER_DOWNLOAD_PROXY` 进行模型准备。

同时当 `WHISPER_DEVICE=auto` 时，程序会自动检测是否有 CUDA：
- 有 CUDA -> 使用 `cuda + float16`
- 无 CUDA -> 使用 `cpu + int8`
