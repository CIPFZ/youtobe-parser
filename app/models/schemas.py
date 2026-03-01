"""Pydantic schemas for request / response models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """POST /v1/analyze body."""
    url: str

class TranslateRequest(BaseModel):
    """POST /v1/translate body."""
    path: str = Field(..., description="Direct URL or local file path to the source SRT or VTT file")


# ── Format / Video Info ──────────────────────────────────

class VideoFormat(BaseModel):
    """A single downloadable format."""
    format_id: str
    ext: str
    resolution: Optional[str] = None
    fps: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    tbr: Optional[float] = None          # total bitrate
    url: Optional[str] = None
    format_note: Optional[str] = None
    category: str = "unknown"            # muxed / video_only / audio_only


class VideoInfo(BaseModel):
    """Parsed metadata for a video."""
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None      # seconds
    channel: Optional[str] = None
    channel_url: Optional[str] = None
    view_count: Optional[int] = None
    upload_date: Optional[str] = None
    webpage_url: str
    formats: list[VideoFormat] = []


# ── Task status ──────────────────────────────────────────

class TaskResponse(BaseModel):
    """Returned after creating a new task."""
    task_id: str
    status: str = "pending"


class TaskStatusResponse(BaseModel):
    """Full task state returned by GET /v1/tasks/{task_id}."""
    task_id: str
    status: str                          # pending | processing | completed | failed
    progress: float = 0.0               # 0‒100
    result: Optional[Any] = None
    error: Optional[str] = None
