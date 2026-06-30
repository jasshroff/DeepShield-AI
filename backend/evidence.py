from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_report_id(payload: dict[str, Any]) -> str:
    base = stable_json({"time": utc_now(), "payload_hash": sha256_text(stable_json(payload))})
    return sha256_text(base)[:16]


def save_evidence_bundle(
    *,
    input_type: str,
    input_summary: dict[str, Any],
    source_discovery: list[dict[str, Any]],
    model_result: dict[str, Any],
    media_file_hash: str | None = None,
) -> dict[str, Any]:
    """Persist an auditable JSON report and return chain-of-custody metadata."""
    bundle = {
        "schema": "newscred-ai-evidence-bundle-v1",
        "generated_at_utc": utc_now(),
        "input_type": input_type,
        "input_summary": input_summary,
        "media_file_sha256": media_file_hash,
        "source_discovery": source_discovery,
        "model_result": model_result,
        "legal_notice": (
            "This is an evidence-grade AI-assisted verification report. "
            "It is not a court order, affidavit, or final legal proof. "
            "For legal use, preserve original files, URLs, timestamps, and have a qualified human reviewer sign the report."
        ),
    }
    report_id = make_report_id(bundle)
    bundle["report_id"] = report_id
    bundle["bundle_sha256"] = sha256_text(stable_json(bundle))

    out_dir = Path(settings.EVIDENCE_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{report_id}.json"
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "report_id": report_id,
        "generated_at_utc": bundle["generated_at_utc"],
        "bundle_sha256": bundle["bundle_sha256"],
        "evidence_file": str(out_path),
        "legal_notice": bundle["legal_notice"],
    }
