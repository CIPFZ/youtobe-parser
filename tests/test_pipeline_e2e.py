from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


class _FakeSettings:
    work_dir = Path('.')
    output_name = 'final_output'
    metadata_dirname = 'metadata'
    cookie_file = ''
    ytdlp_proxy = ''
    playlist_strategy = 'first'


class PipelineE2ETests(unittest.TestCase):
    def test_pipeline_run_with_stage_mocks(self) -> None:
        sys.modules['yt_dlp'] = types.SimpleNamespace(YoutubeDL=object)
        sys.modules['faster_whisper'] = types.SimpleNamespace(WhisperModel=object)
        sys.modules['openai'] = types.SimpleNamespace(OpenAI=object)
        sys.modules['imageio_ffmpeg'] = types.SimpleNamespace(get_ffmpeg_exe=lambda: '/tmp/ffmpeg')
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())

        import app.pipeline as pipeline
        from app.subtitles import Segment
        importlib.reload(pipeline)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            video = root / 'v.mp4'
            audio = root / 'a.m4a'
            video.write_text('video')
            audio.write_text('audio')

            def fake_merge(video: Path, audio: Path, ass: Path, out: Path) -> None:
                out.write_text('final')

            with mock.patch('app.pipeline.settings.work_dir', root), \
                mock.patch(
                    'app.pipeline.download_media',
                    return_value={
                        'video_path': video,
                        'audio_path': audio,
                        'metadata': {'id': 'abc123', 'title': 'sample'},
                    },
                ), \
                mock.patch('app.pipeline.FastWhisperTranscriber') as fw, \
                mock.patch('app.pipeline.SubtitleTranslator') as tr, \
                mock.patch('app.pipeline.merge_av_with_ass', side_effect=fake_merge):

                fw.return_value.transcribe.return_value = [Segment(0, 1, 'hello')]
                tr.return_value.translate.return_value = [Segment(0, 1, '你好')]

                out = pipeline.Pipeline().run('https://example.com/video')

                self.assertTrue(out.exists())
                self.assertTrue((root / 'subtitles' / 'abc123.srt').exists())
                self.assertTrue((root / 'subtitles' / 'abc123.ass').exists())
                metadata_path = root / 'metadata' / 'abc123.video_info.json'
                self.assertTrue(metadata_path.exists())
                loaded = json.loads(metadata_path.read_text(encoding='utf-8'))
                self.assertEqual(loaded['id'], 'abc123')


if __name__ == '__main__':
    unittest.main()
