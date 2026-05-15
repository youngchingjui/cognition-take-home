import logging

import httpx

from webhook.config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"token {settings.github_token}",
    "Accept": "application/vnd.github+json",
}


async def post_issue_comment(owner: str, repo: str, issue_number: int, body: str) -> dict:
    """Post a comment on a GitHub issue."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=HEADERS, json={"body": body})
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "Posted comment on %s/%s#%d (id=%s)",
            owner,
            repo,
            issue_number,
            data.get("id"),
        )
        return data
