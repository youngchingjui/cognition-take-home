import logging
from typing import Any

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


async def get_pr_check_status(owner: str, repo: str, pr_number: int) -> dict[str, Any]:
    """Fetch combined CI check status for a pull request.

    Returns a dict with:
      - total: number of check runs
      - passed: number that succeeded
      - failed: number that failed
      - pending: number still in progress
      - status: "all_passed", "has_failures", "pending", or "no_checks"
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Get the PR to find the head SHA
        pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        resp = await client.get(pr_url, headers=HEADERS)
        resp.raise_for_status()
        head_sha = resp.json().get("head", {}).get("sha", "")

        if not head_sha:
            return {"total": 0, "passed": 0, "failed": 0, "pending": 0, "status": "no_checks"}

        # Get check runs for the head commit
        checks_url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/commits/{head_sha}/check-runs"
        )
        resp = await client.get(checks_url, headers=HEADERS)
        resp.raise_for_status()
        check_runs = resp.json().get("check_runs", [])

        if not check_runs:
            return {"total": 0, "passed": 0, "failed": 0, "pending": 0, "status": "no_checks"}

        passed = 0
        failed = 0
        pending = 0
        for cr in check_runs:
            if cr.get("status") != "completed":
                pending += 1
            elif cr.get("conclusion") in ("success", "skipped", "neutral"):
                passed += 1
            else:
                failed += 1

        total = len(check_runs)
        if failed > 0:
            status = "has_failures"
        elif pending > 0:
            status = "pending"
        else:
            status = "all_passed"

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "status": status,
        }
