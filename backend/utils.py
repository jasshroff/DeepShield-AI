import json
import mimetypes
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ExifTags


IMAGE_MIME_PREFIX = "image/"
AUDIO_MIME_PREFIX = "audio/"
VIDEO_MIME_PREFIX = "video/"
DOCUMENT_MIME_TYPES = {"application/pdf", "text/plain"}


def guess_mime(path: str, supplied: str | None = None) -> str:
    if supplied and supplied != "application/octet-stream":
        return supplied
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def gemini_part_type(mime_type: str) -> str:
    if mime_type.startswith(IMAGE_MIME_PREFIX):
        return "image"
    if mime_type.startswith(AUDIO_MIME_PREFIX):
        return "audio"
    if mime_type.startswith(VIDEO_MIME_PREFIX):
        return "video"
    if mime_type in DOCUMENT_MIME_TYPES or mime_type.startswith("text/"):
        return "document"
    raise ValueError(f"Unsupported media type: {mime_type}")


def extract_local_metadata(path: str, mime_type: str) -> dict[str, Any]:
    p = Path(path)
    data: dict[str, Any] = {
        "filename": p.name,
        "size_bytes": p.stat().st_size if p.exists() else None,
        "mime_type": mime_type,
    }

    if mime_type.startswith("image/"):
        try:
            with Image.open(path) as img:
                data.update({
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                })
                exif = img.getexif()
                if exif:
                    decoded = {}
                    for k, v in exif.items():
                        tag = ExifTags.TAGS.get(k, str(k))
                        # Keep metadata compact and JSON-safe.
                        decoded[tag] = str(v)[:300]
                    data["exif"] = decoded
        except Exception as exc:  # metadata is helpful but should not block analysis
            data["image_metadata_error"] = str(exc)

    if mime_type.startswith("video/") or mime_type.startswith("audio/"):
        # Optional: if ffprobe exists, collect duration/codec metadata.
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                meta = json.loads(result.stdout)
                data["ffprobe"] = {
                    "format": meta.get("format", {}),
                    "streams": [
                        {
                            "codec_type": s.get("codec_type"),
                            "codec_name": s.get("codec_name"),
                            "width": s.get("width"),
                            "height": s.get("height"),
                            "duration": s.get("duration"),
                        }
                        for s in meta.get("streams", [])
                    ],
                }
        except Exception as exc:
            data["ffprobe_error"] = str(exc)

    return data


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Parse strict JSON or recover from a fenced/model response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def get_upload_limit_bytes(max_mb: int) -> int:
    return max_mb * 1024 * 1024
