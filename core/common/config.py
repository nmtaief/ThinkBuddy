"""Core application configuration via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    """Configuration settings for ThinkBuddy Core Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    CORE_HOST: str = Field(default="127.0.0.1", description="Core host address")
    CORE_PORT: int = Field(default=8001, description="Core port")

    # Internal service authentication
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="dev_internal_service_token_placeholder_change_in_production",
        description="Shared secret for gateway-to-core communication",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://thinkbuddy:thinkbuddy_dev_password@localhost:5432/thinkbuddy",
        description="Async PostgreSQL connection URL with pgvector",
    )
    DB_POOL_SIZE: int = Field(default=10, description="Database pool size")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Database pool max overflow")

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Observability
    OTEL_SERVICE_NAME: str = Field(default="thinkbuddy-core", description="OTel service name")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317",
        description="OTel collector endpoint",
    )
    OTEL_ENABLED: bool = Field(default=False, description="Enable OpenTelemetry tracing")


settings = CoreSettings()
