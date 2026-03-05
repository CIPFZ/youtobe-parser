from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

from app.settings import settings

logger = logging.getLogger(__name__)


def ffmpeg_bin() -> str:
    """Resolve ffmpeg binary path.

    Priority:
    1) FFMPEG_PATH from settings (.env / env var)
    2) PATH lookup for "ffmpeg"
    3) imageio-ffmpeg managed binary
    """
    custom = settings.ffmpeg_path.strip()
    if custom:
        p = Path(custom).expanduser()
        if p.exists() and p.is_file():
            logger.info('Using custom ffmpeg binary: %s', p)
            return str(p)
        raise FileNotFoundError(f'Configured FFMPEG_PATH does not exist: {custom}')

    system_ffmpeg = shutil.which('ffmpeg')
    if system_ffmpeg:
        logger.info('Using system ffmpeg binary: %s', system_ffmpeg)
        return system_ffmpeg

    resolved = imageio_ffmpeg.get_ffmpeg_exe()
    logger.info('Using imageio-managed ffmpeg binary: %s', resolved)
    return resolved


def run_ffmpeg(args: list[str]) -> None:
    cmd = [ffmpeg_bin(), '-y', *args]
    logger.info('Running ffmpeg command: %s', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def merge_av_with_ass(video: Path, audio: Path, ass: Path, out: Path) -> None:
    logger.info('Merging A/V with subtitles. video=%s audio=%s ass=%s out=%s', video, audio, ass, out)
    run_ffmpeg(
        [
            '-i', str(video),
            '-i', str(audio),
            '-vf', f'ass={ass.as_posix()}',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '20',
            '-c:a', 'aac',
            '-b:a', '192k',
            str(out),
        ]
    )
