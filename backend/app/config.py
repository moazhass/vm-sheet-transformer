"""Centralized environment-driven configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Cloud Run mandates listening on $PORT.
    port: int = Field(default=8080, alias="PORT")
    host: str = Field(default="0.0.0.0", alias="HOST")

    # Auth
    allowed_email_domains: str = Field(
        default="devoteam.com,devoteam.sa", alias="ALLOWED_EMAIL_DOMAINS"
    )
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    oauth_redirect_url: str | None = Field(default=None, alias="OAUTH_REDIRECT_URL")
    session_secret: str = Field(default="change-me", alias="SESSION_SECRET")
    dev_auth_bypass: bool = Field(default=False, alias="DEV_AUTH_BYPASS")

    # Uploads
    max_upload_mb: int = Field(default=25, alias="MAX_UPLOAD_MB")

    # Storage
    enable_gcs_storage: bool = Field(default=False, alias="ENABLE_GCS_STORAGE")
    gcs_bucket_name: str | None = Field(default=None, alias="GCS_BUCKET_NAME")
    upload_retention_minutes: int = Field(default=60, alias="UPLOAD_RETENTION_MINUTES")

    # Frontend hand-off
    frontend_dist_dir: str = Field(default="frontend/dist", alias="FRONTEND_DIST_DIR")

    @property
    def allowed_domains_list(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
