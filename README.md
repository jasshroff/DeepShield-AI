# DeepShield AI

A local MVP for checking news credibility in India and Asia using Gemini URL Context, Google Search grounding, Gemini media understanding, and multi-source corroboration.

It can analyze:

- Public news URLs and social/news links
- Written claims/headlines/captions
- News screenshots, images, videos, audio clips, PDFs, and text files
- India and Asia-focused claims, including old-content reuse, local context, communal/political framing, and source reliability

> Important: this creates an **AI-assisted evidence-grade verification report**, not final legal proof. Courts, police, lawyers, newsroom editors, and qualified human experts decide legal proof. The tool preserves evidence metadata, hashes, source URLs, citations, and reasoning to support human review.

## What is new in v0.2

1. **Multi-source comparison**
   - Google URL Context + Google Search grounding
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

GDELT and RSS checks work without extra keys.

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

Gemini Live API is for real-time camera/microphone streaming over WebSockets. For uploaded media files, the standard media analysis flow is simpler, cheaper, and easier to audit. Add a server-side WebSocket proxy only if you want live fact-checking from browser camera/mic; do not expose your Gemini API key in frontend JavaScript.
