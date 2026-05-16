import logging

import httpx

from webhook.config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {settings.devin_api_key}",
    "Content-Type": "application/json",
}

BASE = f"{settings.devin_api_base}/organizations/{settings.devin_org_id}"


class DevinAPIError(Exception):
    """Raised when the Devin API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str, response_body: str):
        self.status_code = status_code
        self.detail = detail
        self.response_body = response_body
        super().__init__(detail)


def _raise_on_error(resp: httpx.Response, context: str) -> None:
    """Log and raise a descriptive error for non-2xx responses."""
    if resp.is_success:
        return
    body = resp.text
    status = resp.status_code
    if status == 403:
        detail = (
            f"{context}: 403 Forbidden. "
            "Ensure your DEVIN_API_KEY belongs to a service user with the "
            "'ManageOrgSessions' permission and that DEVIN_ORG_ID is correct. "
            f"Response: {body}"
        )
    elif status == 401:
        detail = (
            f"{context}: 401 Unauthorized. "
            "The DEVIN_API_KEY is invalid or expired. "
            f"Response: {body}"
        )
    else:
        detail = f"{context}: HTTP {status}. Response: {body}"
    logger.error(detail)
    raise DevinAPIError(status_code=status, detail=detail, response_body=body)


async def create_session(prompt: str) -> dict:
    """Create a new Devin session and return the response."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE}/sessions",
            headers=HEADERS,
            json={"prompt": prompt},
        )
        _raise_on_error(resp, "Failed to create Devin session")
        data = resp.json()
        logger.info("Created Devin session %s", data.get("session_id"))
        return data


async def get_session(session_id: str) -> dict:
    """Get the current status of a Devin session."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE}/sessions/{session_id}",
            headers=HEADERS,
        )
        _raise_on_error(resp, f"Failed to get Devin session {session_id}")
        return resp.json()
