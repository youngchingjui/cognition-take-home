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
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pr_created_at TIMESTAMPTZ
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
    has_prs = bool(
        details and details.get("pull_requests")
    )
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
                if has_prs:
                    await conn.execute(
                        """
                        UPDATE devin_sessions
                        SET pr_created_at = $1
                        WHERE session_id = $2 AND pr_created_at IS NULL
                        """,
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


async def get_event_by_id(event_id: int) -> dict[str, Any] | None:
    """Fetch a single webhook event by ID (including payload)."""
    if not _pool:
        return None
    try:
        row = await _pool.fetchrow(
            "SELECT * FROM webhook_events WHERE id = $1",
            event_id,
        )
        return dict(row) if row else None
    except Exception:
        logger.exception("Failed to fetch event %s", event_id)
        return None


async def get_stats() -> dict[str, Any]:
    """Return aggregate statistics for the dashboard overview."""
    empty_stats: dict[str, Any] = {
        "total_events": 0,
        "processed_events": 0,
        "ignored_events": 0,
        "total_sessions": 0,
        "active_sessions": 0,
        "completed_sessions": 0,
        "errored_sessions": 0,
        "avg_time_to_pr_seconds": None,
        "repos": [],
    }
    if not _pool:
        return empty_stats
    try:
        async with _pool.acquire() as conn:
            ev_total = await conn.fetchval("SELECT COUNT(*) FROM webhook_events")
            ev_processed = await conn.fetchval(
                "SELECT COUNT(*) FROM webhook_events WHERE status = 'session_created'"
            )
            ev_ignored = await conn.fetchval(
                "SELECT COUNT(*) FROM webhook_events WHERE status = 'ignored'"
            )
            s_total = await conn.fetchval("SELECT COUNT(*) FROM devin_sessions")
            s_active = await conn.fetchval(
                "SELECT COUNT(*) FROM devin_sessions "
                "WHERE status NOT IN ('finished', 'error', 'stopped', 'timed_out')"
            )
            s_completed = await conn.fetchval(
                "SELECT COUNT(*) FROM devin_sessions WHERE status = 'finished'"
            )
            s_errored = await conn.fetchval(
                "SELECT COUNT(*) FROM devin_sessions "
                "WHERE status IN ('error', 'stopped', 'timed_out')"
            )
            avg_seconds = await conn.fetchval(
                "SELECT AVG(EXTRACT(EPOCH FROM (pr_created_at - created_at))) "
                "FROM devin_sessions WHERE pr_created_at IS NOT NULL"
            )
            repo_rows = await conn.fetch(
                "SELECT DISTINCT repo FROM devin_sessions WHERE repo != '' ORDER BY repo"
            )
            return {
                "total_events": ev_total or 0,
                "processed_events": ev_processed or 0,
                "ignored_events": ev_ignored or 0,
                "total_sessions": s_total or 0,
                "active_sessions": s_active or 0,
                "completed_sessions": s_completed or 0,
                "errored_sessions": s_errored or 0,
                "avg_time_to_pr_seconds": round(float(avg_seconds)) if avg_seconds else None,
                "repos": [r["repo"] for r in repo_rows],
            }
    except Exception:
        logger.exception("Failed to fetch stats")
        return empty_stats
