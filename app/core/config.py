import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "YouTube URL Parse Service"
    API_V1_STR: str = "/api/v1"

    # Proxy Configuration Example: "http://user:pass@proxy1:port,http://proxy2:port"
    PROXY_LIST: str = os.getenv("PROXY_LIST", "")

    # FFmpeg location (for yt-dlp format probing)
    FFMPEG_LOCATION: str = os.getenv("FFMPEG_LOCATION", "./ffmpeg-8.0.1/bin")

    class Config:
        case_sensitive = True

settings = Settings()
