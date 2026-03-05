from __future__ import annotations

import logging

from faster_whisper import WhisperModel

from app.settings import settings
from app.subtitles import Segment

logger = logging.getLogger(__name__)


class FastWhisperTranscriber:
    def __init__(self) -> None:
        logger.info(
            'Loading faster-whisper model. model=%s device=%s compute_type=%s',
            settings.whisper_model,
            settings.whisper_device,
            settings.whisper_compute_type,
        )
        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> list[Segment]:
        logger.info('Transcription started. audio=%s language=%s', audio_path, settings.whisper_language)
        segments, _info = self.model.transcribe(audio_path, language=settings.whisper_language, vad_filter=True)
        result = [Segment(start=s.start, end=s.end, text=s.text) for s in segments]
        logger.info('Transcription completed. segments=%d', len(result))
        return result
