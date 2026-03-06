from __future__ import annotations

import logging
from pathlib import Path

from faster_whisper import WhisperModel

from app.settings import settings
from app.subtitles import Segment

logger = logging.getLogger(__name__)


def _resolve_whisper_model_ref() -> str:
    """Resolve faster-whisper model ref/path based on configured source."""
    source = settings.whisper_model_source.strip().lower()
    model_ref = settings.whisper_model.strip()

    # local path always wins
    if model_ref and Path(model_ref).expanduser().exists():
        local_path = str(Path(model_ref).expanduser())
        logger.info('Using local whisper model path: %s', local_path)
        return local_path

    if source == 'huggingface':
        return model_ref

    if source == 'modelscope':
        repo_id = settings.whisper_modelscope_repo.strip()
        if not repo_id:
            raise ValueError('WHISPER_MODELSCOPE_REPO is required when WHISPER_MODEL_SOURCE=modelscope')
        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except Exception as exc:
            raise RuntimeError(
                'ModelScope support requires `modelscope` package. Please install it first.'
            ) from exc

        cache_dir = settings.whisper_model_cache_dir.expanduser().resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info('Downloading whisper model from ModelScope. repo=%s cache_dir=%s', repo_id, cache_dir)
        local_dir = snapshot_download(repo_id, cache_dir=str(cache_dir))
        logger.info('ModelScope model ready: %s', local_dir)
        return str(local_dir)

    raise ValueError('WHISPER_MODEL_SOURCE must be one of: huggingface, modelscope')


class FastWhisperTranscriber:
    def __init__(self) -> None:
        resolved_model = _resolve_whisper_model_ref()
        logger.info(
            'Loading faster-whisper model. source=%s model_ref=%s resolved=%s device=%s compute_type=%s',
            settings.whisper_model_source,
            settings.whisper_model,
            resolved_model,
            settings.whisper_device,
            settings.whisper_compute_type,
        )
        self.model = WhisperModel(
            resolved_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> list[Segment]:
        logger.info('Transcription started. audio=%s language=%s', audio_path, settings.whisper_language)
        segments, _info = self.model.transcribe(audio_path, language=settings.whisper_language, vad_filter=True)
        result = [Segment(start=s.start, end=s.end, text=s.text) for s in segments]
        logger.info('Transcription completed. segments=%d', len(result))
        return result
