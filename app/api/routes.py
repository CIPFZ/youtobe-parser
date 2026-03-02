"""API routes for the YouTube parser service."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

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


@router.post("/analyze", response_model=TaskResponse)
async def create_analyze_task(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Submit a YouTube URL for analysis."""
    task_id = await task_store.create_task(task_type="analyze")
    background_tasks.add_task(analyze_video, body.url, task_id)
    logger.info("Created task %s for URL: %s", task_id, body.url)
    return TaskResponse(task_id=task_id, task_type="analyze", status="pending")


@router.post("/translate", response_model=TaskResponse)
async def create_translate_task(
    body: TranslateRequest,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Submit an SRT/VTT URL for English-to-Chinese translation to ASS format."""
    task_id = await task_store.create_task(task_type="translate")
    background_tasks.add_task(translate_subtitle, body.path, task_id)
    logger.info("Created translation task %s for path: %s", task_id, body.path)
    return TaskResponse(task_id=task_id, task_type="translate", status="pending")


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Poll the status of an analysis/translation task."""
    task = await task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    result = task.get("result")
    if task.get("task_type") == "analyze" and isinstance(result, dict):
        result = VideoInfo(**result)

    return TaskStatusResponse(
        task_id=task["task_id"],
        task_type=task.get("task_type", "analyze"),
        status=task["status"],
        progress=float(task.get("progress", 0.0)),
        result=result,
        error=task.get("error"),
    )


@router.get("/translate/download/{task_id}")
async def download_translated_ass(task_id: str) -> FileResponse:
    """Download translated ASS file by translation task id."""
    task = await task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("task_type") != "translate":
        raise HTTPException(status_code=400, detail="Task is not a translation task")
    if task.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Task is not completed")

    result = task.get("result") or {}
    output_path = result.get("output_path") if isinstance(result, dict) else None
    if not output_path:
        raise HTTPException(status_code=404, detail="Output file path missing")
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output file not found")

    filename = os.path.basename(output_path)
    return FileResponse(path=output_path, filename=filename, media_type="text/plain")
