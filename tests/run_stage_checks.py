#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STAGES = [
    'tests.test_downloader_stage',
    'tests.test_transcriber_stage',
    'tests.test_translator_stage',
    'tests.test_subtitles_stage',
    'tests.test_ffmpeg_stage',
    'tests.test_pipeline_e2e',
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    for stage in STAGES:
        print(f'===== running {stage} =====')
        rc = subprocess.call([sys.executable, '-m', 'unittest', '-v', stage], cwd=repo_root)
        if rc != 0:
            return rc
    print('all stage checks passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
