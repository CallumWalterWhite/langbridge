from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


def path_to_storage_uri(path: str | Path) -> str:
    return Path(path).resolve().as_uri()


def resolve_local_storage_path(storage_uri: str) -> Path:
    parsed = urlparse(storage_uri)
    if parsed.scheme in {"", "file"}:
        raw_path = parsed.path or storage_uri
        return Path(unquote(raw_path)).resolve()
    raise ValueError(f"Unsupported storage URI scheme '{parsed.scheme}'.")
