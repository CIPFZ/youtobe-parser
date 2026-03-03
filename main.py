#!/usr/bin/env python3
"""Parse a YouTube URL, run C++ media pipeline, translate subtitles, and compose final video."""

from __future__ import annotations

import argparse
import json
import logging
import os
import os.path
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yt_dlp
from dotenv import dotenv_values
from openai import OpenAI


def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("ydl_parser_downloader")
    logger.setLevel(logging.DEBUG)

    Path(os.path.dirname(log_file)).mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(file_formatter)

    logger.addHandler(fh)
    return logger


def _best_formats(info: dict[str, Any]) -> dict[str, Any]:
    formats = info.get("formats") or []
    muxed = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("acodec") not in (None, "none")]
    video_only = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("acodec") in (None, "none")]
    audio_only = [f for f in formats if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]

    best_muxed = max(muxed, key=lambda x: x.get("height") or 0, default=None)
    best_video = max(video_only, key=lambda x: x.get("height") or 0, default=None)
    best_audio = max(audio_only, key=lambda x: x.get("abr") or x.get("tbr") or 0, default=None)

    return {
        "title": info.get("title"),
        "webpage_url": info.get("webpage_url"),
        "best_muxed": {
            "format_id": best_muxed.get("format_id"),
            "ext": best_muxed.get("ext"),
            "resolution": best_muxed.get("resolution"),
            "url": best_muxed.get("url"),
        }
        if best_muxed
        else None,
        "best_video": {
            "format_id": best_video.get("format_id"),
            "ext": best_video.get("ext"),
            "resolution": best_video.get("resolution"),
            "url": best_video.get("url"),
        }
        if best_video
        else None,
        "best_audio": {
            "format_id": best_audio.get("format_id"),
            "ext": best_audio.get("ext"),
            "abr": best_audio.get("abr"),
            "url": best_audio.get("url"),
        }
        if best_audio
        else None,
    }


def print_step(step: int, message: str) -> None:
    print(f"\n{'=' * 50}")
    print(f"[Step {step}] {message}")
    print(f"{'=' * 50}\n")


BASE_URL = "http://127.0.0.1:8888/api/v1"
SRT_TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})")


def _load_runtime_env(env_file: str) -> dict[str, str]:
    file_vars = {k: v for k, v in dotenv_values(env_file).items() if isinstance(v, str)}
    merged = dict(file_vars)
    for k, v in os.environ.items():
        merged[k] = v
    return merged


def _env_get(env: dict[str, str], key: str, default: str = "") -> str:
    return env.get(key, default)


def convert_m4a_to_wav(input_path: str, output_path: str) -> dict[str, Any] | None:
    url = f"{BASE_URL}/audio/m4a-to-wav"
    payload = {"input_path": input_path, "output_path": output_path}
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None


def compose_video(video_path: str, audio_path: str, subtitle_path: str, output_path: str) -> dict[str, Any] | None:
    url = f"{BASE_URL}/compose"
    payload = {
        "video_path": video_path,
        "audio_path": audio_path,
        "subtitle_path": subtitle_path,
        "output_path": output_path,
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"合成请求失败: {e}")
        return None


def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> dict[str, Any] | None:
    url = f"{BASE_URL}/merge"
    payload = {
        "video_path": video_path,
        "audio_path": audio_path,
        "output_path": output_path,
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"合并请求失败: {e}")
        return None


def submit_asr_task(
    audio_path: str,
    subtitle_path: str,
    model_dir: str,
    model_name: str,
    language: str = "en",
) -> dict[str, Any] | None:
    url = f"{BASE_URL}/asr"
    payload = {
        "audio_path": audio_path,
        "subtitle_path": subtitle_path,
        "model_dir": model_dir,
        "model_name": model_name,
        "language": language,
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ASR 请求失败: {e}")
        return None


def get_task_status(task_id: str) -> dict[str, Any] | None:
    url = f"{BASE_URL}/task"
    params = {"task_id": task_id}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"查询失败: {e}")
        return None


def _build_asr_model_hint(model_dir: str, model_name: str) -> str:
    model_path = f"{model_dir.rstrip('/')}/{model_name}"
    return (
        "ASR 模型加载失败，请确认 whisper 模型文件对 C++ 服务可见: "
        f"{model_path}。可通过 --whisper-model-dir/--whisper-model-name "
        "或环境变量 WHISPER_MODEL_DIR/WHISPER_MODEL_NAME 覆盖。"
    )


def wait_for_task(task_id: str, logger: logging.Logger, poll_interval: int = 2, max_retries: int = 300) -> dict[str, Any]:
    logger.info("开始轮询任务: %s", task_id)
    print(f"[{task_id}] 等待任务完成...")

    for _ in range(max_retries):
        status_info = get_task_status(task_id)
        if not status_info or "error" in status_info:
            error_msg = status_info.get("error", "Unknown API error") if status_info else "Unknown API error"
            logger.error("任务 %s 出错: %s", task_id, error_msg)
            raise RuntimeError(f"API Error: {error_msg}")

        status = status_info.get("status")
        progress = status_info.get("progress", 0)
        print(f"\r进度: {progress}% - 状态: {status}", end="", flush=True)

        if status == "SUCCESS":
            print("\n任务完成！")
            return status_info
        if status == "FAILED":
            logger.error("任务 %s 失败: %s", task_id, status_info.get("message"))
            raise RuntimeError(f"Task Failed: {status_info.get('message')}")

        time.sleep(poll_interval)

    raise TimeoutError(f"任务 {task_id} 等待超时")


def _to_ass_time(time_str: str) -> str:
    h, m, sec_ms = time_str.replace(",", ".").split(":")
    sec, ms = sec_ms.split(".")
    return f"{int(h)}:{m}:{sec}.{ms[:2]}"


def _translate_batch(client: OpenAI, model: str, texts: list[str]) -> list[str]:
    if not texts:
        return []

    numbered = "\n".join([f"{i}|{t}" for i, t in enumerate(texts)])
    rsp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "你是专业字幕翻译。请严格保留输入行数，输出格式必须是 index|译文，每行一个，不要额外解释。",
            },
            {
                "role": "user",
                "content": f"将以下英文字幕翻译成中文，保持原本语气和简洁性：\n{numbered}",
            },
        ],
    )
    content = rsp.choices[0].message.content or ""

    mapped: dict[int, str] = {}
    for line in content.splitlines():
        if "|" not in line:
            continue
        idx_str, txt = line.split("|", 1)
        if idx_str.strip().isdigit():
            mapped[int(idx_str.strip())] = txt.strip()

    return [mapped.get(i, t) for i, t in enumerate(texts)]


def translate_srt_to_ass(
    srt_path: str,
    ass_path: str,
    logger: logging.Logger,
    model: str,
    api_key: str,
    base_url: str | None,
) -> None:
    with open(srt_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f.readlines()]

    subtitle_rows: list[tuple[str, str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.isdigit() and i + 1 < len(lines):
            i += 1
            line = lines[i].strip()

        m = SRT_TIME_RE.match(line)
        if not m:
            i += 1
            continue

        start, end = m.group(1), m.group(2)
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1

        if text_lines:
            subtitle_rows.append((start, end, "\\N".join(text_lines)))

    if not subtitle_rows:
        raise RuntimeError(f"未解析到字幕内容: {srt_path}")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未设置（可在 .env 中配置），无法执行 Step6 翻译")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url or None,
    )

    translated: list[str] = []
    batch_size = 30
    for idx in range(0, len(subtitle_rows), batch_size):
        batch = subtitle_rows[idx : idx + batch_size]
        batch_text = [b[2] for b in batch]
        translated.extend(_translate_batch(client, model=model, texts=batch_text))
        logger.info("Step5 翻译进度: %s/%s", min(idx + batch_size, len(subtitle_rows)), len(subtitle_rows))

    header = """[Script Info]
Title: Bilingual Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,62,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        for (start, end, original), zh in zip(subtitle_rows, translated):
            line = f"{zh}\\N{{\\fs40\\c&HCCCCCC&}}{original}"
            f.write(f"Dialogue: 0,{_to_ass_time(start)},{_to_ass_time(end)},Default,,0,0,0,,{line}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and Download YouTube video/audio with logging and step output.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--env-file", default=".env", help="Environment file path")
    parser.add_argument("--output-dir", default="data/input", help="Output directory")
    parser.add_argument("--proxy", default=None, help="Proxy URL, e.g. socks5://127.0.0.1:7890")
    parser.add_argument("--cookie-file", default=None, help="Netscape cookies file path")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout seconds")
    parser.add_argument("--log-file", default="logs/process.log", help="Log file path")
    parser.add_argument("--openai-model", default=None, help="LLM model for subtitle translation (override .env)")
    parser.add_argument("--whisper-model-dir", default=None, help="Whisper C++ model directory (override .env)")
    parser.add_argument("--whisper-model-name", default=None, help="Whisper C++ model file name (override .env)")
    parser.add_argument("--asr-language", default=None, help="ASR language code (override .env)")
    args = parser.parse_args()

    env = _load_runtime_env(args.env_file)

    global BASE_URL
    BASE_URL = _env_get(env, "AV_API_BASE_URL", BASE_URL)

    openai_api_key = _env_get(env, "OPENAI_API_KEY", "")
    openai_base_url = _env_get(env, "OPENAI_BASE_URL", "")
    openai_model = args.openai_model or _env_get(env, "OPENAI_MODEL", "gpt-4o-mini")
    whisper_model_dir = args.whisper_model_dir or _env_get(env, "WHISPER_MODEL_DIR", "/models/whisper")
    whisper_model_name = args.whisper_model_name or _env_get(env, "WHISPER_MODEL_NAME", "ggml-base.en.bin")
    asr_language = args.asr_language or _env_get(env, "ASR_LANGUAGE", "en")

    Path("data/input").mkdir(parents=True, exist_ok=True)
    Path("data/output").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    logger = setup_logger(args.log_file)
    logger.info("=== Starting process for %s ===", args.url)

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_opts: dict[str, Any] = {
        "proxy": args.proxy if args.proxy is not None else (_env_get(env, "GLOBAL_PROXY") or None),
        "cookiefile": args.cookie_file if args.cookie_file is not None else (_env_get(env, "YOUTUBE_COOKIE_FILE") or None),
        "socket_timeout": args.timeout,
    }
    base_opts = {k: v for k, v in base_opts.items() if v is not None}

    print_step(1, "Parsing URL and extracting info...")
    logger.info("Step 1: Extracting info...")
    parse_opts = base_opts.copy()
    parse_opts.update({"quiet": True, "skip_download": True, "no_warnings": True})

    try:
        with yt_dlp.YoutubeDL(parse_opts) as ydl:
            info = ydl.extract_info(args.url, download=False)
            logger.info("Successfully extracted info.")
    except Exception as e:
        logger.error("Failed to extract info: %s", e, exc_info=True)
        print(f"Error extracting info: {e}")
        sys.exit(1)

    vid = info.get("id") or "unknown_vid"
    vid_dir = output_path / vid
    vid_dir.mkdir(parents=True, exist_ok=True)

    metadata_file = vid_dir / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    logger.info("Saved all parsed info to %s", metadata_file)

    parsed_formats = _best_formats(info)
    logger.debug("Format details: %s", json.dumps(parsed_formats, ensure_ascii=False, indent=2))

    print_step(2, "Downloading best formats...")
    logger.info("Step 2: Starting download for video and audio separately...")

    download_opts = base_opts.copy()
    download_opts.update(
        {
            "format": "bestvideo[ext=mp4],bestaudio[ext=m4a]",
            "outtmpl": str(output_path / "%(id)s" / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "retries": 3,
            "quiet": False,
        }
    )

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([args.url])
            logger.info("Download completed successfully.")
    except Exception as e:
        logger.error("Download failed: %s", e, exc_info=True)
        print(f"Error downloading: {e}")
        sys.exit(1)

    print_step(3, "Converting m4a to wav...")
    input_m4a_abs = f"/data/input/{vid}/{vid}.m4a"
    output_wav_abs = f"/data/input/{vid}/{vid}.wav"
    submit_res = convert_m4a_to_wav(input_m4a_abs, output_wav_abs)
    task_id = submit_res.get("task_id") if submit_res else None
    if not task_id:
        logger.error("提交 m4a->wav 任务失败")
        sys.exit(1)

    final_info = wait_for_task(task_id, logger)
    logger.info("转换任务 %s 成功: %s", task_id, final_info)

    print_step(5, "Generating SRT via C++ ASR (whisper.cpp)...")
    srt_file = os.path.join(output_path, vid, f"{vid}.srt")
    asr_audio_abs = f"/data/input/{vid}/{vid}.wav"
    logger.info(
        "Step5 ASR 参数: model_dir=%s, model_name=%s, language=%s",
        whisper_model_dir,
        whisper_model_name,
        asr_language,
    )
    asr_res = submit_asr_task(
        audio_path=asr_audio_abs,
        subtitle_path=f"/data/input/{vid}/{vid}.srt",
        model_dir=whisper_model_dir,
        model_name=whisper_model_name,
        language=asr_language,
    )
    asr_task_id = asr_res.get("task_id") if asr_res else None
    if not asr_task_id:
        logger.error("Step5 提交 ASR 任务失败")
        sys.exit(1)

    try:
        asr_info = wait_for_task(asr_task_id, logger)
    except RuntimeError as exc:
        msg = str(exc)
        if "whisper_init_from_file_with_params" in msg:
            hint = _build_asr_model_hint(whisper_model_dir, whisper_model_name)
            logger.error("%s", hint)
            raise RuntimeError(f"{msg}\n{hint}") from exc
        raise

    logger.info("Step5 ASR 任务成功: %s", asr_info)

    print_step(6, "Translating SRT with OpenAI SDK and generating ASS...")
    ass_file = os.path.join(output_path, vid, f"{vid}.ass")
    if not os.path.exists(srt_file):
        logger.error("Step6 失败，SRT 文件不存在: %s", srt_file)
        raise FileNotFoundError(f"SRT file not found: {srt_file}")

    translate_srt_to_ass(
        srt_file,
        ass_file,
        logger,
        model=openai_model,
        api_key=openai_api_key,
        base_url=openai_base_url or None,
    )
    logger.info("Step6 完成，ASS 输出: %s", ass_file)

    print_step(7, "Composing mp4 + m4a + ass via C++ API...")
    video_abs = f"/data/input/{vid}/{vid}.mp4"
    audio_abs = f"/data/input/{vid}/{vid}.m4a"
    subtitle_abs = f"/data/input/{vid}/{vid}.ass"
    output_abs = f"/data/output/{vid}.final.mp4"

    compose_res = compose_video(video_abs, audio_abs, subtitle_abs, output_abs)
    compose_task_id = compose_res.get("task_id") if compose_res else None
    if not compose_task_id:
        logger.error("Step6 提交 compose 任务失败")
        sys.exit(1)

    try:
        compose_info = wait_for_task(compose_task_id, logger)
        logger.info("Step7 合成任务成功: %s", compose_info)
    except RuntimeError as exc:
        msg = str(exc)
        if "open mov_text encoder" not in msg:
            raise

        logger.warning("Step7 检测到 mov_text 编码器不可用，回退为仅合并音视频（不内嵌字幕）")
        fallback_output_abs = f"/data/output/{vid}.final.no_sub.mp4"
        merge_res = merge_video_audio(video_abs, audio_abs, fallback_output_abs)
        merge_task_id = merge_res.get("task_id") if merge_res else None
        if not merge_task_id:
            logger.error("Step7 回退 merge 任务提交失败")
            raise

        merge_info = wait_for_task(merge_task_id, logger)
        logger.info("Step7 回退 merge 任务成功: %s", merge_info)
        output_abs = fallback_output_abs

    print_step(8, f"全部流程完成: {output_abs}")


if __name__ == "__main__":
    main()
