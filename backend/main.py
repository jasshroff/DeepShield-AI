from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from .config import settings
from .gemini_client import LIVE_SESSION_NOTE, analyze_claim_text, analyze_media, analyze_url
from .utils import extract_local_metadata, get_upload_limit_bytes, guess_mime


app = FastAPI(
    title="DeepShield AI",
    description="Evidence-grade credibility scoring for news URLs and uploaded media using Gemini URL Context, Search grounding, source discovery, and media understanding.",
    version="0.2.0",
)

origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class UrlRequest(BaseModel):
    url: HttpUrl
    user_note: str | None = None


class ClaimRequest(BaseModel):
    claim_text: str
    user_note: str | None = None


@app.get("/", response_class=HTMLResponse)
def home() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "DeepShield AI",
        "version": "0.2.0",
        "providers": {
            "gemini": bool(settings.GEMINI_API_KEY),
            "gemini_search_grounding_paid_tool": settings.ENABLE_GEMINI_SEARCH_GROUNDING,
            "gemini_url_context_paid_tool": settings.ENABLE_GEMINI_URL_CONTEXT,
            "local_deepfake_image_video_classifier": True,
            "local_ai_text_classifier": True,
            "duckduckgo": True,
            "google_cse": bool(settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID),
            "google_factcheck": bool(settings.FACT_CHECK_API_KEY),
            "newsapi": bool(settings.NEWSAPI_KEY),
            "gdelt": True,
            "rss": True,
        },
    }


@app.post("/api/analyze-url")
def analyze_news_url(payload: UrlRequest) -> dict:
    try:
        result = analyze_url(str(payload.url), payload.user_note)
        return {"type": "url", "input": str(payload.url), "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/verify-claim")
def verify_claim(payload: ClaimRequest) -> dict:
    if len(payload.claim_text.strip()) < 8:
        raise HTTPException(status_code=400, detail="Please enter a more specific claim.")
    try:
        result = analyze_claim_text(payload.claim_text, payload.user_note)
        return {"type": "claim_text", "input": payload.claim_text, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze-media")
async def analyze_news_media(
    file: Annotated[UploadFile, File(...)],
    user_note: Annotated[str | None, Form()] = None,
) -> dict:
    contents = await file.read()
    if len(contents) > get_upload_limit_bytes(settings.MAX_UPLOAD_MB):
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.MAX_UPLOAD_MB} MB")

    suffix = os.path.splitext(file.filename or "upload.bin")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        mime_type = guess_mime(tmp_path, file.content_type)
        metadata = extract_local_metadata(tmp_path, mime_type)
        result = analyze_media(tmp_path, file.filename or "upload", mime_type, metadata, user_note)
        return {"type": "media", "filename": file.filename, "mime_type": mime_type, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@app.get("/api/evidence/{report_id}")
def download_evidence_report(report_id: str) -> FileResponse:
    safe_id = "".join(ch for ch in report_id if ch.isalnum() or ch in {"-", "_"})
    if safe_id != report_id or not safe_id:
        raise HTTPException(status_code=400, detail="Invalid report id")

    path = Path(settings.EVIDENCE_DIR) / f"{safe_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence report not found")
    return FileResponse(str(path), media_type="application/json", filename=f"newscred-evidence-{safe_id}.json")


@app.get("/api/live-info")
def live_info() -> dict:
    return {
        "status": "design_ready",
        "note": LIVE_SESSION_NOTE,
        "model": settings.GEMINI_LIVE_MODEL,
        "next_step": "Add a backend WebSocket proxy only if you want real-time camera/mic analysis.",
    }
