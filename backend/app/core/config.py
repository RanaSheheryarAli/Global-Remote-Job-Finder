from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    app_name: str = "Global Remote Job Tool API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://jobtool:jobtool@localhost:5432/jobtool"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    greenhouse_request_timeout_seconds: float = 15.0
    greenhouse_max_retries: int = 3
    source_circuit_breaker_threshold: int = 3
    source_circuit_breaker_cooldown_minutes: int = 30
    resume_max_bytes: int = 2_000_000
    refresh_source_concurrency: int = Field(default=3, ge=1, le=8)
    refresh_source_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    refresh_stale_after_seconds: int = Field(default=900, ge=60, le=7200)


@lru_cache
def get_settings() -> Settings:
    return Settings()
