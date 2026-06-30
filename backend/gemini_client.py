from __future__ import annotations

from typing import Any

from google import genai

from .config import settings
from .evidence import save_evidence_bundle, sha256_file
from .prompts import (
    NEWS_ANALYSIS_SYSTEM,
    build_cross_source_prompt,
    build_media_prompt,
    build_url_prompt,
)
from .source_discovery import discover_sources_for_claim
from .utils import extract_json_from_text, gemini_part_type


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _response_text(interaction: Any) -> str:
    """Extract text from the Interactions API response across SDK versions."""
    if getattr(interaction, "output_text", None):
        return interaction.output_text

    chunks: list[str] = []
    for step in getattr(interaction, "steps", []) or []:
        if getattr(step, "type", None) == "model_output":
            for block in getattr(step, "content", []) or []:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    chunks.append(block.text)
    if not chunks:
        # Some SDK versions expose candidates/content instead of Interactions steps.
        text = getattr(interaction, "text", None)
        if text:
            return text
        chunks.append(str(interaction))
    return "\n".join(chunks)


def _extract_citations(interaction: Any) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    for step in getattr(interaction, "steps", []) or []:
        for block in getattr(step, "content", []) or []:
            for ann in getattr(block, "annotations", []) or []:
                if getattr(ann, "type", None) == "url_citation":
                    citations.append({
                        "title": getattr(ann, "title", "Source"),
                        "url": getattr(ann, "url", ""),
                        "source_type": "news",
                        "supports": "Gemini source annotation",
                    })
    return citations


def _merge_annotations(parsed: dict[str, Any], interaction: Any) -> dict[str, Any]:
    annotations = _extract_citations(interaction)
    if annotations:
        existing = parsed.get("citations") or []
        seen = {c.get("url") for c in existing if isinstance(c, dict)}
        for ann in annotations:
            if ann.get("url") not in seen:
                existing.append(ann)
        parsed["citations"] = existing
    return parsed


def _run_interaction(prompt: str, *, tools: list[dict[str, Any]], input_payload: Any | None = None) -> tuple[dict[str, Any], Any, str]:
    interaction = client.interactions.create(
        model=settings.GEMINI_MODEL,
        input=input_payload if input_payload is not None else prompt,
        tools=tools,
    )
    raw = _response_text(interaction)
    parsed = extract_json_from_text(raw)
    parsed = _merge_annotations(parsed, interaction)
    return parsed, interaction, raw


def _claims_from_result(result: dict[str, Any], fallback: str) -> list[str]:
    claims: list[str] = []
    for item in result.get("key_claims", []) or []:
        if isinstance(item, dict) and item.get("claim"):
            claims.append(str(item["claim"]))
    if not claims and result.get("summary"):
        claims.append(str(result["summary"]))
    if not claims:
        claims.append(fallback)
    return claims[:5]


def _discover_for_result(result: dict[str, Any], fallback: str) -> list[dict[str, Any]]:
    discoveries: list[dict[str, Any]] = []
    for claim in _claims_from_result(result, fallback):
        discoveries.append(discover_sources_for_claim(claim))
    return discoveries


def _cross_source_finalize(initial_result: dict[str, Any], source_discovery: list[dict[str, Any]], input_kind: str) -> dict[str, Any]:
    prompt = NEWS_ANALYSIS_SYSTEM + "\n" + build_cross_source_prompt(initial_result, source_discovery, input_kind)
    final_result, interaction, _raw = _run_interaction(
        prompt,
        tools=[{"type": "url_context"}, {"type": "google_search"}],
    )
    final_result["source_discovery"] = source_discovery
    final_result["initial_model_result"] = initial_result
    return final_result


def analyze_url(url: str, user_note: str | None = None) -> dict[str, Any]:
    prompt = NEWS_ANALYSIS_SYSTEM + "\n" + build_url_prompt(url, user_note)
    initial_result, _interaction, raw = _run_interaction(
        prompt,
        tools=[{"type": "url_context"}, {"type": "google_search"}],
    )

    source_discovery = _discover_for_result(initial_result, fallback=url)
    final_result = _cross_source_finalize(initial_result, source_discovery, "URL")
    bundle_meta = save_evidence_bundle(
        input_type="url",
        input_summary={"url": url, "user_note": user_note},
        source_discovery=source_discovery,
        model_result=final_result,
    )
    final_result["evidence_bundle"] = bundle_meta
    final_result["raw_initial_model_text"] = raw if not isinstance(initial_result, dict) else None
    return final_result


def analyze_claim_text(claim_text: str, user_note: str | None = None) -> dict[str, Any]:
    pseudo_initial = {
        "overall_score": 0,
        "label": "unverifiable",
        "legal_evidence_grade": "E",
        "legal_evidence_notice": "AI-assisted evidence report, not final legal proof",
        "summary": user_note or "User supplied claim for multi-source comparison.",
        "key_claims": [{"claim": claim_text, "verdict": "unverifiable", "confidence": 0, "evidence": [], "counter_evidence": []}],
        "citations": [],
    }
    source_discovery = [discover_sources_for_claim(claim_text)]
    final_result = _cross_source_finalize(pseudo_initial, source_discovery, "claim text")
    bundle_meta = save_evidence_bundle(
        input_type="claim_text",
        input_summary={"claim_text": claim_text, "user_note": user_note},
        source_discovery=source_discovery,
        model_result=final_result,
    )
    final_result["evidence_bundle"] = bundle_meta
    return final_result


def analyze_media(file_path: str, filename: str, mime_type: str, metadata: dict, user_note: str | None = None) -> dict[str, Any]:
    part_type = gemini_part_type(mime_type)
    uploaded = client.files.upload(file=file_path, config={"mime_type": mime_type})
    uploaded_uri = getattr(uploaded, "uri", None)
    uploaded_mime = getattr(uploaded, "mime_type", None) or getattr(uploaded, "mimeType", None) or mime_type
    if not uploaded_uri:
        raise RuntimeError("Gemini file upload did not return a URI.")

    prompt = NEWS_ANALYSIS_SYSTEM + "\n" + build_media_prompt(filename, mime_type, metadata, user_note)
    initial_result, _interaction, raw = _run_interaction(
        prompt,
        input_payload=[
            {"type": "text", "text": prompt},
            {"type": part_type, "uri": uploaded_uri, "mime_type": uploaded_mime},
        ],
        tools=[{"type": "google_search"}],
    )

    source_discovery = _discover_for_result(initial_result, fallback=user_note or filename)
    final_result = _cross_source_finalize(initial_result, source_discovery, "uploaded media")
    media_hash = sha256_file(file_path)
    final_result["server_metadata"] = metadata
    bundle_meta = save_evidence_bundle(
        input_type="media",
        input_summary={"filename": filename, "mime_type": mime_type, "user_note": user_note, "server_metadata": metadata},
        source_discovery=source_discovery,
        model_result=final_result,
        media_file_hash=media_hash,
    )
    final_result["evidence_bundle"] = bundle_meta
    final_result["media_file_sha256"] = media_hash
    final_result["raw_initial_model_text"] = raw if not isinstance(initial_result, dict) else None
    return final_result


LIVE_SESSION_NOTE = """
Optional real-time mode: Use Gemini Live API only when you want browser microphone/camera streaming.
Keep the API key on the server and proxy WebSocket frames from the browser to Gemini Live.
Static URL/image/audio/video analysis should use analyze_url/analyze_media above for cheaper, simpler, auditable results.
"""
