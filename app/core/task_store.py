"""In-memory task store (will be replaced by Redis in Phase 2)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional


class TaskStore:
    """Thread-safe async in-memory task storage."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_task(self) -> str:
        """Create a new task in *pending* state which returns its ID."""
        task_id = uuid.uuid4().hex[:12]
        async with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "pending",
                "progress": 0.0,
                "result": None,
                "error": None,
            }
        return task_id

    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def update_task(self, task_id: str, **kwargs: Any) -> None:
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)


# Singleton
task_store = TaskStore()
