from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import yt_dlp

from app.settings import settings

logger = logging.getLogger(__name__)


def _normalize_youtube_url_for_first_item(url: str) -> str:
    """For playlist-style links with a concrete `v`, keep that video URL only."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    video_ids = query.get('v')
    if not video_ids:
        return url
    clean_query = urlencode({'v': video_ids[0]})
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))


def _build_video_metadata(info: dict[str, Any], source_url: str, normalized_url: str, playlist_strategy: str) -> dict[str, Any]:
    return {
        'id': info.get('id'),
        'title': info.get('title'),
        'uploader': info.get('uploader'),
        'duration': info.get('duration'),
        'webpage_url': info.get('webpage_url'),
        'extractor': info.get('extractor'),
        'source_url': source_url,
        'normalized_url': normalized_url,
        'playlist_strategy': playlist_strategy,
    }


def _ytdlp_opts(out_dir: Path, selector: str, cookie_file: str, proxy_url: str) -> dict[str, Any]:
    opts: dict[str, Any] = {
        'quiet': False,
        'noplaylist': True,
        'outtmpl': str(out_dir / '%(id)s.%(ext)s'),
        'format': selector,
    }
    if cookie_file:
        opts['cookiefile'] = cookie_file
    if proxy_url:
        opts['proxy'] = proxy_url
    return opts


def _selector_candidates(stream_kind: str) -> list[str]:
    primary = settings.ytdlp_video_format if stream_kind == 'video' else settings.ytdlp_audio_format
    if stream_kind == 'video':
        fallback = ['bestvideo/best', 'best']
    else:
        fallback = ['bestaudio/best', 'best']

    candidates: list[str] = []
    for sel in [primary, *fallback]:
        if sel and sel not in candidates:
            candidates.append(sel)
    return candidates


def _download_stream(normalized_url: str, out_dir: Path, stream_kind: str, cookie_file: str, proxy_url: str) -> tuple[dict[str, Any], Path]:
    last_exc: Exception | None = None
    info: dict[str, Any] | None = None
    selector_used = ''

    for selector in _selector_candidates(stream_kind):
        selector_used = selector
        opts = _ytdlp_opts(out_dir=out_dir, selector=selector, cookie_file=cookie_file, proxy_url=proxy_url)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(normalized_url, download=True)
            break
        except Exception as exc:
            last_exc = exc
            message = str(exc)
            unavailable = 'Requested format is not available' in message
            logger.warning(
                'yt-dlp %s download failed with selector=%s. unavailable=%s err=%s',
                stream_kind,
                selector,
                unavailable,
                message,
            )
            if unavailable:
                continue
            raise

    if info is None:
        raise RuntimeError(
            f'Failed to download {stream_kind}. tried selectors={_selector_candidates(stream_kind)}'
        ) from last_exc

    video_id = info.get('id')
    if not video_id:
        raise RuntimeError('yt-dlp did not return video id.')

    ext = 'mp4' if stream_kind == 'video' else 'm4a'
    target = out_dir / f'{video_id}.{ext}'
    if target.exists():
        return info, target

    # fallback for edge cases where preferred ext is unavailable
    fallback = sorted(out_dir.glob(f'{video_id}.*'))
    if not fallback:
        raise RuntimeError(
            f'Cannot find downloaded {stream_kind} file for id={video_id}, selector={selector_used}'
        )
    logger.warning('Preferred %s extension %s not found, fallback=%s', stream_kind, ext, fallback[0])
    return info, fallback[0]


def download_media(
    url: str,
    out_dir: Path,
    cookie_file: str = '',
    proxy_url: str = '',
    playlist_strategy: str = 'first',
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    if playlist_strategy not in {'first'}:
        raise ValueError('playlist_strategy currently supports only: first')

    normalized_url = _normalize_youtube_url_for_first_item(url)

    if normalized_url != url:
        logger.info('Playlist-style URL normalized to first-item URL. from=%s to=%s', url, normalized_url)

    logger.info('yt-dlp start. url=%s proxy=%s output_dir=%s strategy=%s video_format=%s audio_format=%s', normalized_url, proxy_url or 'none', out_dir, playlist_strategy, settings.ytdlp_video_format, settings.ytdlp_audio_format)

    video_info, video_path = _download_stream(normalized_url, out_dir, 'video', cookie_file, proxy_url)
    _audio_info, audio_path = _download_stream(normalized_url, out_dir, 'audio', cookie_file, proxy_url)

    metadata = _build_video_metadata(
        info=video_info,
        source_url=url,
        normalized_url=normalized_url,
        playlist_strategy=playlist_strategy,
    )

    logger.info('yt-dlp completed. id=%s title=%s video=%s audio=%s', metadata.get('id'), metadata.get('title'), video_path, audio_path)
    return {
        'title': video_info.get('title', video_info.get('id', 'unknown')),
        'video_path': video_path,
        'audio_path': audio_path,
        'metadata': metadata,
    }
