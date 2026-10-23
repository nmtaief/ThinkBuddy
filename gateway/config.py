"""Gateway application configuration via pydantic-settings."""

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Configuration settings for ThinkBuddy Gateway Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = Field(
        default="local",
        validation_alias=AliasChoices("ENV", "ENVIRONMENT"),
        description="Runtime environment (local, development, staging, production)",
    )
    ENVIRONMENT: str = Field(
        default="local",
        validation_alias=AliasChoices("ENVIRONMENT", "ENV"),
        description="Alias for runtime environment",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    @property
    def is_local(self) -> bool:
        """Return True only if running in local environment (ENV=local)."""
        return self.ENV.lower() == "local"

    GATEWAY_HOST: str = Field(default="127.0.0.1", description="Gateway host address")
    GATEWAY_PORT: int = Field(default=8000, description="Gateway port")

    # Downstream Core connection
    CORE_INTERNAL_URL: str = Field(
        default="http://127.0.0.1:8001",
        description="Internal URL to ThinkBuddy Core service",
    )
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="dev_internal_service_token_placeholder_change_in_production",
        description="Shared secret for gateway-to-core communication",
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL for rate limiting and cache",
    )

    # Observability
    OTEL_SERVICE_NAME: str = Field(default="thinkbuddy-gateway", description="OTel service name")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317",
        description="OTel collector endpoint",
    )
    OTEL_ENABLED: bool = Field(default=False, description="Enable OpenTelemetry tracing")

    @model_validator(mode="after")
    def validate_non_local_secrets(self) -> "GatewaySettings":
        """Refuse to start with placeholder secrets when environment is not local/development."""
        env = self.ENVIRONMENT.lower()
        is_local = env in {"local", "development", "dev", "test", "testing"}
        if not is_local:
            token_lower = self.INTERNAL_SERVICE_TOKEN.lower()
            if "placeholder" in token_lower or "dev_" in token_lower:
                msg = (
                    f"Refusing to start in environment '{self.ENVIRONMENT}' "
                    "with placeholder INTERNAL_SERVICE_TOKEN."
                )
                raise ValueError(msg)
        return self


settings = GatewaySettings()
