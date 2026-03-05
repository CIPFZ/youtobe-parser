from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


def ffmpeg_bin() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str]) -> None:
    cmd = [ffmpeg_bin(), '-y', *args]
    subprocess.run(cmd, check=True)


def merge_av_with_ass(video: Path, audio: Path, ass: Path, out: Path) -> None:
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
