from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path


class _FakeYoutubeDL:
    captured_opts_list: list[dict] = []
    captured_urls: list[str] = []

    def __init__(self, opts: dict):
        self.opts = opts
        _FakeYoutubeDL.captured_opts_list.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool = True):
        _FakeYoutubeDL.captured_urls.append(url)
        return {
            'id': 'abc123',
            'title': 'sample',
            'uploader': 'tester',
            'duration': 120,
            'webpage_url': 'https://youtube.com/watch?v=abc123',
            'extractor': 'youtube',
        }


class DownloaderStageTests(unittest.TestCase):
    def test_id_filename_best_stream_selection(self) -> None:
        fake_mod = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        sys.modules['yt_dlp'] = fake_mod

        from app.downloader import download_media

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / 'abc123.mp4').write_text('v')
            (out / 'abc123.m4a').write_text('a')
            source_url = 'https://www.youtube.com/watch?v=DFdh8BrzJ_Y&list=RDDFdh8BrzJ_Y&start_radio=1'
            result = download_media(
                url=source_url,
                out_dir=out,
                cookie_file='/tmp/cookies.txt',
                proxy_url='socks5://127.0.0.1:7897',
                playlist_strategy='first',
            )

            self.assertEqual(result['title'], 'sample')
            self.assertEqual(result['video_path'], out / 'abc123.mp4')
            self.assertEqual(result['audio_path'], out / 'abc123.m4a')

            self.assertEqual(len(_FakeYoutubeDL.captured_opts_list), 2)
            video_opts, audio_opts = _FakeYoutubeDL.captured_opts_list

            self.assertEqual(video_opts['outtmpl'], str(out / '%(id)s.%(ext)s'))
            self.assertEqual(audio_opts['outtmpl'], str(out / '%(id)s.%(ext)s'))
            self.assertEqual(video_opts['format'], 'bestvideo[ext=mp4]/bestvideo')
            self.assertEqual(audio_opts['format'], 'bestaudio[ext=m4a]/bestaudio')
            self.assertEqual(video_opts['cookiefile'], '/tmp/cookies.txt')
            self.assertEqual(audio_opts['proxy'], 'socks5://127.0.0.1:7897')

            self.assertEqual(_FakeYoutubeDL.captured_urls[0], 'https://www.youtube.com/watch?v=DFdh8BrzJ_Y')
            self.assertEqual(result['metadata']['id'], 'abc123')
            self.assertEqual(result['metadata']['source_url'], source_url)


if __name__ == '__main__':
    unittest.main()
