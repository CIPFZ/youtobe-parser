"""API routes for the YouTube parser service."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.task_store import task_store
from app.core.worker import analyze_video
from app.core.translator import translate_subtitle
from app.models.schemas import (
    AnalyzeRequest,
    TranslateRequest,
    TaskResponse,
    TaskStatusResponse,
    VideoInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["parser"])


# ── POST /v1/analyze ─────────────────────────────────────

@router.post("/analyze", response_model=TaskResponse)
async def create_analyze_task(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Submit a YouTube URL for analysis.

    Returns a *task_id* immediately – poll ``GET /v1/tasks/{task_id}``
    for progress and results.
    """
    task_id = await task_store.create_task()
    background_tasks.add_task(analyze_video, body.url, task_id)
    logger.info("Created task %s for URL: %s", task_id, body.url)
    return TaskResponse(task_id=task_id, status="pending")


# ── POST /v1/translate ───────────────────────────────────

@router.post("/translate", response_model=TaskResponse)
async def create_translate_task(
    body: TranslateRequest,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Submit an SRT/VTT URL for English-to-Chinese translation to ASS format.

    Returns a *task_id* immediately – poll ``GET /v1/tasks/{task_id}``
    for progress and results. The final ASS content will be in the 'result' field.
    """
    task_id = await task_store.create_task()
    background_tasks.add_task(translate_subtitle, body.path, task_id)
    logger.info("Created translation task %s for path: %s", task_id, body.path)
    return TaskResponse(task_id=task_id, status="pending")


# ── GET /v1/tasks/{task_id} ──────────────────────────────

@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Poll the status of an analysis task."""
    task = await task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    result = task.get("result")
    
    # If it's a dict (VideoInfo), parse it. If it's a string (ASS), keep it as is.
    if isinstance(result, dict):
        result_data = VideoInfo(**result)
    else:
        result_data = result

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task.get("progress", 0.0),
        result=result_data,
        error=task.get("error"),
    )
