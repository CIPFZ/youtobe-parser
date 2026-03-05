from __future__ import annotations

import importlib
import sys
import types
import unittest


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


if __name__ == '__main__':
    unittest.main()
