# DeepShield AI

A local MVP for checking news credibility in India and Asia using Gemini media understanding, dedicated
local deepfake/AI-text classifiers, free web search/corroboration, and multi-source comparison.

> **Runs fully free by default.** Gemini's `google_search` / `url_context` grounding tools are billed beyond a
> small free quota, so they are **off by default** (`ENABLE_GEMINI_SEARCH_GROUNDING=False`,
> `ENABLE_GEMINI_URL_CONTEXT=False` in `.env`). In their place:
> - **Image/video deepfake detection** runs on a local, free, offline-capable Hugging Face model
>   ([`dima806/deepfake_vs_real_image_detection`](https://huggingface.co/dima806/deepfake_vs_real_image_detection)),
>   not an LLM guess — this is also a better fit for a research project since it's a purpose-built forensic
>   classifier, not a general-purpose chatbot reasoning about pixels.
> - **AI-generated text detection** runs on a local, free model
>   ([`Hello-SimpleAI/chatgpt-detector-roberta`](https://huggingface.co/Hello-SimpleAI/chatgpt-detector-roberta)).
> - **Web corroboration/search** uses free DuckDuckGo search plus the existing free GDELT/RSS/Fact Check
>   sources, instead of Gemini's paid search grounding.
> - Gemini itself is still used (for multimodal understanding and report writing) on its normal free-tier
>   quota — only the paid *tools* were removed. If you later enable Gemini billing, you can flip the two
>   `ENABLE_GEMINI_*` flags back to `True` to restore Gemini's own grounding.

It can analyze:

- Public news URLs and social/news links
- Written claims/headlines/captions
- News screenshots, images, videos, audio clips, PDFs, and text files
- India and Asia-focused claims, including old-content reuse, local context, communal/political framing, and source reliability

> Important: this creates an **AI-assisted evidence-grade verification report**, not final legal proof. Courts, police, lawyers, newsroom editors, and qualified human experts decide legal proof. The tool preserves evidence metadata, hashes, source URLs, citations, and reasoning to support human review.

## What is new in v0.3

1. **Local, free forensic classifiers replace paid Gemini grounding**
   - Image/video deepfake risk: local ViT classifier, runs offline after first download
   - AI-generated text risk: local RoBERTa classifier for claims and fetched article text
   - Both attach a `local_forensic_model` section to every result, with raw model scores

## What is new in v0.2

1. **Multi-source comparison**
   - Local article text extraction (no Gemini URL Context tool needed)
   - Free DuckDuckGo web search
   - Google Programmable Search / Custom Search JSON API when configured
   - Google Fact Check Tools API when configured
   - NewsAPI when configured
   - GDELT DOC API, no key required
   - RSS feeds from selected India/Asia/world sources where available

2. **Source discovery from trusted news domains**
   - Times of India
   - BBC News
   - NDTV
   - The Hindu
   - Indian Express
   - Hindustan Times
   - Reuters
   - Associated Press
   - ANI/PTI
   - Al Jazeera
   - CNA
   - Nikkei Asia
   - Dawn
   - The Straits Times
   - South China Morning Post

3. **Evidence bundle**
   - JSON report generated for every analysis
   - Report ID
   - UTC timestamp
   - Source discovery list
   - Model result
   - Uploaded media SHA-256 hash
   - Evidence bundle SHA-256 hash
   - Legal-use limitations and audit notes

4. **Legal evidence grade**
   - A: Primary/official record + multiple independent credible reports + preserved evidence bundle
   - B: Multiple independent credible reports and fact-check/official support, but incomplete primary records
   - C: Partly corroborated, but missing primary confirmation or strong independence
   - D: Weak/conflicting evidence, old/reused content, mostly social reposts
   - E: No reliable corroboration or strong evidence of false/manipulated content

## Setup

```bash
cd deepshield-ai
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# torch (needed by the local deepfake/AI-text classifiers) is installed separately as a
# CPU-only build to avoid pulling multi-GB CUDA packages you don't need for this project:
pip install torch --index-url https://download.pytorch.org/whl/cpu

cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_key_here
```

For stronger evidence checks, also add optional keys:

```env
GOOGLE_CSE_API_KEY=your_google_custom_search_json_api_key
GOOGLE_CSE_ID=your_programmable_search_engine_id
FACT_CHECK_API_KEY=your_google_fact_check_tools_api_key
NEWSAPI_KEY=your_newsapi_key
```

GDELT, RSS, and DuckDuckGo checks work without extra keys.

The first time you analyze an image, video, or claim/URL, the local classifiers will download their model
weights from Hugging Face automatically (roughly 300–500 MB total) and cache them under
`~/.cache/huggingface`. That first request will be slow (tens of seconds); every request after that is fast
since the models stay loaded in memory for the life of the server process.

Run:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

## API endpoints

### Analyze URL

```bash
curl -X POST http://localhost:8000/api/analyze-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/news", "user_note":"Viral on WhatsApp as breaking news"}'
```

### Verify written claim

```bash
curl -X POST http://localhost:8000/api/verify-claim \
  -H "Content-Type: application/json" \
  -d '{"claim_text":"A viral post claims that ...", "user_note":"Seen on Instagram"}'
```

### Analyze media

```bash
curl -X POST http://localhost:8000/api/analyze-media \
  -F "file=@/path/to/news-video.mp4" \
  -F "user_note=Claims this happened today in India"
```

### Download evidence bundle

Every result includes:

```json
"evidence_bundle": {
  "report_id": "...",
  "bundle_sha256": "...",
  "evidence_file": "evidence_reports/....json"
}
```

Download it locally:

```bash
curl http://localhost:8000/api/evidence/REPORT_ID
```

## Why this is not called “legal proof”

The tool can support legal/newsroom review by keeping a structured audit trail. But it cannot guarantee admissibility, authorship, chain of custody before upload, or intent. For actual legal use:

- Preserve the original file or URL evidence exactly as received.
- Save screenshots/PDF snapshots of source pages with timestamps.
- Keep device/source chain-of-custody records.
- Get a qualified human reviewer, lawyer, editor, police/cyber expert, or court-appointed expert to sign off.
- Use official records where possible.

## Production upgrade checklist

- Add login/authentication.
- Store reports in Postgres/S3 with immutability controls.
- Add Redis/Celery for long video jobs.
- Add OCR preprocessing for screenshots in Indian languages.
- Add perceptual image hashing and video keyframe hashing for duplicate/old-image detection.
- Add Google Lens / reverse-image-search workflow, subject to available APIs and terms.
- Add publisher licensing or official APIs for commercial use.
- Add human review workflow for elections, communal violence, public health, financial scams, national security, and legal disputes.

## Live API note

Gemini Live API is for real-time camera/microphone streaming over WebSockets and is **not used anywhere in
this codebase** — `GEMINI_LIVE_MODEL` and `/api/live-info` are placeholders for a future feature, not an
active integration. All current analysis (`/api/analyze-url`, `/api/verify-claim`, `/api/analyze-media`) uses
one-shot Gemini calls plus the local classifiers described above, not the Live API. If you build a WebSocket
proxy for browser camera/mic later, keep the API key server-side and never expose it in frontend JavaScript.

## Local forensic classifier notes

- `dima806/deepfake_vs_real_image_detection` and `Hello-SimpleAI/chatgpt-detector-roberta` are general-purpose
  research models, not perfect detectors — treat their scores as one signal among several (alongside the
  Gemini reasoning and multi-source corroboration), not a final verdict. This mirrors how the rest of the
  report already treats `legal_evidence_grade` as evidence-grade, not proof.
- Both run on CPU by default; if you have a CUDA GPU available, install the matching `torch` CUDA build
  instead of the CPU wheel for faster inference, especially for video (which classifies multiple frames).
- Swap either model via `FORENSIC_IMAGE_MODEL` / `FORENSIC_TEXT_MODEL` in `.env` if you find a better-performing
  one for your dataset (e.g. a model fine-tuned specifically on FaceForensics++/DFDC for your region's content).
