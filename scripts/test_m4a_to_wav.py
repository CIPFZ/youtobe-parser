#!/usr/bin/env python3
"""Parse a YouTube URL, run C++ media pipeline, translate subtitles, and compose final video."""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8888/api/v1"
SRT_TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})")


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


def wait_for_task(task_id: str, poll_interval: int = 2, max_retries: int = 300) -> dict[str, Any]:
    print("开始轮询任务: %s", task_id)
    print(f"[{task_id}] 等待任务完成...")

    for _ in range(max_retries):
        status_info = get_task_status(task_id)
        if not status_info or "error" in status_info:
            error_msg = status_info.get("error", "Unknown API error") if status_info else "Unknown API error"
            print("任务 %s 出错: %s", task_id, error_msg)
            raise RuntimeError(f"API Error: {error_msg}")

        status = status_info.get("status")
        progress = status_info.get("progress", 0)
        print(f"\r进度: {progress}% - 状态: {status}", end="", flush=True)

        if status == "SUCCESS":
            print("\n任务完成！")
            return status_info
        if status == "FAILED":
            print("任务 %s 失败: %s", task_id, status_info.get("message"))
            raise RuntimeError(f"Task Failed: {status_info.get('message')}")

        time.sleep(poll_interval)

    raise TimeoutError(f"任务 {task_id} 等待超时")


def main() -> None:
    parser = argparse.ArgumentParser(description="M4A TO MAV")
    parser.add_argument("--m4a", required=True, help="M4A file path")
    parser.add_argument("--wav", required=True, help="WAV file path")
    args = parser.parse_args()

    print(f"M4A to WAV 参数: m4a: {args.m4a}, wav: {args.wav}")
    submit_res = convert_m4a_to_wav(args.m4a, args.wav)
    task_id = submit_res.get("task_id") if submit_res else None
    if not task_id:
        print("提交 m4a->wav 任务失败")
        sys.exit(1)

    final_info = wait_for_task(task_id)
    print("转换任务 %s 成功: %s", task_id, final_info)


if __name__ == "__main__":
    main()
