from __future__ import annotations

from typing import Any

import trafilatura


def fetch_readable_text(url: str, max_chars: int = 12000) -> dict[str, Any]:
    """Download a URL and extract its main article text locally, free, no API key."""
    try:
        downloaded = trafilatura.fetch_url(url)
    except Exception as exc:
        return {"url": url, "title": None, "text": "", "truncated": False, "error": str(exc)}

    if not downloaded:
        return {"url": url, "title": None, "text": "", "truncated": False, "error": "Could not download page"}

    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
    metadata = trafilatura.extract_metadata(downloaded)
    title = getattr(metadata, "title", None) if metadata else None

    return {
        "url": url,
        "title": title,
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "error": None if text else "Page downloaded but no readable article text was found",
    }
