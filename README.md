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

Below is a breakdown of each variable and how to obtain it.

#### `DEVIN_API_KEY`

Your Devin API key, used to create and poll Devin sessions. It starts with `cog_`.

1. Go to [**Devin → Settings → API Keys**](https://app.devin.ai/settings/api-keys)
2. Click **Create API Key**
3. Give it a descriptive name (e.g. `issue-remediation-webhook`)
4. Copy the key and paste it into your `.env` file

#### `DEVIN_ORG_ID`

Your Devin organization ID, used to scope API requests to your organization.

1. Go to [**Devin → Settings → General**](https://app.devin.ai/settings)
2. Your organization ID is displayed on this page
3. Copy the ID and paste it into your `.env` file

#### `GITHUB_TOKEN`

A GitHub **Personal Access Token (classic)** used to post comments on issues. It needs the `repo` scope.

1. Go to [**GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**](https://github.com/settings/tokens)
2. Click **Generate new token** → **Generate new token (classic)**
3. Give it a descriptive note (e.g. `devin-webhook`)
4. Set an expiration (or choose **No expiration** for long-running deployments)
5. Under **Select scopes**, check **`repo`** (this grants access to post comments on issues)
6. Click **Generate token**
7. Copy the token immediately (you won't be able to see it again) and paste it into your `.env` file

> **Tip:** If you prefer fine-grained tokens, go to [**Fine-grained tokens**](https://github.com/settings/personal-access-tokens/new) instead. Grant **Read and Write** access to **Issues** for the specific repositories you want to monitor.

#### `GITHUB_WEBHOOK_SECRET`

A shared secret used to verify that incoming webhook requests are genuinely from GitHub (via HMAC-SHA256 signature verification). This is optional but **strongly recommended** for production use.

**Generate a secret:**

```bash
# Generate a random 32-character hex string
python -c "import secrets; print(secrets.token_hex(32))"
```

Or use `openssl`:

```bash
openssl rand -hex 32
```

1. Copy the generated value and paste it into your `.env` file as `GITHUB_WEBHOOK_SECRET`
2. Use the **same value** when configuring the webhook in each GitHub repository (see [Step 4](#4-configure-webhooks-on-your-repositories) below)

> **Note:** If `GITHUB_WEBHOOK_SECRET` is left empty, the server will skip signature verification and accept all incoming requests. This is fine for local development, but you should always set a secret in production.

### 3. Run the Server

```bash
uvicorn webhook.server:app --host 0.0.0.0 --port 8000
```

### 4. Configure Webhooks on Your Repositories

For each repository you want to monitor:

1. Go to your repository's webhook settings: `https://github.com/<owner>/<repo>/settings/hooks`
   (or navigate to **Settings → Webhooks** in the GitHub repo)
2. Click **Add webhook**
3. Set the **Payload URL** to: `https://<your-server>/webhook/github`
4. Set **Content type** to: `application/json`
5. Set the **Secret** to the same value you saved as `GITHUB_WEBHOOK_SECRET` in your `.env` file
6. Under **Which events would you like to trigger this webhook?**, select **Let me select individual events** and check **Issues**
7. Click **Add webhook**

> **Important:** The **Secret** field in GitHub must exactly match the `GITHUB_WEBHOOK_SECRET` value in your `.env` file. This is how the server verifies that webhook payloads are genuinely from GitHub.

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
