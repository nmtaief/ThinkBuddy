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
        description="Runtime environment (local, development, staging, production)",
    )
    ENVIRONMENT: str = Field(
        default="local",
        description="Alias for runtime environment",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    CORE_HOST: str = Field(default="127.0.0.1", description="Core host address")
    CORE_PORT: int = Field(default=8001, description="Core port")

    # Reverse proxy security (restricted to specific web/gateway addresses, no whole private ranges)
    # Reverse proxy security: Core trusts strictly the Gateway's specific fixed IP/loopback.
    # No whole private ranges and no container hostnames.
    TRUSTED_PROXIES: list[str] = Field(
        default=[
            "127.0.0.1",
            "::1",
            "172.29.0.2",  # Gateway fixed address in internal network
        ],
        description="Core trusted reverse proxy IP addresses (strictly Gateway only, no hostnames)",
    )

    # Internal service authentication
    INTERNAL_SERVICE_TOKEN: str = Field(
        default="dev_internal_service_token_placeholder_change_in_production",
        description="Shared secret for gateway-to-core communication",
    )
    INTERNAL_SERVICE_SECRET: str = Field(
        default="dev_internal_service_hmac_secret_32bytes_min_key!",
        description="HMAC secret key for signing inter-service JWTs",
    )
    QUESTION_KEY_ENCRYPTION_KEY: str = Field(
        default="dev_question_key_aes_gcm_32bytes_secret_key!",
        description="AES-GCM key for encrypting question keys at rest",
    )
    EXPORT_ENCRYPTION_KEY: str = Field(
        default="prod_valid_high_entropy_export_crypto_key_384729",
        description="AES-GCM key for encrypting exported family archives at rest",
    )

    # Public ingress domain
    PUBLIC_DOMAIN: str | None = Field(
        default=None,
        description="Public domain for API and client ingress (e.g. api.thinkbuddy.com)",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy",
        description="Async PostgreSQL connection URL with pgvector",
    )
    DB_POOL_SIZE: int = Field(default=25, description="Database pool size per Core worker process")
    DB_MAX_OVERFLOW: int = Field(default=15, description="Database pool max overflow per Core worker process")
    DB_POOL_TIMEOUT: float = Field(default=15.0, description="Database pool checkout timeout in seconds")
    WORKER_DB_POOL_SIZE: int = Field(
        default=5,
        description="Database pool size for Celery worker processes",
    )
    WORKER_DB_MAX_OVERFLOW: int = Field(
        default=5,
        description="Database pool max overflow for Celery worker processes",
    )

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

    # Offsite Disaster Recovery Storage (Different provider or region, separate least-privilege credentials)
    OFFSITE_BACKUP_PROVIDER: str = Field(
        default="minio",
        description="Offsite backup storage provider (e.g., s3, cloudflare_r2, backblaze_b2, minio)",
    )
    OFFSITE_BACKUP_ENDPOINT_URL: str = Field(
        default="http://localhost:9000",
        description="Offsite S3/R2 endpoint URL (different host/provider from primary S3)",
    )
    OFFSITE_BACKUP_ACCESS_KEY_ID: str = Field(
        default="minio_dev_access_key",
        description="Offsite backup access key ID (separate least-privilege credentials)",
    )
    OFFSITE_BACKUP_SECRET_ACCESS_KEY: str = Field(
        default="minio_dev_secret_key",
        description="Offsite backup secret access key (separate least-privilege credentials)",
    )
    OFFSITE_BACKUP_BUCKET_NAME: str = Field(
        default="thinkbuddy-backups-offsite",
        description="Offsite backup destination bucket name",
    )
    OFFSITE_BACKUP_REGION: str = Field(
        default="eu-central-1",
        description="Offsite backup region (separate geographical region from primary, e.g. eu-central-1 vs ap-southeast-1)",
    )
    OFFSITE_BACKUP_USE_SSL: bool = Field(
        default=False,
        description="Whether to use SSL for offsite backup storage connection",
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
    FEATURE_RAG_CHAT_ENABLED: bool = Field(
        default=False,
        description="Global feature flag for RAG AI Tutor Chat (P05). Disabled by default.",
    )
    FEATURE_PROGRESS_MASTERY_ENABLED: bool = Field(
        default=False,
        description="Global feature flag for Progress & Mastery tracking (P06). Disabled by default.",
    )
    FEATURE_SPACED_REVISION_ENABLED: bool = Field(
        default=False,
        description="Global feature flag for Spaced Revision Scheduler (P06). Disabled by default.",
    )
    FEATURE_WEB_APP: bool = Field(
        default=False,
        description="Global feature flag for Web Application & BFF Proxy (P08). Disabled by default; enabled via environment.",
    )
    FEATURE_ANDROID_APP: bool = Field(
        default=False,
        description="Global feature flag for Native Android Application (P08a). Disabled by default; enabled via environment.",
    )

    # AI Planner Integration (P06a)
    AI_PLANNER_ENABLED: bool = Field(
        default=False,
        description="Global kill switch for AI study planner integration (P06a)",
    )
    AI_PLANNER_SHADOW_MODE: bool = Field(
        default=False,
        description="Shadow mode: calls AI planner in background for evaluation without applying it",
    )
    AI_PLANNER_URL: str = Field(
        default="http://localhost:8088",
        description="Base URL for external AI planner service",
    )
    AI_PLANNER_API_KEY: str = Field(
        default="ai_planner_dev_secret_key_placeholder",
        description="Service authentication key for AI planner service",
    )
    AI_PLANNER_SECRET_KEY: str = Field(
        default="ai_planner_service_hmac_secret_32_chars_dev_key",
        description="HMAC secret for signing short-lived service tokens",
    )
    AI_PLANNER_ENABLED_CLASS_BANDS: list[str] = Field(
        default_factory=lambda: ["6-8", "9-10", "11-12"],
        description="Class bands where AI planner is enabled for rollout",
    )
    AI_PLANNER_TIMEOUT_SECONDS: float = Field(
        default=20.0,
        description="HTTP timeout in seconds for AI planner routine proposal endpoint",
    )
    AI_PLANNER_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum HTTP retries on transient errors with exponential backoff",
    )
    AI_PLANNER_CIRCUIT_BREAKER_FAILURES: int = Field(
        default=3,
        description="Number of consecutive failures before opening circuit breaker",
    )
    AI_PLANNER_CIRCUIT_BREAKER_RESET_SECONDS: float = Field(
        default=30.0,
        description="Cooldown duration in seconds before testing half-open state",
    )

    # Ingestion & RAG Settings
    EMBEDDING_PROVIDER: str = Field(
        default="mock",
        description="Embedding provider implementation (mock, hosted, bge-m3, multilingual-e5)",
    )
    EMBEDDING_MODEL: str = Field(
        default="bge-m3",
        description="Model identifier for multilingual text embeddings",
    )
    EMBEDDING_DIMENSION: int = Field(
        default=384,
        description="Vector dimension for embeddings (read from provider config)",
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="Batch size for generating embeddings",
    )
    OCR_QUALITY_THRESHOLD: float = Field(
        default=0.70,
        description="Minimum OCR quality threshold (0.0 to 1.0) for chunk retrievability",
    )

    @property
    def is_local(self) -> bool:
        """Return True only if running in local environment (ENV=local)."""
        return (self.ENV or "").strip().lower() == "local"

    @model_validator(mode="after")
    def validate_non_local_secrets(self) -> "CoreSettings":
        """Refuse placeholder or weak secrets in non-local environments."""
        if self.ENVIRONMENT != "local" and self.ENV == "local":
            self.ENV = self.ENVIRONMENT
        self.ENVIRONMENT = self.ENV
        env = self.ENV.lower()
        is_dev_or_local = env in {"local", "development", "dev", "test", "testing"}
        if not is_dev_or_local:
            known_defaults = {
                "dev_internal_service_token_placeholder_change_in_production",
                "placeholder_token",
                "dev_jwt_secret_key_change_in_production_9876543210123456789",
                "dev_link_code_hmac_secret_key_change_in_production",
                "dev_jwt_secret_key_change_in_production",
                "dev_link_code_secret_change_in_production",
            }

            # 1. Internal Service Token
            token_lower = self.INTERNAL_SERVICE_TOKEN.lower()
            if (
                "placeholder" in token_lower
                or "dev_" in token_lower
                or self.INTERNAL_SERVICE_TOKEN in known_defaults
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder INTERNAL_SERVICE_TOKEN."
                )
                raise ValueError(msg)
            if len(self.INTERNAL_SERVICE_TOKEN) < 32:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "INTERNAL_SERVICE_TOKEN must have at least 32 characters."
                )
                raise ValueError(msg)

            # 2. Database credentials
            if "thinkbuddy_dev_password" in self.DATABASE_URL.lower():
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with default development database credentials."
                )
                raise ValueError(msg)

            # 3. JWT Secret Key
            jwt_lower = self.JWT_SECRET_KEY.lower()
            if (
                "change_in_production" in jwt_lower
                or "dev_" in jwt_lower
                or self.JWT_SECRET_KEY in known_defaults
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder JWT_SECRET_KEY."
                )
                raise ValueError(msg)
            if len(self.JWT_SECRET_KEY) < 32:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "JWT_SECRET_KEY must have at least 32 characters."
                )
                raise ValueError(msg)

            # 4. Link Code Secret
            link_lower = self.LINK_CODE_SECRET.lower()
            if (
                "change_in_production" in link_lower
                or "dev_" in link_lower
                or self.LINK_CODE_SECRET in known_defaults
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder LINK_CODE_SECRET."
                )
                raise ValueError(msg)
            if len(self.LINK_CODE_SECRET) < 32:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "LINK_CODE_SECRET must have at least 32 characters."
                )
                raise ValueError(msg)

            # 5. Internal Service Secret (HMAC)
            service_secret_lower = self.INTERNAL_SERVICE_SECRET.lower()
            if (
                "change_in_production" in service_secret_lower
                or "dev_" in service_secret_lower
                or "placeholder" in service_secret_lower
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder INTERNAL_SERVICE_SECRET."
                )
                raise ValueError(msg)
            if len(self.INTERNAL_SERVICE_SECRET) < 32:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "INTERNAL_SERVICE_SECRET must have at least 32 characters."
                )
                raise ValueError(msg)

            # 6. Question Key Encryption Key
            crypto_key_lower = self.QUESTION_KEY_ENCRYPTION_KEY.lower()
            if (
                "change_in_production" in crypto_key_lower
                or "dev_" in crypto_key_lower
                or "placeholder" in crypto_key_lower
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder QUESTION_KEY_ENCRYPTION_KEY."
                )
                raise ValueError(msg)
            if len(self.QUESTION_KEY_ENCRYPTION_KEY) < 32:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "QUESTION_KEY_ENCRYPTION_KEY must have at least 32 characters."
                )
                raise ValueError(msg)

            # 7. Export Encryption Key
            export_key_lower = self.EXPORT_ENCRYPTION_KEY.lower()
            if (
                "change_in_production" in export_key_lower
                or "dev_" in export_key_lower
                or "placeholder" in export_key_lower
                or self.EXPORT_ENCRYPTION_KEY in known_defaults
            ):
                msg = (
                    f"Refusing to start in environment '{self.ENV}' "
                    "with placeholder EXPORT_ENCRYPTION_KEY."
                )
                raise ValueError(msg)
            if len(self.EXPORT_ENCRYPTION_KEY) < 32:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "EXPORT_ENCRYPTION_KEY must have at least 32 characters."
                )
                raise ValueError(msg)

            # 3. Require distinct secrets across all keys
            secrets_set = {
                self.JWT_SECRET_KEY,
                self.LINK_CODE_SECRET,
                self.INTERNAL_SERVICE_TOKEN,
                self.INTERNAL_SERVICE_SECRET,
                self.QUESTION_KEY_ENCRYPTION_KEY,
                self.EXPORT_ENCRYPTION_KEY,
            }
            if len(secrets_set) < 6:
                msg = (
                    f"Refusing to start in environment '{self.ENV}': "
                    "JWT_SECRET_KEY, LINK_CODE_SECRET, INTERNAL_SERVICE_TOKEN, "
                    "INTERNAL_SERVICE_SECRET, QUESTION_KEY_ENCRYPTION_KEY, and EXPORT_ENCRYPTION_KEY must be distinct."
                )
                raise ValueError(msg)

        return self


settings = CoreSettings()
