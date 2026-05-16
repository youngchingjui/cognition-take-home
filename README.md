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
2. Use the **same value** when configuring the webhook in each GitHub repository (see [Step 5](#5-configure-webhooks-on-your-repositories) below)

> **Note:** If `GITHUB_WEBHOOK_SECRET` is left empty, the server will skip signature verification and accept all incoming requests. This is fine for local development, but you should always set a secret in production.

### 3. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

This starts the webhook server on port **8000** with a Postgres database for logging.
Open **http://localhost:8000** to view the dashboard.

#### Run without Docker

If you prefer to run the server directly:

```bash
uvicorn webhook.server:app --host 0.0.0.0 --port 8000
```

> **Note:** Without `DATABASE_URL` set, the server runs without persistence (no dashboard data).

### 4. Local Development with Smee.io

GitHub webhooks require a publicly accessible URL. During local development, use [**smee.io**](https://smee.io) — a free webhook proxy that forwards payloads from GitHub to your local machine.

#### 4a. Create a Smee Channel

1. Go to [**https://smee.io/new**](https://smee.io/new)
2. You'll be redirected to a unique URL like `https://smee.io/AbCdEfGhIjKl`
3. Copy this URL — you'll use it as the **Payload URL** when configuring your GitHub webhook (Step 5), and as the `--url` argument for the smee client below

#### 4b. Install the Smee Client

```bash
npm install -g smee-client
```

> **Note:** If you don't have Node.js/npm installed, you can also use the [**smee-client Python package**](https://pypi.org/project/pysmee/): `pip install pysmee`

#### 4c. Start the Smee Client

In a **separate terminal**, run:

```bash
smee --url https://smee.io/<your-channel-id> --target http://localhost:8000/webhook/github
```

Replace `https://smee.io/<your-channel-id>` with your actual Smee channel URL from Step 4a.

This will listen for webhook deliveries on your Smee channel and forward them to your local server at `http://localhost:8000/webhook/github`.

> **Tip:** Keep this terminal open while developing. The smee client must be running to receive webhooks locally.

### 5. Configure Webhooks on Your Repositories

For each repository you want to monitor:

1. Go to your repository's webhook settings: `https://github.com/<owner>/<repo>/settings/hooks`
   (or navigate to **Settings → Webhooks** in the GitHub repo)
2. Click **Add webhook**
3. Set the **Payload URL** to:
   - **For local development:** Your Smee channel URL (e.g. `https://smee.io/AbCdEfGhIjKl`) from [Step 3a](#3a-create-a-smee-channel)
   - **For production:** `https://<your-server>/webhook/github`
4. Set **Content type** to: `application/json`
5. Set the **Secret** to the same value you saved as `GITHUB_WEBHOOK_SECRET` in your `.env` file
6. Under **Which events would you like to trigger this webhook?**, select **Let me select individual events** and check **Issues**
7. Click **Add webhook**

> **Important:** The **Secret** field in GitHub must exactly match the `GITHUB_WEBHOOK_SECRET` value in your `.env` file. This is how the server verifies that webhook payloads are genuinely from GitHub.

### 6. Create the `devin-fix` Label

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
| `GET` | `/` | Dashboard UI — view webhook events and Devin sessions |
| `GET` | `/health` | Health check, returns active session count |
| `POST` | `/webhook/github` | GitHub webhook receiver |
| `GET` | `/api/events` | Recent webhook events (JSON) |
| `GET` | `/api/sessions` | Devin sessions (JSON) |
| `GET` | `/api/sessions/{id}/updates` | Status updates for a session (JSON) |

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

### Running Locally (Quick Start)

1. Install dependencies: `pip install -e ".[dev]"`
2. Copy `.env.example` to `.env` and fill in your credentials (see [Setup](#setup))
3. Create a Smee channel at [smee.io/new](https://smee.io/new)
4. In terminal 1: `smee --url https://smee.io/<your-channel-id> --target http://localhost:8000/webhook/github`
5. In terminal 2: `uvicorn webhook.server:app --host 0.0.0.0 --port 8000`
6. Configure a GitHub repo webhook to point to your Smee URL (see [Step 5](#5-configure-webhooks-on-your-repositories))
7. Label an issue with `devin-fix` — you should see the webhook payload in your smee terminal and the server processing it

## Deployment

The server can be deployed to any platform that supports Docker. The included `Dockerfile` and `docker-compose.yml` handle everything:

```bash
# Production deploy with Docker Compose
docker compose up -d --build
```

For platforms like Fly.io:

```bash
fly deploy
```

Make sure to set the environment variables as secrets on your deployment platform and provide a Postgres database via `DATABASE_URL`.
