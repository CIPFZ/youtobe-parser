from __future__ import annotations

from faster_whisper import WhisperModel

from app.settings import settings
from app.subtitles import Segment


class FastWhisperTranscriber:
    def __init__(self) -> None:
        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> list[Segment]:
        segments, _info = self.model.transcribe(audio_path, language=settings.whisper_language, vad_filter=True)
        return [Segment(start=s.start, end=s.end, text=s.text) for s in segments]
