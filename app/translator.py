from __future__ import annotations

from openai import OpenAI

from app.settings import settings
from app.subtitles import Segment


class SubtitleTranslator:
    def __init__(self) -> None:
        self.enabled = bool(settings.openai_api_key)
        self.client = (
            OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url.rstrip('/'))
            if self.enabled
            else None
        )

    def translate(self, segments: list[Segment]) -> list[Segment]:
        if not self.enabled:
            return segments

        out: list[Segment] = []
        for seg in segments:
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
        return out
