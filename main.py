#!/usr/bin/env python3
"""Parse a YouTube URL, log the best formats, and download best video+audio."""

from __future__ import annotations

import argparse
import json
import logging
import os.path
import sys
import time

import requests
from pathlib import Path
from typing import Any

import yt_dlp


def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("ydl_parser_downloader")
    logger.setLevel(logging.DEBUG)
    
    # File handler for saving logs
    Path(os.path.dirname(log_file)).mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
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
        } if best_muxed else None,
        "best_video": {
            "format_id": best_video.get("format_id"),
            "ext": best_video.get("ext"),
            "resolution": best_video.get("resolution"),
            "url": best_video.get("url"),
        } if best_video else None,
        "best_audio": {
            "format_id": best_audio.get("format_id"),
            "ext": best_audio.get("ext"),
            "abr": best_audio.get("abr"),
            "url": best_audio.get("url"),
        } if best_audio else None,
    }


def print_step(step: int, message: str) -> None:
    print(f"\n{'='*50}")
    print(f"[Step {step}] {message}")
    print(f"{'='*50}\n")


BASE_URL = "http://127.0.0.1:8888/api/v1"


def convert_m4a_to_wav(input_path, output_path):
    """发起音频转换任务"""
    url = f"{BASE_URL}/audio/m4a-to-wav"
    payload = {
        "input_path": input_path,
        "output_path": output_path
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # 检查 HTTP 状态码
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None


def get_task_status(task_id):
    """查询任务进度"""
    url = f"{BASE_URL}/task"
    params = {"task_id": task_id}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"查询失败: {e}")
        return None


def wait_for_task(task_id: str, logger: logging.Logger, poll_interval: int = 2, max_retries: int = 300) -> dict:
    """
    通用任务等待方法
    :param task_id: 任务ID
    :param logger: 日志记录器
    :param poll_interval: 轮询间隔（秒）
    :param max_retries: 最大尝试次数
    :return: 任务完成后的最终状态信息 (dict)
    """
    logger.info(f"开始轮询任务: {task_id}")
    print(f"[{task_id}] 等待任务完成...")

    for _ in range(max_retries):
        try:
            status_info = get_task_status(task_id)

            if not status_info or "error" in status_info:
                error_msg = status_info.get("error", "Unknown API error")
                logger.error(f"任务 {task_id} 出错: {error_msg}")
                raise RuntimeError(f"API Error: {error_msg}")

            status = status_info.get("status")
            progress = status_info.get("progress", 0)

            print(f"\r进度: {progress}% - 状态: {status}", end="", flush=True)

            if status == "SUCCESS":
                print("\n任务完成！")
                return status_info

            if status == "FAILED":
                logger.error(f"任务 {task_id} 失败: {status_info.get('message')}")
                raise RuntimeError(f"Task Failed: {status_info.get('message')}")

        except Exception as e:
            logger.error(f"查询任务状态时发生异常: {e}")
            raise e

        time.sleep(poll_interval)

    raise TimeoutError(f"任务 {task_id} 等待超时")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and Download YouTube video/audio with logging and step output.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output-dir", default="data/input", help="Output directory")
    parser.add_argument("--proxy", default="", help="Proxy URL, e.g. socks5://127.0.0.1:7890")
    parser.add_argument("--cookie-file", default="", help="Netscape cookies file path")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout seconds")
    parser.add_argument("--log-file", default="logs/process.log", help="Log file path")
    args = parser.parse_args()

    # 目录初始化
    Path("data/input").mkdir(parents=True, exist_ok=True)
    Path("data/output").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    logger = setup_logger(args.log_file)
    logger.info(f"=== Starting process for {args.url} ===")
    
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_opts: dict[str, Any] = {
        "proxy": args.proxy if args.proxy else None,
        "cookiefile": args.cookie_file if args.cookie_file else None,
        "socket_timeout": args.timeout,
    }
    # Remove None values
    base_opts = {k: v for k, v in base_opts.items() if v is not None}

    # --- Step 1: Parse ---
    print_step(1, "Parsing URL and extracting info...")
    logger.info("Step 1: Extracting info...")
    parse_opts = base_opts.copy()
    parse_opts.update({
        "quiet": True, 
        "skip_download": True, 
        "no_warnings": True
    })

    try:
        with yt_dlp.YoutubeDL(parse_opts) as ydl:
            info = ydl.extract_info(args.url, download=False)
            logger.info("Successfully extracted info.")
    except Exception as e:
        logger.error(f"Failed to extract info: {e}", exc_info=True)
        print(f"Error extracting info: {e}")
        sys.exit(1)

    vid = info.get("id") or "unknown_vid"
    vid_dir = output_path / vid
    vid_dir.mkdir(parents=True, exist_ok=True)

    # Save all info to metadata.json
    metadata_file = vid_dir / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved all parsed info to {metadata_file}")

    parsed_formats = _best_formats(info)
    formats_json = json.dumps(parsed_formats, ensure_ascii=False, indent=2)
    logger.info("Parsed best formats successfully.")
    logger.debug(f"Format details: {formats_json}")

    # --- Step 2: Download ---
    print_step(2, "Downloading best formats...")
    logger.info("Step 2: Starting download for video and audio separately...")

    # We want bestvideo as mp4 and bestaudio as m4a. 
    # And we want them to go into output_dir/<vid>/<vid>_<format_id>.<ext>
    # In yt-dlp, %(id)s is the video ID (vid).
    download_opts = base_opts.copy()
    download_opts.update({
        "format": "bestvideo[ext=mp4],bestaudio[ext=m4a]",
        "outtmpl": str(output_path / "%(id)s" / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "retries": 3,
        "quiet": False,  # Allow yt-dlp's default progress bar
    })

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([args.url])
            logger.info("Download completed successfully.")
    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        print(f"Error downloading: {e}")
        sys.exit(1)

    # --- Step 3: 将音频 m4a 转换为 wav ---
    print_step(3, "Process finished!")
    logger.info("=== Process finished completely ===")

    # --- Step 4: wav 生成 字幕 srt 文件 ---
    submit_res = convert_m4a_to_wav(f"/data/input/{vid}.m4a", f"/data/input/{vid}.wav")
    task_id = submit_res.get("task_id")

    if task_id:
        # 2. 直接调用通用等待方法
        final_info = wait_for_task(task_id, logger)
        # 任务成功后，你可以继续后续处理
        logger.info(f"转换任务 {task_id} 成功: {final_info}")
    else:
        logger.error("提交任务失败，未获得 task_id")

    # --- Step 5: TODO 字幕 srt 文件 进行翻译并生成 ass 文件 ---
    srt_file = os.path.join(output_path, vid, f"{vid}.srt")
    ass_file = os.path.join(output_path, vid, f"{vid}.ass")

    # --- Step 6: ass字幕 + m4a + mp4 合并 ---
    video_file = os.path.join(output_path, vid, f"{vid}.mp4")


if __name__ == "__main__":
    logger = setup_logger("logs/process.log")
    vid = "iMDibaO4dXw"
    # # --- Step 4: wav 生成 字幕 srt 文件 ---
    # submit_res = convert_m4a_to_wav(f"/data/input/{vid}/audio.m4a", f"/data/input/{vid}/audio.wav")
    # task_id = submit_res.get("task_id")
    #
    # if task_id:
    #     # 2. 直接调用通用等待方法
    #     final_info = wait_for_task(task_id, logger)
    #     # 任务成功后，你可以继续后续处理
    #     print(f"转换任务 {task_id} 成功: {final_info}")
    # else:
    #     print("提交任务失败，未获得 task_id")



