import asyncio
import hashlib
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from webhook.config import settings
from webhook.dashboard import DASHBOARD_HTML
from webhook.database import (
    close_db,
    get_event_by_id,
    get_recent_events,
    get_session_updates,
    get_sessions,
    get_stats,
    init_db,
    log_session_created,
    log_session_update,
    log_webhook_event,
)
from webhook.devin_client import DevinAPIError, create_session, get_session
from webhook.github_client import post_issue_comment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Track active polling tasks so we can cancel on shutdown
_active_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    if settings.database_url:
        await init_db(settings.database_url)
    yield
    # Cancel all background polling tasks on shutdown
    for task in _active_tasks:
        task.cancel()
    if _active_tasks:
        await asyncio.gather(*_active_tasks, return_exceptions=True)
    _active_tasks.clear()
    await close_db()


app = FastAPI(
    title="Devin Issue Remediation Webhook",
    description=(
        "Receives GitHub webhook events and triggers Devin sessions "
        "to remediate issues labeled 'devin-fix'."
    ),
    lifespan=lifespan,
)


def _verify_signature(payload: bytes, signature: str | None) -> None:
    """Verify the GitHub webhook HMAC-SHA256 signature."""
    secret = settings.github_webhook_secret
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET is not set — skipping signature verification")
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _build_prompt(issue: dict, repo_full_name: str) -> str:
    """Build the Devin session prompt from the GitHub issue."""
    title = issue.get("title", "")
    body = issue.get("body", "") or ""
    number = issue.get("number", "")
    return (
        f"Fix the following GitHub issue in the repository {repo_full_name}.\n\n"
        f"Issue #{number}: {title}\n\n"
        f"{body}\n\n"
        f"Please:\n"
        f"1. Clone the repository https://github.com/{repo_full_name}\n"
        f"2. Understand the issue and identify the root cause\n"
        f"3. Implement a fix\n"
        f"4. Create a pull request that references this issue (Fixes #{number})\n"
    )


async def _poll_and_update(
    session_id: str,
    session_url: str,
    owner: str,
    repo: str,
    issue_number: int,
) -> None:
    """Poll the Devin session until it completes, then update the GitHub issue."""
    elapsed = 0
    terminal_statuses = {"stopped", "error", "finished", "timed_out"}
    try:
        while elapsed < settings.poll_timeout_seconds:
            await asyncio.sleep(settings.poll_interval_seconds)
            elapsed += settings.poll_interval_seconds
            try:
                session = await get_session(session_id)
            except Exception:
                logger.exception("Error polling session %s", session_id)
                continue

            status = session.get("status", "unknown")
            logger.info("Session %s status: %s", session_id, status)

            if status not in terminal_statuses:
                await log_session_update(session_id, status)
                continue

            status_label = "completed" if status == "finished" else status
            pull_requests = (
                session.get("pull_requests")
                or session.get("structured_output", {}).get("pull_requests")
                or []
            )
            pr_text = ""
            if pull_requests:
                pr_links = [f"- {pr.get('url', pr)}" for pr in pull_requests]
                pr_text = "\n\n**Pull Requests:**\n" + "\n".join(pr_links)

            body = (
                f"🤖 **Devin session {status_label}**\n\n"
                f"Session: {session_url}\n"
                f"Status: `{status}`"
                f"{pr_text}"
            )
            await post_issue_comment(owner, repo, issue_number, body)

            await log_session_update(
                session_id,
                status,
                {"pull_requests": pull_requests} if pull_requests else None,
            )
            return

        # Timeout
        await post_issue_comment(
            owner,
            repo,
            issue_number,
            f"⏱️ **Devin session timed out** (polling limit reached)\n\n"
            f"Session: {session_url}\n"
            f"Check the session for the latest status.",
        )
        await log_session_update(session_id, "timed_out")
    except asyncio.CancelledError:
        logger.info("Polling task for session %s cancelled", session_id)
    except Exception:
        logger.exception("Unexpected error in polling task for session %s", session_id)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "active_sessions": len(_active_tasks)}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, Any]:
    """Handle incoming GitHub webhook events."""
    payload = await request.body()
    _verify_signature(payload, x_hub_signature_256)

    if x_github_event != "issues":
        await log_webhook_event(
            event_type=x_github_event or "unknown",
            action="",
            repo="",
            issue_number=None,
            label="",
            status="ignored",
        )
        return {"status": "ignored", "reason": f"event type '{x_github_event}' not handled"}

    data = await request.json()
    action = data.get("action")

    if action != "labeled":
        await log_webhook_event(
            event_type="issues",
            action=action or "",
            repo=data.get("repository", {}).get("full_name", ""),
            issue_number=data.get("issue", {}).get("number"),
            label="",
            status="ignored",
        )
        return {"status": "ignored", "reason": f"action '{action}' not handled"}

    label = data.get("label", {})
    if label.get("name") != "devin-fix":
        repo_full = data.get("repository", {}).get("full_name", "")
        await log_webhook_event(
            event_type="issues",
            action="labeled",
            repo=repo_full,
            issue_number=data.get("issue", {}).get("number"),
            label=label.get("name", ""),
            status="ignored",
        )
        return {
            "status": "ignored",
            "reason": f"label '{label.get('name')}' is not 'devin-fix'",
        }

    issue = data.get("issue", {})
    repo_data = data.get("repository", {})
    repo_full_name = repo_data.get("full_name", "")
    owner, repo = repo_full_name.split("/", 1) if "/" in repo_full_name else ("", "")
    issue_number = issue.get("number", 0)

    logger.info(
        "Received devin-fix event for %s#%d: %s",
        repo_full_name,
        issue_number,
        issue.get("title"),
    )

    await log_webhook_event(
        event_type="issues",
        action="labeled",
        repo=repo_full_name,
        issue_number=issue_number,
        label="devin-fix",
        status="session_created",
        payload=data,
    )

    # Create Devin session
    prompt = _build_prompt(issue, repo_full_name)
    try:
        session_resp = await create_session(prompt)
    except DevinAPIError as exc:
        logger.error("Devin API error for %s#%d: %s", repo_full_name, issue_number, exc.detail)
        raise HTTPException(status_code=502, detail=exc.detail)
    except Exception:
        logger.exception("Failed to create Devin session for %s#%d", repo_full_name, issue_number)
        raise HTTPException(status_code=502, detail="Failed to create Devin session")

    session_id = session_resp.get("session_id", "")
    session_url = session_resp.get("url", f"https://app.devin.ai/sessions/{session_id}")

    await log_session_created(
        session_id=session_id,
        session_url=session_url,
        repo=repo_full_name,
        issue_number=issue_number,
        issue_title=issue.get("title", ""),
    )

    # Post initial comment on the issue
    comment_body = (
        f"🤖 **Devin is working on this issue**\n\n"
        f"A Devin session has been started to remediate this issue.\n\n"
        f"**Session:** {session_url}\n"
        f"**Status:** `running`\n\n"
        f"I'll post an update here when the session completes."
    )
    try:
        await post_issue_comment(owner, repo, issue_number, comment_body)
    except Exception:
        logger.exception("Failed to post initial comment on %s#%d", repo_full_name, issue_number)

    # Start background polling
    task = asyncio.create_task(_poll_and_update(session_id, session_url, owner, repo, issue_number))
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)

    return {
        "status": "session_created",
        "session_id": session_id,
        "session_url": session_url,
        "issue": f"{repo_full_name}#{issue_number}",
    }


# ---------------------------------------------------------------------------
# Dashboard API endpoints
# ---------------------------------------------------------------------------


def _serialise_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert datetime values to ISO-8601 strings for JSON serialisation."""
    for row in rows:
        for key, val in row.items():
            if hasattr(val, "isoformat"):
                row[key] = val.isoformat()
    return rows


@app.get("/api/stats")
async def api_stats() -> dict[str, Any]:
    """Return aggregate statistics for the dashboard overview."""
    return await get_stats()


@app.get("/api/events")
async def api_events() -> list[dict[str, Any]]:
    """Return recent webhook events as JSON (payload excluded for list view)."""
    events = await get_recent_events()
    for e in events:
        e.pop("payload", None)
    return _serialise_rows(events)


@app.get("/api/events/{event_id}")
async def api_event_detail(event_id: int) -> dict[str, Any]:
    """Return a single webhook event with its full payload."""
    event = await get_event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    for key, val in event.items():
        if hasattr(val, "isoformat"):
            event[key] = val.isoformat()
    return event


@app.get("/api/sessions")
async def api_sessions() -> list[dict[str, Any]]:
    """Return Devin sessions as JSON."""
    return _serialise_rows(await get_sessions())


@app.get("/api/sessions/{session_id}/updates")
async def api_session_updates(session_id: str) -> list[dict[str, Any]]:
    """Return status updates for a specific session."""
    return _serialise_rows(await get_session_updates(session_id))


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Serve the dashboard UI."""
    return DASHBOARD_HTML
