#!/usr/bin/env python3
"""Parse a YouTube URL, log the best formats, and download best video+audio."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yt_dlp


def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("ydl_parser_downloader")
    logger.setLevel(logging.DEBUG)
    
    # File handler for saving logs
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and Download YouTube video/audio with logging and step output.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output-dir", default="downloads", help="Output directory")
    parser.add_argument("--proxy", default="", help="Proxy URL, e.g. socks5://127.0.0.1:7890")
    parser.add_argument("--cookie-file", default="", help="Netscape cookies file path")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout seconds")
    parser.add_argument("--log-file", default="process.log", help="Log file path")
    args = parser.parse_args()

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
    print(f"Saved all metadata to {metadata_file}")

    parsed_formats = _best_formats(info)
    formats_json = json.dumps(parsed_formats, ensure_ascii=False, indent=2)
    print("\nParsed Best Formats:")
    print(formats_json)
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
        "outtmpl": str(output_path / "%(id)s" / "%(id)s_%(format_id)s.%(ext)s"),
        "noplaylist": True,
        "retries": 3,
        "quiet": False,  # Allow yt-dlp's default progress bar
    })

    print(download_opts)

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([args.url])
            logger.info("Download completed successfully.")
    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        print(f"Error downloading: {e}")
        sys.exit(1)

    # --- Step 3: Complete ---
    print_step(3, "Process finished!")
    logger.info("=== Process finished completely ===")


if __name__ == "__main__":
    main()
