"""Aliyun OSS object storage adapter.

The ``Document.source_uri`` column stores OSS object URIs in the form
``oss://{key}``. Uploads, parses, reindex, and delete all flow through OSS;
there is no local-disk fallback.
"""
from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

_OSS_SCHEME = "oss://"
_bucket = None  # type: ignore[var-annotated]


def get_bucket():
    global _bucket
    if _bucket is None:
        import oss2

        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        _bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)
    return _bucket


def make_key(filename: str) -> str:
    pfx = (settings.oss_prefix or "").rstrip("/") + "/"
    safe_name = Path(filename).name.replace("/", "_").replace("\\", "_")
    return f"{pfx}{uuid.uuid4().hex}_{safe_name}"


def uri_for(key: str) -> str:
    if key.startswith(_OSS_SCHEME):
        return key
    return f"{_OSS_SCHEME}{key}"


def key_from_uri(uri: str | None) -> str | None:
    if not uri or not uri.startswith(_OSS_SCHEME):
        return None
    return uri[len(_OSS_SCHEME):]


def is_oss_uri(uri: str | None) -> bool:
    return bool(uri) and uri.startswith(_OSS_SCHEME)  # type: ignore[return-value]


def upload_bytes(data: bytes, filename: str, content_type: str | None = None) -> str:
    key = make_key(filename)
    bucket = get_bucket()
    headers = {"Content-Type": content_type} if content_type else None
    bucket.put_object(key, data, headers=headers)
    return uri_for(key)


def download_to_file(uri_or_key: str, suffix: str | None = None) -> Path:
    key = key_from_uri(uri_or_key) or uri_or_key
    bucket = get_bucket()
    if suffix is None:
        suffix = Path(key).suffix or ".bin"
    fd, path_str = tempfile.mkstemp(suffix=suffix, prefix="oss_")
    os.close(fd)
    path = Path(path_str)
    try:
        bucket.get_object_to_file(key, path_str)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def object_exists(uri_or_key: str) -> bool:
    key = key_from_uri(uri_or_key) or uri_or_key
    bucket = get_bucket()
    return bool(bucket.object_exists(key))


def delete(uri_or_key: str) -> None:
    key = key_from_uri(uri_or_key) or uri_or_key
    bucket = get_bucket()
    try:
        bucket.delete_object(key)
    except Exception as e:
        logger.warning("OSS delete failed for %s: %s", key, e)
