"""Generic S3-compatible object storage interface.

Ensures ThinkBuddy storage is platform-agnostic and provider-independent.
Works identically with AWS S3, Cloudflare R2, or local Silo without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.common.config import CoreSettings


@dataclass(frozen=True)
class S3StorageConfig:
    """Generic S3 client connection settings."""

    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    region: str = "auto"
    use_ssl: bool = False

    @classmethod
    def from_settings(cls, settings: CoreSettings) -> S3StorageConfig:
        """Construct generic S3 config from application settings."""
        return cls(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            bucket_name=settings.S3_BUCKET_NAME,
            region=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
        )


@runtime_checkable
class ObjectStorage(Protocol):
    """Protocol defining generic object storage operations."""

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload an object and return its storage key or URL."""
        ...

    async def get_object(self, key: str) -> bytes:
        """Download an object's binary content."""
        ...

    async def delete_object(self, key: str) -> bool:
        """Delete an object by key."""
        ...

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        operation: str = "get_object",
    ) -> str:
        """Generate a time-limited presigned URL."""
        ...

    async def object_exists(self, key: str) -> bool:
        """Check whether an object exists."""
        ...
