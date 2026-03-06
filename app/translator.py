from __future__ import annotations

import logging

from openai import OpenAI

from app.settings import settings
from app.subtitles import Segment

logger = logging.getLogger(__name__)


class SubtitleTranslator:
    def __init__(self) -> None:
        self.enabled = bool(settings.openai_api_key)
        self.client = (
            OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url.rstrip('/'))
            if self.enabled
            else None
        )
        if self.enabled:
            logger.info('Translator enabled. model=%s target_language=%s', settings.openai_model, settings.target_language)
        else:
            logger.warning('Translator disabled because OPENAI_API_KEY is empty. subtitles will keep original text.')

    def translate(self, segments: list[Segment]) -> list[Segment]:
        if not self.enabled:
            return segments

        out: list[Segment] = []
        logger.info('Translation started. segments=%d', len(segments))
        for idx, seg in enumerate(segments, start=1):
            rsp = self.client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.2,
                messages=[
                    {'role': 'system', 'content': f'You are a subtitle translator. Translate to {settings.target_language} only.'},
                    {'role': 'user', 'content': seg.text.strip()},
                ],
            )
            translated = rsp.choices[0].message.content or seg.text
            out.append(Segment(start=seg.start, end=seg.end, text=translated.strip()))
            if idx % 20 == 0:
                logger.info('Translation progress: %d/%d', idx, len(segments))

        logger.info('Translation completed. segments=%d', len(out))
        return out
