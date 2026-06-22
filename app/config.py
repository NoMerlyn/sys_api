"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read configuration from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: Annotated[str, Field(alias="DATABASE_URL")]
    database_url_sync: Annotated[str, Field(alias="DATABASE_URL_SYNC")]

    # JWT
    jwt_secret: Annotated[str, Field(alias="JWT_SECRET")]
    jwt_algorithm: Annotated[str, Field(alias="JWT_ALGORITHM")] = "HS256"
    jwt_issuer: Annotated[str, Field(alias="JWT_ISSUER")] = "sys_api"
    jwt_audience: Annotated[str, Field(alias="JWT_AUDIENCE")] = "pos-clients"
    jwt_ttl_seconds: Annotated[int, Field(alias="JWT_TTL_SECONDS")] = 28800

    # RabbitMQ
    rabbitmq_url: Annotated[str, Field(alias="RABBITMQ_URL")]

    # Server
    host: Annotated[str, Field(alias="HOST")] = "0.0.0.0"
    port: Annotated[int, Field(alias="PORT")] = 8000
    log_level: Annotated[str, Field(alias="LOG_LEVEL")] = "info"
    env: Annotated[str, Field(alias="ENV")] = "dev"

    # Login policy
    login_max_failed_attempts: Annotated[int, Field(alias="LOGIN_MAX_FAILED_ATTEMPTS")] = 3

    # CORS
    cors_allow_origins: Annotated[str, Field(alias="CORS_ALLOW_ORIGINS")] = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
