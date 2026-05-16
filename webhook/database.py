"""Database layer for persisting webhook events and Devin session logs to Postgres."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS webhook_events (
    id          SERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type  TEXT NOT NULL,
    action      TEXT NOT NULL DEFAULT '',
    repo        TEXT NOT NULL DEFAULT '',
    issue_number INTEGER,
    label       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT '',
    payload     JSONB
);

CREATE TABLE IF NOT EXISTS devin_sessions (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT UNIQUE NOT NULL,
    session_url TEXT NOT NULL DEFAULT '',
    repo        TEXT NOT NULL DEFAULT '',
    issue_number INTEGER,
    issue_title TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'created',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS session_updates (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES devin_sessions(session_id),
    status      TEXT NOT NULL,
    details     JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def init_db(database_url: str) -> None:
    """Initialize the connection pool and create tables if needed."""
    global _pool
    if _pool is not None:
        return
    try:
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
        logger.info("Database initialized successfully")
    except Exception:
        logger.exception("Failed to initialize database — running without persistence")
        _pool = None


async def close_db() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def log_webhook_event(
    event_type: str,
    action: str,
    repo: str,
    issue_number: int | None,
    label: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record an incoming webhook event."""
    if not _pool:
        return
    try:
        await _pool.execute(
            """
            INSERT INTO webhook_events
                (event_type, action, repo, issue_number, label, status, payload)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            event_type,
            action,
            repo,
            issue_number,
            label,
            status,
            json.dumps(payload) if payload else None,
        )
    except Exception:
        logger.exception("Failed to log webhook event")


async def log_session_created(
    session_id: str,
    session_url: str,
    repo: str,
    issue_number: int,
    issue_title: str,
) -> None:
    """Record a newly created Devin session."""
    if not _pool:
        return
    try:
        await _pool.execute(
            """
            INSERT INTO devin_sessions (session_id, session_url, repo, issue_number, issue_title)
            VALUES ($1, $2, $3, $4, $5)
            """,
            session_id,
            session_url,
            repo,
            issue_number,
            issue_title,
        )
    except Exception:
        logger.exception("Failed to log session created")


async def log_session_update(
    session_id: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Record a session status update and update the session record."""
    if not _pool:
        return
    now = _now()
    try:
        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO session_updates (session_id, status, details, recorded_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    session_id,
                    status,
                    json.dumps(details) if details else None,
                    now,
                )
                await conn.execute(
                    """
                    UPDATE devin_sessions SET status = $1, updated_at = $2
                    WHERE session_id = $3
                    """,
                    status,
                    now,
                    session_id,
                )
    except Exception:
        logger.exception("Failed to log session update")


async def get_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent webhook events for the dashboard."""
    if not _pool:
        return []
    try:
        rows = await _pool.fetch(
            "SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT $1",
            limit,
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to fetch recent events")
        return []


async def get_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch Devin sessions for the dashboard."""
    if not _pool:
        return []
    try:
        rows = await _pool.fetch(
            "SELECT * FROM devin_sessions ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to fetch sessions")
        return []


async def get_session_updates(session_id: str) -> list[dict[str, Any]]:
    """Fetch status updates for a specific session."""
    if not _pool:
        return []
    try:
        rows = await _pool.fetch(
            "SELECT * FROM session_updates WHERE session_id = $1 ORDER BY recorded_at DESC",
            session_id,
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to fetch session updates")
        return []
