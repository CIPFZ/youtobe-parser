"""yt-dlp based async video analysis worker."""

from __future__ import annotations

import asyncio
import functools
import logging
import re
from typing import Any

import yt_dlp

from app.config import settings
from app.core.pot_client import fetch_po_token
from app.core.task_store import task_store
from app.models.schemas import VideoFormat, VideoInfo

logger = logging.getLogger(__name__)

# Concurrency limiter
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
    return _semaphore


def _categorize_format(fmt: dict[str, Any]) -> str:
    """Classify a yt-dlp format dict into muxed / video_only / audio_only."""
    vcodec = fmt.get("vcodec", "none")
    acodec = fmt.get("acodec", "none")
    has_video = vcodec not in ("none", None)
    has_audio = acodec not in ("none", None)
    if has_video and has_audio:
        return "muxed"
    if has_video:
        return "video_only"
    if has_audio:
        return "audio_only"
    return "unknown"


# Regex to extract YouTube video ID from URL
_YT_VIDEO_ID_RE = re.compile(
    r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})"
)


def _extract_video_id(url: str) -> str:
    """Try to extract a YouTube video ID from a URL."""
    m = _YT_VIDEO_ID_RE.search(url)
    return m.group(1) if m else ""


def _build_ydl_opts(
    task_id: str,
    loop: asyncio.AbstractEventLoop,
    *,
    po_token: str = "",
    content_binding: str = "",
) -> dict[str, Any]:
    """Build yt-dlp option dict, optionally with PO Token."""

    def _progress_hook(d: dict[str, Any]) -> None:
        """Sync hook called by yt-dlp – schedule async update."""
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            pct = (downloaded / total * 100) if total else 0.0
            asyncio.run_coroutine_threadsafe(
                task_store.update_task(task_id, progress=round(pct, 1)),
                loop,
            )

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,          # we only extract info, no download
        "progress_hooks": [_progress_hook],
    }

    # Proxy
    if settings.global_proxy:
        opts["proxy"] = settings.global_proxy

    # PO Token injection from HTTP Provider
    if po_token:
        yt_args: list[str] = [f"po_token=web+{po_token}"]
        if content_binding:
            yt_args.append(f"po_token_visitor_data={content_binding}")
        opts["extractor_args"] = {"youtube": yt_args}
        logger.info("PO Token injected into yt-dlp extractor args")

    return opts


def _extract_sync(url: str, opts: dict[str, Any]) -> dict[str, Any]:
    """Run yt-dlp extract_info in a blocking manner (called in executor)."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


async def analyze_video(url: str, task_id: str) -> None:
    """Top-level async entry: extract all formats for *url* and update the task store."""
    sem = _get_semaphore()
    await task_store.update_task(task_id, status="processing")

    try:
        # Fetch PO Token from provider (graceful fallback if unavailable)
        video_id = _extract_video_id(url)
        token = await fetch_po_token(video_id)

        async with sem:
            loop = asyncio.get_running_loop()
            opts = _build_ydl_opts(
                task_id,
                loop,
                po_token=token.po_token if token else "",
                content_binding=token.content_binding if token else "",
            )
            info: dict[str, Any] = await loop.run_in_executor(
                None, functools.partial(_extract_sync, url, opts)
            )

        # Parse formats
        raw_formats: list[dict[str, Any]] = info.get("formats") or []
        formats: list[VideoFormat] = []
        for f in raw_formats:
            cat = _categorize_format(f)
            formats.append(
                VideoFormat(
                    format_id=f.get("format_id", ""),
                    ext=f.get("ext", ""),
                    resolution=f.get("resolution"),
                    fps=f.get("fps"),
                    vcodec=f.get("vcodec"),
                    acodec=f.get("acodec"),
                    filesize=f.get("filesize"),
                    filesize_approx=f.get("filesize_approx"),
                    tbr=f.get("tbr"),
                    url=f.get("url"),
                    format_note=f.get("format_note"),
                    category=cat,
                )
            )

        video_info = VideoInfo(
            title=info.get("title", "Unknown"),
            thumbnail=info.get("thumbnail"),
            duration=info.get("duration"),
            channel=info.get("channel") or info.get("uploader"),
            channel_url=info.get("channel_url") or info.get("uploader_url"),
            view_count=info.get("view_count"),
            upload_date=info.get("upload_date"),
            webpage_url=info.get("webpage_url", url),
            formats=formats,
        )

        await task_store.update_task(
            task_id,
            status="completed",
            progress=100.0,
            result=video_info.model_dump(),
        )
        logger.info("Task %s completed – %d formats found", task_id, len(formats))

    except Exception as exc:
        logger.exception("Task %s failed", task_id)
        await task_store.update_task(
            task_id,
            status="failed",
            error=str(exc),
        )
