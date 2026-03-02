#!/usr/bin/env python3
"""Translate SRT/VTT via OpenAI-compatible LLM then write ASS."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.core.translator import translate_subtitle


async def _run(path: str) -> None:
    task_id = uuid.uuid4().hex
    await translate_subtitle(path=path, task_id=task_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate subtitle and output ASS by script.")
    parser.add_argument("path", help="Local SRT/VTT path or http(s) URL")
    parser.add_argument("--proxy", default="", help="Override GLOBAL_PROXY for this run")
    parser.add_argument("--openai-api-key", default="", help="Override OPENAI_API_KEY for this run")
    args = parser.parse_args()

    if args.proxy:
        os.environ["GLOBAL_PROXY"] = args.proxy
        settings.global_proxy = args.proxy
    if args.openai_api_key:
        os.environ["OPENAI_API_KEY"] = args.openai_api_key
        settings.openai_api_key = args.openai_api_key

    asyncio.run(_run(args.path))


if __name__ == "__main__":
    main()
