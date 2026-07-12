"""Object storage for invoice images.

Two implementations behind one Protocol (mirrors the translation/discovery
provider pattern):
  * ``LocalDiskStorage`` — dev/test, writes under ``storage_local_dir`` with
    path-traversal protection.
  * ``S3Storage`` — any S3-compatible endpoint (R2 / Backblaze / AWS) via env.

Keys are always server-generated (``invoices/{org_id}/{sha256}.{ext}``); client
filenames are never trusted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("storage")


class StorageService(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...

    def get(self, key: str) -> bytes: ...

    def signed_url(self, key: str, ttl: int = 3600) -> str | None: ...


class LocalDiskStorage:
    """Stores bytes under a base directory. Path-traversal safe."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Reject absolute keys and any traversal that escapes the base dir.
        candidate = (self._base / key).resolve()
        if not candidate.is_relative_to(self._base):
            raise ValueError(f"unsafe storage key: {key!r}")
        return candidate

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def signed_url(self, key: str, ttl: int = 3600) -> str | None:
        # No public URL for local disk; the API streams the image instead.
        return None


class S3Storage:
    """S3-compatible object storage (AWS/R2/Backblaze). Lazily builds a client."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint: str | None,
        region: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        self._bucket = bucket
        self._endpoint = endpoint or None
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._client_cache: object | None = None

    def _client(self) -> object:
        if self._client_cache is None:
            import boto3  # imported lazily so tests/local don't need AWS libs at import

            self._client_cache = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                region_name=self._region,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
            )
        return self._client_cache

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self._client().put_object(  # type: ignore[attr-defined]
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )
        return key

    def get(self, key: str) -> bytes:
        resp = self._client().get_object(Bucket=self._bucket, Key=key)  # type: ignore[attr-defined]
        return bytes(resp["Body"].read())

    def signed_url(self, key: str, ttl: int = 3600) -> str | None:
        return str(
            self._client().generate_presigned_url(  # type: ignore[attr-defined]
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl,
            )
        )


def get_storage_service() -> StorageService:
    if settings.storage_provider.lower() == "s3" and settings.s3_bucket:
        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint=settings.s3_endpoint,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
    return LocalDiskStorage(settings.storage_local_dir)
