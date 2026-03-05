from __future__ import annotations

from pathlib import Path

from app.downloader import download_media
from app.ffmpeg_tools import merge_av_with_ass
from app.settings import settings
from app.subtitles import write_ass, write_srt
from app.transcriber import FastWhisperTranscriber
from app.translator import SubtitleTranslator


class Pipeline:
    def __init__(self) -> None:
        self.work_dir = settings.work_dir.resolve()
        self.download_dir = self.work_dir / 'downloads'
        self.subtitle_dir = self.work_dir / 'subtitles'
        self.output_dir = self.work_dir / 'output'
        for d in (self.download_dir, self.subtitle_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

    def run(self, url: str) -> Path:
        print('1) 解析链接并下载音频+视频...')
        media = download_media(url=url, out_dir=self.download_dir, cookie_file=settings.cookie_file)
        video_path = Path(media['video_path'])
        audio_path = Path(media['audio_path'])

        print('2) fast-whisper 转写 SRT...')
        segments = FastWhisperTranscriber().transcribe(str(audio_path))
        srt_path = self.subtitle_dir / f"{settings.output_name}.srt"
        write_srt(segments, srt_path)

        print('3) 翻译 SRT 并生成 ASS...')
        translated = SubtitleTranslator().translate(segments)
        ass_path = self.subtitle_dir / f"{settings.output_name}.ass"
        write_ass(translated, ass_path)

        print('4) 合并 ASS + 音频 + 视频...')
        output_path = self.output_dir / f'{settings.output_name}.mp4'
        merge_av_with_ass(video=video_path, audio=audio_path, ass=ass_path, out=output_path)
        return output_path
