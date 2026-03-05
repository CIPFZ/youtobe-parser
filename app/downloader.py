from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp


def download_media(url: str, out_dir: Path, cookie_file: str = '', proxy_url: str = '') -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
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

    with yt_dlp.YoutubeDL(opts) as ydl:
        # extract_info with download=True covers both metadata parsing and actual download.
        info = ydl.extract_info(url, download=True)
        req = ydl.prepare_filename(info)

    downloaded = Path(req)
    stem = downloaded.stem

    video_candidates = sorted(out_dir.glob(f'{stem}*.mp4')) + sorted(out_dir.glob(f'{stem}*.webm'))
    audio_candidates = sorted(out_dir.glob(f'{stem}*.m4a')) + sorted(out_dir.glob(f'{stem}*.webm'))

    if not video_candidates or not audio_candidates:
        raise RuntimeError('无法找到下载后的音频/视频文件，请检查 yt-dlp 输出格式。')

    return {
        'title': info.get('title', stem),
        'video_path': video_candidates[0],
        'audio_path': audio_candidates[-1],
    }
