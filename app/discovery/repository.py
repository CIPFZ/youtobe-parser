from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.discovery.models import VideoCandidate


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discovered_videos (
                video_id TEXT PRIMARY KEY,
                discovered_at TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                channel_title TEXT NOT NULL,
                published_at TEXT NOT NULL,
                language_hint TEXT NOT NULL,
                duration_sec INTEGER NOT NULL,
                view_count INTEGER NOT NULL,
                comment_count INTEGER NOT NULL,
                like_count INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                score REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'discovered',
                raw_json TEXT NOT NULL
            )
            """
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_discovered_score ON discovered_videos(score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_discovered_at ON discovered_videos(discovered_at DESC)')
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT '',
                finished_at TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                bilingual_video TEXT NOT NULL DEFAULT '',
                dubbed_video TEXT NOT NULL DEFAULT '',
                log_path TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON processing_jobs(status, created_at DESC)')


def upsert_candidates(db_path: Path, items: list[VideoCandidate]) -> int:
    if not items:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO discovered_videos (
                video_id, discovered_at, url, title, description, channel_id, channel_title,
                published_at, language_hint, duration_sec, view_count, comment_count, like_count,
                keyword, score, status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?)
            ON CONFLICT(video_id) DO UPDATE SET
                discovered_at=excluded.discovered_at,
                url=excluded.url,
                title=excluded.title,
                description=excluded.description,
                channel_id=excluded.channel_id,
                channel_title=excluded.channel_title,
                published_at=excluded.published_at,
                language_hint=excluded.language_hint,
                duration_sec=excluded.duration_sec,
                view_count=excluded.view_count,
                comment_count=excluded.comment_count,
                like_count=excluded.like_count,
                keyword=excluded.keyword,
                score=excluded.score,
                raw_json=excluded.raw_json
            """,
            [
                (
                    x.video_id,
                    now,
                    x.url,
                    x.title,
                    x.description,
                    x.channel_id,
                    x.channel_title,
                    x.published_at,
                    x.language_hint,
                    x.duration_sec,
                    x.view_count,
                    x.comment_count,
                    x.like_count,
                    x.keyword,
                    x.score,
                    x.raw_json,
                )
                for x in items
            ],
        )
    return len(items)


def enqueue_processing_job(db_path: Path, video_id: str) -> tuple[bool, str]:
    vid = video_id.strip()
    if not vid:
        return False, 'video_id is empty'
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT video_id, url FROM discovered_videos WHERE video_id=?',
            (vid,),
        ).fetchone()
        if not row:
            return False, f'video_id not found: {vid}'
        exists = conn.execute(
            "SELECT id FROM processing_jobs WHERE video_id=? AND status IN ('pending','running') ORDER BY id DESC LIMIT 1",
            (vid,),
        ).fetchone()
        if exists:
            return False, f'job already queued/running for {vid}'
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO processing_jobs(video_id, url, status, created_at) VALUES (?, ?, ?, ?)',
            (row[0], row[1], 'pending', now),
        )
    return True, f'job queued for {vid}'


def claim_next_job(db_path: Path) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.isolation_level = None
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            "SELECT id, video_id, url FROM processing_jobs WHERE status='pending' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if not row:
            conn.execute('COMMIT')
            return None
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE processing_jobs SET status='running', started_at=? WHERE id=?",
            (now, int(row[0])),
        )
        conn.execute('COMMIT')
    return {'id': int(row[0]), 'video_id': str(row[1]), 'url': str(row[2])}


def complete_job(
    db_path: Path,
    *,
    job_id: int,
    success: bool,
    error: str = '',
    bilingual_video: str = '',
    dubbed_video: str = '',
    log_path: str = '',
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    status = 'success' if success else 'failed'
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE processing_jobs
            SET status=?, finished_at=?, error=?, bilingual_video=?, dubbed_video=?, log_path=?
            WHERE id=?
            """,
            (status, now, error, bilingual_video, dubbed_video, log_path, int(job_id)),
        )


def list_jobs(db_path: Path, limit: int = 30) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, video_id, status, created_at, started_at, finished_at, error, bilingual_video, dubbed_video
            FROM processing_jobs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 300)),),
        )
        return list(cur.fetchall())
