from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    devin_api_key: str
    devin_org_id: str
    github_token: str
    github_webhook_secret: str = ""

    # Devin API
    devin_api_base: str = "https://api.devin.ai/v3"

    # Polling
    poll_interval_seconds: int = 30
    poll_timeout_seconds: int = 3600  # 1 hour max

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]
