from __future__ import annotations

import http.server
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from app.downloader import download_media
from app.ffmpeg_tools import run_ffmpeg
from app.settings import settings


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class DownloaderStageTests(unittest.TestCase):
    def test_download_media_from_real_http_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix='downloader-stage-') as td:
            root = Path(td)
            source = root / 'source.mp4'
            run_ffmpeg(['-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=24', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)])

            handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=str(root), **kwargs)
            with _ReusableTCPServer(('127.0.0.1', 0), handler) as httpd:
                port = httpd.server_address[1]
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    out_dir = root / 'downloads'
                    url = f'http://127.0.0.1:{port}/source.mp4'

                    old_vfmt = settings.ytdlp_video_format
                    old_afmt = settings.ytdlp_audio_format
                    settings.ytdlp_video_format = 'best'
                    settings.ytdlp_audio_format = 'bestaudio/best'
                    try:
                        result = download_media(url=url, out_dir=out_dir)
                    finally:
                        settings.ytdlp_video_format = old_vfmt
                        settings.ytdlp_audio_format = old_afmt

                    self.assertTrue(Path(result['video_path']).exists())
                    self.assertTrue(Path(result['audio_path']).exists())
                    self.assertIn('id', result['metadata'])
                    self.assertEqual(result['metadata']['source_url'], url)
                finally:
                    httpd.shutdown()
                    thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
