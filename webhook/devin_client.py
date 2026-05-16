import logging

import httpx

from webhook.config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {settings.devin_api_key}",
    "Content-Type": "application/json",
}

BASE = f"{settings.devin_api_base}/organizations/{settings.devin_org_id}"


async def create_session(prompt: str) -> dict:
    """Create a new Devin session and return the response."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE}/sessions",
            headers=HEADERS,
            json={"prompt": prompt},
        )
        resp.raise_for_status()
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
        resp.raise_for_status()
        return resp.json()
