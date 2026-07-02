from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import settings


@lru_cache(maxsize=1)
def _image_classifier():
    """Lazy-loaded local ViT deepfake classifier (downloaded once, cached by HF on disk)."""
    from transformers import pipeline

    return pipeline("image-classification", model=settings.FORENSIC_IMAGE_MODEL)


@lru_cache(maxsize=1)
def _text_classifier():
    """Lazy-loaded local AI-generated-text classifier."""
    from transformers import pipeline

    return pipeline(
        "text-classification",
        model=settings.FORENSIC_TEXT_MODEL,
        truncation=True,
        max_length=512,
    )


def _label_probability(scores: list[dict[str, Any]], label: str) -> float:
    for item in scores:
        if str(item.get("label", "")).lower() == label.lower():
            return float(item["score"])
    return 0.0


def detect_image_deepfake(image_path: str) -> dict[str, Any]:
    """Classify a single image as Real/Fake using a local, free, offline-capable model."""
    from PIL import Image

    classifier = _image_classifier()
    with Image.open(image_path) as img:
        scores = classifier(img.convert("RGB"), top_k=None)

    fake_probability = _label_probability(scores, "Fake")
    return {
        "model": settings.FORENSIC_IMAGE_MODEL,
        "label": "Fake" if fake_probability >= 0.5 else "Real",
        "fake_probability": round(fake_probability, 4),
        "raw_scores": scores,
    }


def detect_video_deepfake(video_path: str, max_frames: int | None = None) -> dict[str, Any]:
    """Sample frames across the video and run the image classifier on each, then aggregate."""
    import cv2
    from PIL import Image

    max_frames = max_frames or settings.FORENSIC_VIDEO_MAX_FRAMES
    classifier = _image_classifier()

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0

    if total_frames <= 0:
        cap.release()
        return {
            "model": settings.FORENSIC_IMAGE_MODEL,
            "error": "Could not read any frames from this video file.",
            "frames_analyzed": 0,
        }

    sample_count = min(max_frames, total_frames)
    frame_indices = sorted({int(i * total_frames / sample_count) for i in range(sample_count)})

    frame_results: list[dict[str, Any]] = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        scores = classifier(Image.fromarray(rgb_frame), top_k=None)
        fake_probability = _label_probability(scores, "Fake")
        frame_results.append({
            "frame_index": idx,
            "timestamp_seconds": round(idx / fps, 2) if fps else None,
            "fake_probability": round(fake_probability, 4),
        })
    cap.release()

    if not frame_results:
        return {
            "model": settings.FORENSIC_IMAGE_MODEL,
            "error": "Frames were located but none could be decoded.",
            "frames_analyzed": 0,
        }

    fake_probabilities = [f["fake_probability"] for f in frame_results]
    average_fake = sum(fake_probabilities) / len(fake_probabilities)
    worst_frame = max(frame_results, key=lambda f: f["fake_probability"])

    return {
        "model": settings.FORENSIC_IMAGE_MODEL,
        "frames_analyzed": len(frame_results),
        "average_fake_probability": round(average_fake, 4),
        "max_fake_probability": worst_frame["fake_probability"],
        "most_suspicious_frame": worst_frame,
        "label": "Fake" if average_fake >= 0.5 or worst_frame["fake_probability"] >= 0.85 else "Real",
        "per_frame": frame_results,
    }


def detect_ai_generated_text(text: str) -> dict[str, Any] | None:
    """Classify text as Human/AI-generated. Returns None for text too short to be meaningful."""
    cleaned = (text or "").strip()
    if len(cleaned) < settings.FORENSIC_TEXT_MIN_CHARS:
        return None

    classifier = _text_classifier()
    scores = classifier(cleaned[:4000], top_k=None)
    ai_probability = _label_probability(scores, "ChatGPT")
    return {
        "model": settings.FORENSIC_TEXT_MODEL,
        "label": "AI-generated" if ai_probability >= 0.5 else "Human-written",
        "ai_generated_probability": round(ai_probability, 4),
        "raw_scores": scores,
    }
