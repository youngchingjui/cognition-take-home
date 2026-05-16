import asyncio
import hashlib
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from webhook.config import settings
from webhook.devin_client import create_session, get_session
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
    yield
    # Cancel all background polling tasks on shutdown
    for task in _active_tasks:
        task.cancel()
    if _active_tasks:
        await asyncio.gather(*_active_tasks, return_exceptions=True)
    _active_tasks.clear()


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

            if status in terminal_statuses:
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
        return {"status": "ignored", "reason": f"event type '{x_github_event}' not handled"}

    data = await request.json()
    action = data.get("action")

    if action != "labeled":
        return {"status": "ignored", "reason": f"action '{action}' not handled"}

    label = data.get("label", {})
    if label.get("name") != "devin-fix":
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

    # Create Devin session
    prompt = _build_prompt(issue, repo_full_name)
    try:
        session_resp = await create_session(prompt)
    except Exception:
        logger.exception("Failed to create Devin session for %s#%d", repo_full_name, issue_number)
        raise HTTPException(status_code=502, detail="Failed to create Devin session")

    session_id = session_resp.get("session_id", "")
    session_url = session_resp.get("url", f"https://app.devin.ai/sessions/{session_id}")

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
