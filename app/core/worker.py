"""yt-dlp based async video analysis worker."""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import time
from pathlib import Path
from http.cookiejar import MozillaCookieJar
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

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
    use_proxy: bool = True,
    player_client: str = "web",
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
    if use_proxy and settings.global_proxy:
        opts["proxy"] = settings.global_proxy

    # Optional YouTube cookies (Netscape format)
    cookie_file = _resolve_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    # YouTube extractor args (client + optional PO token)
    yt_args: list[str] = [f"player_client={player_client}"]
    if po_token:
        yt_args.append(f"po_token=web+{po_token}")
        if content_binding:
            yt_args.append(f"po_token_visitor_data={content_binding}")
        logger.info("PO Token injected into yt-dlp extractor args")
    else:
        logger.info("Using yt-dlp without PO token (player_client=%s)", player_client)

    opts["extractor_args"] = {"youtube": yt_args}
    return opts


def _inspect_cookie_file(cookie_path: Path) -> str:
    """Return a short health summary for a Netscape/Mozilla cookie file."""
    jar = MozillaCookieJar()
    try:
        jar.load(str(cookie_path), ignore_discard=True, ignore_expires=True)
    except Exception as exc:
        logger.warning("Failed to parse cookie file %s: %s", cookie_path, exc)
        return "cookie file parse failed"

    now = time.time()
    total = 0
    yt_total = 0
    yt_alive = 0
    sid_like = 0

    for ck in jar:
        total += 1
        domain = (ck.domain or '').lower()
        name = (ck.name or '').upper()
        is_yt = ('youtube.com' in domain) or ('google.com' in domain)
        if not is_yt:
            continue
        yt_total += 1
        if not ck.expires or ck.expires > now:
            yt_alive += 1
        if name in {'SID', '__SECURE-1PSID', '__SECURE-3PSID', 'SAPISID', '__SECURE-1PSIDTS', '__SECURE-3PSIDTS'}:
            sid_like += 1

    summary = f"cookies(total={total}, yt={yt_total}, yt_alive={yt_alive}, sid_like={sid_like})"
    if yt_total == 0:
        logger.warning("Cookie file %s has no youtube/google cookies: %s", cookie_path, summary)
    elif yt_alive == 0:
        logger.warning("Cookie file %s has no unexpired youtube/google cookies: %s", cookie_path, summary)
    else:
        logger.info("Cookie diagnostics for %s: %s", cookie_path, summary)

    return summary


def _resolve_cookie_file() -> str:
    """Resolve an existing cookie file path for yt-dlp and emit diagnostic logs."""
    configured = (settings.youtube_cookie_file or "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists() and configured_path.is_file():
            logger.info("Using configured YouTube cookie file: %s", configured_path)
            _inspect_cookie_file(configured_path)
            return str(configured_path)
        logger.warning("Configured YOUTUBE_COOKIE_FILE not found or not a file: %s", configured_path)

    # Default/auto-discovery candidates inside container mounts
    search_roots = [Path('/app/secrets'), Path('/app/secrents')]
    preferred_names = ['youtube_cookies.txt', 'cookies.txt', 'youtube.txt']

    for root in search_roots:
        for name in preferred_names:
            path = root / name
            if path.exists() and path.is_file():
                logger.info("Using discovered YouTube cookie file: %s", path)
                _inspect_cookie_file(path)
                return str(path)

    for root in search_roots:
        if root.exists() and root.is_dir():
            for path in sorted(root.iterdir()):
                if path.is_file() and path.suffix.lower() in {'.txt', '.cookies', '.cookie'}:
                    logger.info("Using discovered YouTube cookie file: %s", path)
                    _inspect_cookie_file(path)
                    return str(path)

    # Helpful typo hint for common misspelling
    if Path('/app/secrents').exists() and not Path('/app/secrets').exists():
        logger.warning("Detected /app/secrents but /app/secrets is missing. Did you mean 'secrets'?")

    logger.info("No usable YouTube cookie file found; continuing without cookies")
    return ""


def _is_bot_check_error(err_text: str) -> bool:
    lowered = err_text.lower()
    return ("sign in to confirm you’re not a bot" in lowered) or ("sign in to confirm you're not a bot" in lowered)


async def _extract_with_fallbacks(
    url: str,
    task_id: str,
    loop: asyncio.AbstractEventLoop,
    *,
    po_token: str,
    content_binding: str,
) -> dict[str, Any]:
    """Try multiple yt-dlp strategies for flaky YouTube bot-check/proxy scenarios."""
    strategies = [
        {"name": "po+proxy+web", "use_proxy": True, "use_po": True, "player_client": "web"},
        {"name": "po-no-proxy+web", "use_proxy": False, "use_po": True, "player_client": "web"},
        {"name": "cookie-only+proxy+web", "use_proxy": True, "use_po": False, "player_client": "web"},
        {"name": "cookie-only+proxy+android", "use_proxy": True, "use_po": False, "player_client": "android"},
        {"name": "cookie-only+no-proxy+android", "use_proxy": False, "use_po": False, "player_client": "android"},
    ]

    # skip no-proxy attempts if proxy isn't configured or retry is disabled
    if (not settings.global_proxy) or (not settings.retry_without_proxy_on_refused):
        strategies = [s for s in strategies if s["use_proxy"]]

    last_exc: Exception | None = None
    for idx, s in enumerate(strategies, start=1):
        logger.info("Task %s yt-dlp attempt %d/%d strategy=%s", task_id, idx, len(strategies), s["name"])
        opts = _build_ydl_opts(
            task_id,
            loop,
            po_token=po_token if s["use_po"] else "",
            content_binding=content_binding if s["use_po"] else "",
            use_proxy=s["use_proxy"],
            player_client=s["player_client"],
        )

        try:
            return await loop.run_in_executor(None, functools.partial(_extract_sync, url, opts))
        except DownloadError as exc:
            last_exc = exc
            err = str(exc)
            proxy_refused = ("connection refused" in err.lower() or "[errno 111]" in err.lower()) and bool(settings.global_proxy)
            bot_error = _is_bot_check_error(err)

            # only continue retry chain for known recoverable patterns
            if not (proxy_refused or bot_error):
                raise

            if idx == len(strategies):
                raise

            logger.warning(
                "Task %s attempt %s failed (%s). Retrying with next strategy.",
                task_id,
                s["name"],
                "proxy_refused" if proxy_refused else "bot_check",
            )

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("yt-dlp extraction failed without a captured exception")


def _extract_sync(url: str, opts: dict[str, Any]) -> dict[str, Any]:
    """Run yt-dlp extract_info in a blocking manner (called in executor)."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


async def analyze_video(url: str, task_id: str) -> None:
    """Top-level async entry: extract all formats for *url* and update the task store."""
    sem = _get_semaphore()
    await task_store.update_task(task_id, status="processing", progress=5.0)

    try:
        # Fetch PO Token from provider (graceful fallback if unavailable)
        video_id = _extract_video_id(url)
        token = await fetch_po_token(video_id)
        await task_store.update_task(task_id, progress=20.0)

        async with sem:
            loop = asyncio.get_running_loop()
            info: dict[str, Any] = await _extract_with_fallbacks(
                url,
                task_id,
                loop,
                po_token=token.po_token if token else "",
                content_binding=token.content_binding if token else "",
            )

        await task_store.update_task(task_id, progress=70.0)

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
        err_text = str(exc)
        if _is_bot_check_error(err_text):
            configured_cookie = (settings.youtube_cookie_file or '').strip()
            err_text += (
                " | Hint: configure YOUTUBE_COOKIE_FILE with exported YouTube cookies (Netscape format)."
                + (f" Current YOUTUBE_COOKIE_FILE={configured_cookie!r}." if configured_cookie else " YOUTUBE_COOKIE_FILE is empty.")
                + " In Docker compose, host ./data/secrets is mounted to /app/secrets."
                + " Check that cookies are freshly exported (Netscape format) and include unexpired youtube/google SID-like cookies."
            )
        await task_store.update_task(
            task_id,
            status="failed",
            error=err_text,
        )
