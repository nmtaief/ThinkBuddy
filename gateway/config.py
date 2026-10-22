"""Gateway application configuration via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Configuration settings for ThinkBuddy Gateway Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    GATEWAY_HOST: str = Field(default="127.0.0.1", description="Gateway host address")
    GATEWAY_PORT: int = Field(default=8000, description="Gateway port")

    # Downstream Core connection
    CORE_INTERNAL_URL: str = Field(
        default="http://localhost:8001",
        description="Internal URL to ThinkBuddy Core service",
    )
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="dev_internal_service_token_placeholder_change_in_production",
        description="Shared secret for gateway-to-core communication",
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for rate limiting and cache",
    )

    # Observability
    OTEL_SERVICE_NAME: str = Field(default="thinkbuddy-gateway", description="OTel service name")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317",
        description="OTel collector endpoint",
    )
    OTEL_ENABLED: bool = Field(default=False, description="Enable OpenTelemetry tracing")


settings = GatewaySettings()
