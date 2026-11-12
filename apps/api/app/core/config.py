from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-only-secret-key-change-me-in-production"


class Settings(BaseSettings):
    """Application settings, read from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Football Analytics API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://afa:afa@localhost:5432/afa"
    cors_origins: list[str] = ["http://localhost:3000"]

    secret_key: str = DEV_SECRET_KEY
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False

    @model_validator(mode="after")
    def _require_real_secrets_outside_development(self) -> "Settings":
        if self.environment != "development":
            if self.secret_key == DEV_SECRET_KEY:
                raise ValueError("SECRET_KEY must be set outside development")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
