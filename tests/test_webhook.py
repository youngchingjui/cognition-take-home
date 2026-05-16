import hashlib
import hmac
import json

# Set required env vars before importing the app
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DEVIN_API_KEY", "cog_test_key")
os.environ.setdefault("DEVIN_ORG_ID", "org_test")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")

from webhook.server import app  # noqa: E402


def _sign(payload: bytes, secret: str = "test_secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _make_issue_labeled_payload(
    label_name: str = "devin-fix",
    issue_number: int = 42,
    issue_title: str = "Bug: login fails",
    issue_body: str = "The login page returns a 500 error.",
    repo_full_name: str = "youngchingjui/superset",
) -> dict:
    return {
        "action": "labeled",
        "label": {"name": label_name},
        "issue": {
            "number": issue_number,
            "title": issue_title,
            "body": issue_body,
        },
        "repository": {"full_name": repo_full_name},
    }


@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest.fixture
def client(transport):
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_ignores_non_issue_events(client):
    payload = json.dumps({"action": "opened"}).encode()
    resp = await client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_ignores_non_labeled_action(client):
    data = _make_issue_labeled_payload()
    data["action"] = "opened"
    payload = json.dumps(data).encode()
    resp = await client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_ignores_other_labels(client):
    data = _make_issue_labeled_payload(label_name="bug")
    payload = json.dumps(data).encode()
    resp = await client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


@pytest.mark.asyncio
@patch("webhook.server.post_issue_comment", new_callable=AsyncMock)
@patch("webhook.server.create_session", new_callable=AsyncMock)
async def test_devin_fix_triggers_session(mock_create, mock_comment, client):
    mock_create.return_value = {
        "session_id": "devin-abc123",
        "url": "https://app.devin.ai/sessions/devin-abc123",
        "status": "running",
    }
    mock_comment.return_value = {"id": 1}

    data = _make_issue_labeled_payload()
    payload = json.dumps(data).encode()
    resp = await client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "session_created"
    assert result["session_id"] == "devin-abc123"
    assert result["issue"] == "youngchingjui/superset#42"

    mock_create.assert_called_once()
    mock_comment.assert_called_once()
    # Verify the comment was posted to the right issue
    call_args = mock_comment.call_args
    assert call_args[0][0] == "youngchingjui"
    assert call_args[0][1] == "superset"
    assert call_args[0][2] == 42


@pytest.mark.asyncio
async def test_invalid_signature_rejected(client):
    data = _make_issue_labeled_payload()
    payload = json.dumps(data).encode()
    resp = await client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=bad_signature",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401
