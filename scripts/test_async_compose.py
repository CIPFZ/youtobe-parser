#!/usr/bin/env python3
"""Async check for final compose step: submit task, poll status, and validate output streams."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from typing import Any

import httpx


async def submit_compose(base_url: str, payload: dict[str, str]) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(f"{base_url}/compose", json=payload)
        r.raise_for_status()
        data = r.json()
        task_id = data.get("task_id")
        if not task_id:
            raise RuntimeError(f"compose submit failed: {data}")
        return task_id


async def wait_task(base_url: str, task_id: str, sleep_s: float, max_retries: int) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        for _ in range(max_retries):
            r = await client.get(f"{base_url}/task", params={"task_id": task_id})
            r.raise_for_status()
            data = r.json()
            status = data.get("status")
            print(f"task={task_id} status={status} progress={data.get('progress')} msg={data.get('message')}")
            if status == "SUCCESS":
                return data
            if status == "FAILED":
                raise RuntimeError(f"task failed: {data.get('message')}")
            await asyncio.sleep(sleep_s)
    raise TimeoutError(f"task timeout: {task_id}")


def probe_streams(path: str) -> set[str]:
    rsp = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", path],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(rsp.stdout or "{}")
    return {str(s.get("codec_type")) for s in data.get("streams", []) if s.get("codec_type")}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Async compose check with stream validation")
    parser.add_argument("--base-url", default="http://127.0.0.1:8888/api/v1")
    parser.add_argument("--video-path", default="/data/input/iMDibaO4dXw/iMDibaO4dXw.mp4")
    parser.add_argument("--audio-path", default="/data/input/iMDibaO4dXw/iMDibaO4dXw.m4a")
    parser.add_argument("--subtitle-path", default="/data/input/iMDibaO4dXw/iMDibaO4dXw.ass")
    parser.add_argument("--output-path", default="/data/output/iMDibaO4dXw_merge.mp4")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=180)
    args = parser.parse_args()

    task_id = await submit_compose(
        args.base_url,
        {
            "video_path": args.video_path,
            "audio_path": args.audio_path,
            "subtitle_path": args.subtitle_path,
            "output_path": args.output_path,
        },
    )
    await wait_task(args.base_url, task_id, args.sleep, args.max_retries)

    streams = probe_streams(args.output_path)
    if "video" not in streams or "audio" not in streams:
        raise RuntimeError(f"invalid output streams for {args.output_path}: {sorted(streams)}")

    print(f"ok: {args.output_path} streams={sorted(streams)}")


if __name__ == "__main__":
    asyncio.run(main())
