#!/usr/bin/env python3
"""Parse a YouTube URL and print best playable stream URLs."""

from __future__ import annotations

import argparse
import json
from typing import Any

import yt_dlp


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Input YouTube URL and output best parsed stream URL(s).")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--proxy", default="", help="Proxy URL, e.g. socks5://127.0.0.1:7890")
    parser.add_argument("--cookie-file", default="", help="Netscape cookies file path")
    args = parser.parse_args()

    opts: dict[str, Any] = {"quiet": True, "skip_download": True, "no_warnings": True}
    if args.proxy:
        opts["proxy"] = args.proxy
    if args.cookie_file:
        opts["cookiefile"] = args.cookie_file

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(args.url, download=False)

    print(json.dumps(_best_formats(info), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
