"""Application settings loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration – reads from .env automatically."""

    # Network / Proxy
    global_proxy: str = Field(default="", description="Global proxy URL (e.g. socks5://127.0.0.1:1080)")

    # PO Token Provider (Docker HTTP service)
    po_token_server: str = Field(default="http://localhost:4416", description="PO Token provider URL")

    # LLM Translation API Setup (OpenAI-compatible)
    openai_api_key: str = Field(default="", description="OpenAI-compatible API key")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI-compatible base URL")
    openai_model: str = Field(default="gpt-4o-mini", description="LLM model used for subtitle translation")

    # Task Store
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL for task status storage")
    task_ttl_seconds: int = Field(default=86400, description="How long completed/failed task metadata is kept in Redis")

    # Concurrency
    max_concurrent_downloads: int = Field(default=3, description="Max simultaneous yt-dlp tasks")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton – import this everywhere
settings = Settings()
