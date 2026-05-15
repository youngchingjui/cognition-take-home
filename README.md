# Devin Issue Remediation Webhook

An event-driven automation that uses the [Devin API](https://docs.devin.ai/api-reference/overview) to automatically remediate GitHub issues.

## How It Works

```
GitHub Issue labeled "devin-fix"
  → GitHub sends webhook to this server
    → Server creates a Devin session with the issue context
      → Posts a comment on the issue with the session link
        → Polls session status → updates the issue when complete
```

1. You label a GitHub issue with `devin-fix` in any subscribed repository
2. GitHub sends a webhook event to this server
3. The server calls the Devin API to create a session that will fix the issue
4. A comment is posted on the issue with the Devin session link
5. The server polls the session until completion and posts a final status update (including any PRs created)

## Setup

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment Variables

Copy the example and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|----------|-------------|
| `DEVIN_API_KEY` | Devin service user API key (starts with `cog_`) |
| `DEVIN_ORG_ID` | Your Devin organization ID |
| `GITHUB_TOKEN` | GitHub personal access token (needs `repo` scope for posting comments) |
| `GITHUB_WEBHOOK_SECRET` | Shared secret for webhook signature verification |

### 3. Run the Server

```bash
uvicorn webhook.server:app --host 0.0.0.0 --port 8000
```

### 4. Configure Webhooks on Your Repositories

For each repository you want to monitor:

1. Go to **Settings → Webhooks → Add webhook** in the GitHub repo
2. Set the **Payload URL** to: `https://<your-server>/webhook/github`
3. Set **Content type** to: `application/json`
4. Set the **Secret** to the same value as your `GITHUB_WEBHOOK_SECRET`
5. Under **Which events would you like to trigger this webhook?**, select **Let me select individual events** and check **Issues**
6. Click **Add webhook**

### 5. Create the `devin-fix` Label

In each subscribed repository, create a label named `devin-fix`:

```bash
gh label create devin-fix --description "Trigger Devin to fix this issue" --color 7057ff --repo OWNER/REPO
```

## Usage

1. Open (or find) an issue in a subscribed repository
2. Add the `devin-fix` label
3. The webhook server will:
   - Create a Devin session to fix the issue
   - Post a comment with the session link
   - Poll until the session completes
   - Post a final comment with the status and any PRs created

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check, returns active session count |
| `POST` | `/webhook/github` | GitHub webhook receiver |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

## Deployment

The server can be deployed to any platform that supports Python ASGI apps. Example with Fly.io:

```bash
# The deploy tool handles Dockerfile and fly.toml generation
fly deploy
```

Make sure to set the environment variables as secrets on your deployment platform.
