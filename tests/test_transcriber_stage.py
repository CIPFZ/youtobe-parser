from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


class _Seg:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisperModel:
    def __init__(self, model_name: str, device: str, compute_type: str):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: str, language: str, vad_filter: bool):
        return [_Seg(0.0, 1.0, 'hello')], {'language': language}


class _FakeSettings:
    whisper_model = 'base'
    whisper_model_source = 'huggingface'
    whisper_modelscope_repo = ''
    whisper_model_cache_dir = Path('/tmp/runtime-models')
    whisper_download_proxy = ''
    whisper_model_fallback_to_modelscope = True
    whisper_device = 'cpu'
    whisper_compute_type = 'int8'
    whisper_language = 'en'


class TranscriberStageTests(unittest.TestCase):
    def test_transcriber_outputs_segments(self) -> None:
        sys.modules['faster_whisper'] = types.SimpleNamespace(WhisperModel=_FakeWhisperModel)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())
        import app.transcriber as transcriber
        importlib.reload(transcriber)

        worker = transcriber.FastWhisperTranscriber()
        items = worker.transcribe('audio.m4a')

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text, 'hello')

    def test_modelscope_download_flow(self) -> None:
        class _MsSettings(_FakeSettings):
            whisper_model_source = 'modelscope'
            whisper_modelscope_repo = 'demo/repo'

        calls: dict[str, str] = {}

        def _fake_snapshot_download(repo_id: str, cache_dir: str):
            calls['repo_id'] = repo_id
            calls['cache_dir'] = cache_dir
            return '/tmp/ms_model'

        fake_ms_mod = types.SimpleNamespace(snapshot_download=_fake_snapshot_download)
        sys.modules['faster_whisper'] = types.SimpleNamespace(WhisperModel=_FakeWhisperModel)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_MsSettings())
        sys.modules['modelscope'] = types.SimpleNamespace()
        sys.modules['modelscope.hub'] = types.SimpleNamespace()
        sys.modules['modelscope.hub.snapshot_download'] = fake_ms_mod

        import app.transcriber as transcriber
        importlib.reload(transcriber)

        resolved = transcriber._resolve_whisper_model_ref(source='modelscope')
        self.assertEqual(resolved, '/tmp/ms_model')
        self.assertEqual(calls['repo_id'], 'demo/repo')

    def test_local_model_path_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            local = Path(td) / 'model-dir'
            local.mkdir(parents=True, exist_ok=True)

            class _LocalSettings(_FakeSettings):
                whisper_model = str(local)
                whisper_model_source = 'modelscope'
                whisper_modelscope_repo = 'demo/repo'

            sys.modules['faster_whisper'] = types.SimpleNamespace(WhisperModel=_FakeWhisperModel)
            sys.modules['app.settings'] = types.SimpleNamespace(settings=_LocalSettings())

            import app.transcriber as transcriber
            importlib.reload(transcriber)

            resolved = transcriber._resolve_whisper_model_ref(source='modelscope')
            self.assertEqual(resolved, str(local))


    def test_auto_device_selection_cuda_and_cpu(self) -> None:
        sys.modules['faster_whisper'] = types.SimpleNamespace(WhisperModel=_FakeWhisperModel)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())

        # cuda available
        sys.modules['ctranslate2'] = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
        import app.transcriber as transcriber
        importlib.reload(transcriber)
        self.assertEqual(transcriber._auto_select_device('auto'), 'cuda')
        self.assertEqual(transcriber._auto_select_compute_type('auto', 'cuda'), 'float16')

        # cuda unavailable
        sys.modules['ctranslate2'] = types.SimpleNamespace(get_cuda_device_count=lambda: 0)
        importlib.reload(transcriber)
        self.assertEqual(transcriber._auto_select_device('auto'), 'cpu')
        self.assertEqual(transcriber._auto_select_compute_type('auto', 'cpu'), 'int8')

    def test_apply_download_proxy_env(self) -> None:
        sys.modules['faster_whisper'] = types.SimpleNamespace(WhisperModel=_FakeWhisperModel)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())
        import app.transcriber as transcriber
        importlib.reload(transcriber)

        transcriber._apply_download_proxy_env('socks5://127.0.0.1:7897')
        self.assertEqual(os.environ.get('HTTP_PROXY'), 'socks5://127.0.0.1:7897')
        self.assertEqual(os.environ.get('HTTPS_PROXY'), 'socks5://127.0.0.1:7897')


if __name__ == '__main__':
    unittest.main()
