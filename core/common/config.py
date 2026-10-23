"""Core application configuration via pydantic-settings."""

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    """Configuration settings for ThinkBuddy Core Service."""

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

    CORE_HOST: str = Field(default="127.0.0.1", description="Core host address")
    CORE_PORT: int = Field(default=8001, description="Core port")

    # Reverse proxy security
    TRUSTED_PROXIES: list[str] = Field(
        default=[
            "127.0.0.1",
            "::1",
            "core",
            "gateway",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
        ],
        description="Trusted reverse proxy IP ranges or hostnames",
    )

    # Internal service authentication
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="dev_internal_service_token_placeholder_change_in_production",
        description="Shared secret for gateway-to-core communication",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy",
        description="Async PostgreSQL connection URL with pgvector",
    )
    DB_POOL_SIZE: int = Field(default=10, description="Database pool size")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Database pool max overflow")

    # Redis
    REDIS_URL: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL",
    )

    # Storage (Generic S3 Interface - Cloudflare R2 / AWS S3 in prod, Silo in dev)
    S3_ENDPOINT_URL: str = Field(
        default="http://localhost:9000",
        description="S3 endpoint URL",
    )
    S3_ACCESS_KEY_ID: str = Field(
        default="minio_dev_access_key",
        description="S3 access key ID",
    )
    S3_SECRET_ACCESS_KEY: str = Field(
        default="minio_dev_secret_key",
        description="S3 secret access key",
    )
    S3_BUCKET_NAME: str = Field(
        default="thinkbuddy-content",
        description="S3 bucket name",
    )
    S3_REGION: str = Field(
        default="auto",
        description="S3 region name",
    )
    S3_USE_SSL: bool = Field(
        default=False,
        description="Whether to use SSL for S3 connection",
    )

    # Observability
    OTEL_SERVICE_NAME: str = Field(default="thinkbuddy-core", description="OTel service name")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317",
        description="OTel collector endpoint",
    )
    OTEL_ENABLED: bool = Field(default=False, description="Enable OpenTelemetry tracing")

    # Authentication & JWT
    JWT_SECRET_KEY: str = Field(
        default="dev_jwt_secret_key_change_in_production_9876543210123456789",
        description="Secret key for signing access JWTs",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15, description="Access token expiration in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30, description="Refresh token expiration in days"
    )
    LINK_CODE_EXPIRE_HOURS: int = Field(
        default=24, description="Student link code expiration in hours"
    )
    LINK_CODE_SECRET: str = Field(
        default="dev_link_code_hmac_secret_key_change_in_production",
        description="Server-side secret used for HMAC-SHA256 hashing of student link codes",
    )

    # Feature Flags
    TEACHER_REVIEW_ENABLED: bool = Field(
        default=False, description="Teacher review feature flag (off in beta)"
    )

    @property
    def is_local(self) -> bool:
        """Return True only if running in local environment (ENV=local)."""
        return self.ENV.lower() == "local"

    @model_validator(mode="after")
    def validate_non_local_secrets(self) -> "CoreSettings":
        """Refuse to start with placeholder secrets when environment is not local/development."""
        env = self.ENV.lower()
        is_dev_or_local = env in {"local", "development", "dev", "test", "testing"}
        if not is_dev_or_local:
            token_lower = self.INTERNAL_SERVICE_TOKEN.lower()
            if "placeholder" in token_lower or "dev_" in token_lower:
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder INTERNAL_SERVICE_TOKEN."
                )
                raise ValueError(msg)
            if "thinkbuddy_dev_password" in self.DATABASE_URL.lower():
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with default development database credentials."
                )
                raise ValueError(msg)
            if (
                "change_in_production" in self.JWT_SECRET_KEY.lower()
                or "dev_" in self.JWT_SECRET_KEY.lower()
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder JWT_SECRET_KEY."
                )
                raise ValueError(msg)
            if (
                "change_in_production" in self.LINK_CODE_SECRET.lower()
                or "dev_" in self.LINK_CODE_SECRET.lower()
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder LINK_CODE_SECRET."
                )
                raise ValueError(msg)
        return self


settings = CoreSettings()
