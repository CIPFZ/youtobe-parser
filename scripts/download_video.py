#!/usr/bin/env python3
"""Download best video+audio using yt-dlp with optional scientific proxy."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yt_dlp


def main() -> None:
    parser = argparse.ArgumentParser(description="Download YouTube video/audio with proxy support.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output-dir", default="downloads", help="Output directory")
    parser.add_argument("--proxy", default="", help="Proxy URL, e.g. socks5://127.0.0.1:7890")
    parser.add_argument("--cookie-file", default="", help="Netscape cookies file path")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout seconds")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    opts: dict[str, Any] = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(Path(args.output_dir) / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "retries": 3,
        "socket_timeout": args.timeout,
    }
    if args.proxy:
        opts["proxy"] = args.proxy
    if args.cookie_file:
        opts["cookiefile"] = args.cookie_file

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([args.url])


if __name__ == "__main__":
    main()
