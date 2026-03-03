"""Application settings loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration – reads from .env automatically."""

    # Network / Proxy
    global_proxy: str = Field(default="", description="Global proxy URL (e.g. socks5://127.0.0.1:1080)")

    # LLM Translation API Setup (OpenAI-compatible)
    openai_api_key: str = Field(default="", description="OpenAI-compatible API key")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI-compatible base URL")
    openai_model: str = Field(default="gpt-4o-mini", description="LLM model used for subtitle translation")

    # YouTube auth/cookies
    youtube_cookie_file: str = Field(default="", description="Optional Netscape cookie file path for yt-dlp YouTube requests")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton – import this everywhere
settings = Settings()