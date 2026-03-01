"""Task storage with Redis-first implementation and in-memory fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover - optional dependency in local dev
    Redis = None

from app.config import settings

logger = logging.getLogger(__name__)


class BaseTaskStore:
    async def create_task(self, *, task_type: str) -> str:
        raise NotImplementedError

    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    async def update_task(self, task_id: str, **kwargs: Any) -> None:
        raise NotImplementedError


class InMemoryTaskStore(BaseTaskStore):
    """Thread-safe async in-memory task storage (fallback mode)."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, *, task_type: str) -> str:
        task_id = uuid.uuid4().hex[:12]
        async with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "task_type": task_type,
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


class RedisTaskStore(BaseTaskStore):
    """Redis-backed task store suitable for multi-instance deployment."""

    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        if Redis is None:
            raise RuntimeError("redis package is not installed")
        self._redis: Redis = Redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _task_key(task_id: str) -> str:
        return f"task:{task_id}"

    async def create_task(self, *, task_type: str) -> str:
        task_id = uuid.uuid4().hex[:12]
        key = self._task_key(task_id)
        payload = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "pending",
            "progress": 0.0,
            "result": None,
            "error": None,
        }
        await self._redis.set(key, json.dumps(payload), ex=self._ttl_seconds)
        return task_id

    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(self._task_key(task_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def update_task(self, task_id: str, **kwargs: Any) -> None:
        key = self._task_key(task_id)
        raw = await self._redis.get(key)
        if raw is None:
            return
        data = json.loads(raw)
        data.update(kwargs)
        # refresh TTL for each status update
        await self._redis.set(key, json.dumps(data), ex=self._ttl_seconds)


async def _build_task_store() -> BaseTaskStore:
    """Build Redis task store; fallback to in-memory when Redis is unavailable."""
    try:
        store = RedisTaskStore(settings.redis_url, settings.task_ttl_seconds)
        await store._redis.ping()
        logger.info("TaskStore initialized with Redis: %s", settings.redis_url)
        return store
    except Exception as exc:
        logger.warning("Redis unavailable (%s), fallback to in-memory task store", exc)
        return InMemoryTaskStore()


task_store: BaseTaskStore = asyncio.run(_build_task_store())
