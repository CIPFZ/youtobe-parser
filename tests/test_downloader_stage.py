from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path


class _FakeYoutubeDL:
    captured_opts: dict | None = None
    captured_url: str | None = None

    def __init__(self, opts: dict):
        _FakeYoutubeDL.captured_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool = True):
        _FakeYoutubeDL.captured_url = url
        return {
            'id': 'abc123',
            'title': 'sample',
            'uploader': 'tester',
            'duration': 120,
            'webpage_url': 'https://youtube.com/watch?v=abc123',
            'extractor': 'youtube',
        }

    def prepare_filename(self, info):
        outtmpl = _FakeYoutubeDL.captured_opts['outtmpl']
        return str(outtmpl).replace('%(title).100s', 'sample').replace('%(ext)s', 'mkv')


class DownloaderStageTests(unittest.TestCase):
    def test_proxy_cookie_and_playlist_normalization(self) -> None:
        fake_mod = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        sys.modules['yt_dlp'] = fake_mod

        from app.downloader import download_media

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / 'sample.mp4').write_text('v')
            (out / 'sample.m4a').write_text('a')
            source_url = 'https://www.youtube.com/watch?v=DFdh8BrzJ_Y&list=RDDFdh8BrzJ_Y&start_radio=1'
            result = download_media(
                url=source_url,
                out_dir=out,
                cookie_file='/tmp/cookies.txt',
                proxy_url='socks5://127.0.0.1:7897',
                playlist_strategy='first',
            )

            self.assertEqual(result['title'], 'sample')
            self.assertTrue(str(result['video_path']).endswith('.mp4'))
            self.assertTrue(str(result['audio_path']).endswith('.m4a'))
            self.assertEqual(_FakeYoutubeDL.captured_opts['cookiefile'], '/tmp/cookies.txt')
            self.assertEqual(_FakeYoutubeDL.captured_opts['proxy'], 'socks5://127.0.0.1:7897')
            self.assertEqual(_FakeYoutubeDL.captured_opts['noplaylist'], True)
            self.assertEqual(_FakeYoutubeDL.captured_url, 'https://www.youtube.com/watch?v=DFdh8BrzJ_Y')
            self.assertEqual(result['metadata']['source_url'], source_url)
            self.assertEqual(result['metadata']['playlist_strategy'], 'first')


if __name__ == '__main__':
    unittest.main()
