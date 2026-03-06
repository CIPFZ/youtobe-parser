from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.ffmpeg_tools import run_ffmpeg
from app.settings import settings
from app.transcriber import FastWhisperTranscriber


class TranscriberStageTests(unittest.TestCase):
    def test_real_transcriber_on_synthetic_audio(self) -> None:
        if os.getenv('RUN_REAL_TRANSCRIBER', '').lower() not in {'1', 'true', 'yes'}:
            self.skipTest('Set RUN_REAL_TRANSCRIBER=1 to run real faster-whisper transcription test.')

        old_model = settings.whisper_model
        old_source = settings.whisper_model_source
        old_local = settings.whisper_download_to_local
        old_lang = settings.whisper_language
        try:
            settings.whisper_model = os.getenv('TEST_WHISPER_MODEL', 'tiny')
            settings.whisper_model_source = os.getenv('TEST_WHISPER_MODEL_SOURCE', 'huggingface')
            settings.whisper_download_to_local = False
            settings.whisper_language = os.getenv('TEST_WHISPER_LANGUAGE', 'en')

            with tempfile.TemporaryDirectory(prefix='transcriber-stage-') as td:
                audio = Path(td) / 'speech.wav'
                run_ffmpeg(['-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=16000', '-t', '2', '-ac', '1', str(audio)])

                worker = FastWhisperTranscriber()
                items = worker.transcribe(str(audio))
                self.assertGreaterEqual(len(items), 1)
                self.assertTrue(all(hasattr(seg, 'text') for seg in items))
        finally:
            settings.whisper_model = old_model
            settings.whisper_model_source = old_source
            settings.whisper_download_to_local = old_local
            settings.whisper_language = old_lang


if __name__ == '__main__':
    unittest.main()
