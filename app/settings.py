from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    work_dir: Path = Field(default=Path('runtime'))
    source_url: str = Field(default='')
    output_name: str = Field(default='final_output')
    metadata_dirname: str = Field(default='metadata')

    # yt-dlp
    cookie_file: str = Field(default='')
    ytdlp_proxy: str = Field(default='')
    playlist_strategy: str = Field(default='first')

    # ffmpeg
    ffmpeg_path: str = Field(default='')


    # logging
    log_level: str = Field(default='INFO')
    log_file: Path = Field(default=Path('runtime/logs/pipeline.log'))

    # whisper
    whisper_model: str = Field(default='large-v3')
    whisper_device: str = Field(default='auto')
    whisper_compute_type: str = Field(default='auto')
    whisper_language: str = Field(default='en')

    # translation (OpenAI-compatible)
    openai_api_key: str = Field(default='')
    openai_base_url: str = Field(default='https://api.openai.com/v1')
    openai_model: str = Field(default='gpt-4o-mini')
    target_language: str = Field(default='zh-CN')


settings = Settings()
