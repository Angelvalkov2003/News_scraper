"""Shared utilities for base classes."""

import sys
from pathlib import Path


def ensure_utf8_stdout() -> None:
    """Reconfigure stdout for UTF-8 when possible (Windows)."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def url_to_slug(url: str) -> str:
    """Return slug for filename from URL (e.g. .../makale/slug-123 -> slug-123)."""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path[:-5] if path.endswith(".html") else path
