from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import yt_dlp

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
    opts: dict[str, Any] = {
        'quiet': False,
        'noplaylist': True,
        'outtmpl': str(out_dir / '%(title).100s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
    }
    if cookie_file:
        opts['cookiefile'] = cookie_file
    if proxy_url:
        opts['proxy'] = proxy_url

    if normalized_url != url:
        logger.info('Playlist-style URL normalized to first-item URL. from=%s to=%s', url, normalized_url)

    logger.info('yt-dlp start. url=%s proxy=%s output_dir=%s strategy=%s', normalized_url, proxy_url or 'none', out_dir, playlist_strategy)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(normalized_url, download=True)
        req = ydl.prepare_filename(info)

    downloaded = Path(req)
    stem = downloaded.stem

    video_candidates = sorted(out_dir.glob(f'{stem}*.mp4')) + sorted(out_dir.glob(f'{stem}*.webm'))
    audio_candidates = sorted(out_dir.glob(f'{stem}*.m4a')) + sorted(out_dir.glob(f'{stem}*.webm'))

    if not video_candidates or not audio_candidates:
        raise RuntimeError('无法找到下载后的音频/视频文件，请检查 yt-dlp 输出格式。')

    metadata = _build_video_metadata(
        info=info,
        source_url=url,
        normalized_url=normalized_url,
        playlist_strategy=playlist_strategy,
    )

    logger.info('yt-dlp completed. title=%s video_candidates=%d audio_candidates=%d', info.get('title', stem), len(video_candidates), len(audio_candidates))
    return {
        'title': info.get('title', stem),
        'video_path': video_candidates[0],
        'audio_path': audio_candidates[-1],
        'metadata': metadata,
    }
