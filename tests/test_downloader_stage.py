from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path


class _FakeYoutubeDL:
    captured_opts: dict | None = None

    def __init__(self, opts: dict):
        _FakeYoutubeDL.captured_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool = True):
        return {'title': 'sample'}

    def prepare_filename(self, info):
        outtmpl = _FakeYoutubeDL.captured_opts['outtmpl']
        return str(outtmpl).replace('%(title).100s', 'sample').replace('%(ext)s', 'mkv')


class DownloaderStageTests(unittest.TestCase):
    def test_proxy_and_cookie_are_wired(self) -> None:
        fake_mod = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        sys.modules['yt_dlp'] = fake_mod

        from app.downloader import download_media  # import after stub

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / 'sample.mp4').write_text('v')
            (out / 'sample.m4a').write_text('a')
            result = download_media(
                url='https://example.com/v',
                out_dir=out,
                cookie_file='/tmp/cookies.txt',
                proxy_url='socks5://127.0.0.1:7897',
            )

            self.assertEqual(result['title'], 'sample')
            self.assertTrue(str(result['video_path']).endswith('.mp4'))
            self.assertTrue(str(result['audio_path']).endswith('.m4a'))
            self.assertEqual(_FakeYoutubeDL.captured_opts['cookiefile'], '/tmp/cookies.txt')
            self.assertEqual(_FakeYoutubeDL.captured_opts['proxy'], 'socks5://127.0.0.1:7897')


if __name__ == '__main__':
    unittest.main()
