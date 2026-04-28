"""Pluggable storage for uploaded files and per-upload metadata.

Default backend writes to /tmp and tracks state in-process. When
ENABLE_GCS_STORAGE is true, the local copy still exists for the duration of
the request (Cloud Run filesystems are ephemeral) but is also mirrored to a
GCS object so subsequent stateless requests can re-fetch it.
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings


@dataclass
class UploadRecord:
    upload_id: str
    filename: str
    local_path: Path
    gcs_path: str | None = None
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class _Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, UploadRecord] = {}
        base = Path(tempfile.gettempdir()) / "vm-sheet-transformer"
        base.mkdir(parents=True, exist_ok=True)
        self._base = base

    def save(self, filename: str, data: bytes) -> UploadRecord:
        upload_id = uuid.uuid4().hex
        suffix = Path(filename).suffix
        local = self._base / f"{upload_id}{suffix}"
        local.write_bytes(data)
        record = UploadRecord(upload_id=upload_id, filename=filename, local_path=local)

        settings = get_settings()
        if settings.enable_gcs_storage and settings.gcs_bucket_name:
            record.gcs_path = self._mirror_to_gcs(record, data)

        with self._lock:
            self._records[upload_id] = record
        return record

    def get(self, upload_id: str) -> UploadRecord | None:
        with self._lock:
            record = self._records.get(upload_id)
        if record is None:
            return None
        if not record.local_path.exists() and record.gcs_path:
            self._restore_from_gcs(record)
        return record

    def evict_expired(self) -> int:
        settings = get_settings()
        ttl = settings.upload_retention_minutes * 60
        cutoff = time.time() - ttl
        removed = 0
        with self._lock:
            for uid, rec in list(self._records.items()):
                if rec.created_at < cutoff:
                    try:
                        rec.local_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    del self._records[uid]
                    removed += 1
        return removed

    @staticmethod
    def _mirror_to_gcs(record: UploadRecord, data: bytes) -> str | None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError:
            return None
        settings = get_settings()
        client = storage.Client()
        bucket = client.bucket(settings.gcs_bucket_name)
        blob_name = f"uploads/{record.upload_id}/{record.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data)
        return f"gs://{settings.gcs_bucket_name}/{blob_name}"

    @staticmethod
    def _restore_from_gcs(record: UploadRecord) -> None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError:
            return
        if not record.gcs_path:
            return
        bucket_name, _, blob_path = record.gcs_path.replace("gs://", "").partition("/")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        record.local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(record.local_path))


_store = _Store()


def get_store() -> _Store:
    return _store


__all__ = ["UploadRecord", "get_store"]
