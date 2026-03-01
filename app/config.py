"""Application settings loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration – reads from .env automatically."""

    # Network / Proxy
    global_proxy: str = Field(default="", description="Global proxy URL (e.g. socks5://127.0.0.1:1080)")

    # PO Token Provider (Docker HTTP service)
    po_token_server: str = Field(default="http://localhost:4416", description="PO Token provider URL")

    # LLM Translation API Setup
    llm_api_key: str = Field(default="ak_1Wa63Y8MS3Ux3a08ge5oY9GL7242x", description="OpenAI format API key")
    llm_base_url: str = Field(default="https://api.longcat.chat/openai/v1", description="OpenAI base URL")
    llm_model: str = Field(default="LongCat-Flash-Chat", description="LLM default model")

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
