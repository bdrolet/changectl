"""Document storage: GCS in production, local disk for tests and local dev."""

import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def signed_url(self, key: str, filename: str, minutes: int = 10) -> str: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def signed_url(self, key: str, filename: str, minutes: int = 10) -> str:
        return Path(self.root / key).resolve().as_uri()


class GcsStorage:
    def __init__(self, bucket: str) -> None:
        self.bucket_name = bucket
        self._client: Any = None

    def _bucket(self) -> Any:
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client.bucket(self.bucket_name)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._bucket().blob(key).upload_from_string(data, content_type=content_type)

    def get(self, key: str) -> bytes:
        data: bytes = self._bucket().blob(key).download_as_bytes()
        return data

    def signed_url(self, key: str, filename: str, minutes: int = 10) -> str:
        import google.auth
        from google.auth.transport.requests import Request

        credentials: Any
        credentials, _ = google.auth.default()
        credentials.refresh(Request())
        url: str = (
            self._bucket()
            .blob(key)
            .generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=minutes),
                method="GET",
                response_disposition=f'attachment; filename="{filename}"',
                service_account_email=credentials.service_account_email,
                access_token=credentials.token,
            )
        )
        return url


def from_env() -> Storage:
    bucket = os.environ.get("CHANGECTL_BUCKET")
    if bucket:
        return GcsStorage(bucket)
    return LocalStorage(Path(os.environ.get("CHANGECTL_LOCAL_STORAGE", ".storage")))


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file"


def object_key(document_id: str, revision_id: str, filename: str) -> str:
    return f"documents/{document_id}/{revision_id}/{safe_filename(filename)}"
