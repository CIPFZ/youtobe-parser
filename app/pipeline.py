from __future__ import annotations

import json
import logging
from pathlib import Path

from app.downloader import download_media
from app.ffmpeg_tools import merge_av_with_ass
from app.settings import settings
from app.subtitles import write_ass, write_srt
from app.transcriber import FastWhisperTranscriber
from app.translator import SubtitleTranslator

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self) -> None:
        self.work_dir = settings.work_dir.resolve()
        self.download_dir = self.work_dir / 'downloads'
        self.subtitle_dir = self.work_dir / 'subtitles'
        self.output_dir = self.work_dir / 'output'
        self.metadata_dir = self.work_dir / settings.metadata_dirname
        for d in (self.download_dir, self.subtitle_dir, self.output_dir, self.metadata_dir):
            d.mkdir(parents=True, exist_ok=True)
        logger.info('Pipeline initialized. work_dir=%s', self.work_dir)

    @staticmethod
    def _artifact_stem(media: dict) -> str:
        metadata = media.get('metadata') or {}
        video_id = str(metadata.get('id') or '').strip()
        return video_id or settings.output_name

    def run(self, url: str) -> Path:
        logger.info('Stage 1/4: parse and download media')
        media = download_media(
            url=url,
            out_dir=self.download_dir,
            cookie_file=settings.cookie_file,
            proxy_url=settings.ytdlp_proxy,
            playlist_strategy=settings.playlist_strategy,
        )
        video_path = Path(media['video_path'])
        audio_path = Path(media['audio_path'])
        stem = self._artifact_stem(media)
        logger.info('Downloaded media. video=%s audio=%s stem=%s', video_path, audio_path, stem)

        metadata_path = self.metadata_dir / f'{stem}.video_info.json'
        metadata_path.write_text(json.dumps(media.get('metadata', {}), ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info('Video metadata written. path=%s', metadata_path)

        logger.info('Stage 2/4: transcribe audio to SRT segments')
        segments = FastWhisperTranscriber().transcribe(str(audio_path))
        srt_path = self.subtitle_dir / f'{stem}.srt'
        write_srt(segments, srt_path)
        logger.info('SRT written. path=%s segments=%d', srt_path, len(segments))

        logger.info('Stage 3/4: translate segments and write ASS')
        translated = SubtitleTranslator().translate(segments)
        ass_path = self.subtitle_dir / f'{stem}.ass'
        write_ass(translated, ass_path)
        logger.info('ASS written. path=%s segments=%d', ass_path, len(translated))

        logger.info('Stage 4/4: merge video + audio + ASS')
        output_path = self.output_dir / f'{settings.output_name}.mp4'
        merge_av_with_ass(video=video_path, audio=audio_path, ass=ass_path, out=output_path)
        logger.info('Merge completed. output=%s', output_path)
        return output_path
