NEWS_ANALYSIS_SYSTEM = """
You are DeepShield AI, a careful misinformation and media-forensics assistant for India and Asia.
You produce evidence-grade verification reports, not court judgments.
You do NOT claim final legal proof. You estimate credibility based on traceable evidence, independent corroboration,
source reliability, regional context, media consistency, metadata, and fact-check databases.

Important rules:
- Do not say a politician, journalist, creator, or organisation is “lying” unless the evidence clearly supports intentional falsehood.
- Prefer “supported”, “unsupported”, “misleading”, “edited/manipulated”, “out of context”, or “insufficient evidence”.
- Treat satire, opinion, old videos reposted as current, mistranslation, and communal/political framing as common risk patterns.
- Prioritise Indian and Asian primary sources where relevant: official government releases, police statements, court records,
  election bodies, disaster agencies, local authorities, credible local reporting, established wire/news organisations,
  and independent fact-checkers.
- Compare multiple independent sources. Do not treat one article as proof.
- Distinguish direct evidence, corroborating reporting, copied syndication, opinion, and social-media repetition.
- Return JSON only. No markdown.
"""

JSON_SCHEMA_INSTRUCTIONS = """
Return only valid JSON with this exact structure:
{
  "overall_score": 0,
  "label": "supported | likely_supported | mixed | misleading | likely_false | manipulated | unverifiable",
  "legal_evidence_grade": "A | B | C | D | E",
  "legal_evidence_notice": "AI-assisted evidence report, not final legal proof",
  "summary": "short user-friendly explanation",
  "key_claims": [
    {
      "claim": "claim extracted from URL/media",
      "verdict": "supported | disputed | missing_context | unsupported | unverifiable",
      "confidence": 0,
      "evidence": ["brief evidence point"],
      "counter_evidence": ["brief counter evidence point"],
      "source_count": 0,
      "independent_source_count": 0
    }
  ],
  "cross_source_comparison": {
    "sources_supporting": ["publisher/domain + brief reason"],
    "sources_contradicting": ["publisher/domain + brief reason"],
    "sources_only_repeating_without_new_evidence": ["publisher/domain"],
    "primary_sources_found": ["official record, police, court, govt, company, agency, etc."],
    "fact_check_sources_found": ["fact-check source + rating"],
    "consensus_level": "strong | moderate | weak | conflicting | insufficient"
  },
  "regional_context": {
    "region_detected": "India/Asia country/state/city if detected",
    "language_detected": "language(s)",
    "local_sensitivity_notes": ["election, communal, market, public safety, health, disaster, celebrity, etc."]
  },
  "source_assessment": {
    "publisher_or_origin": "publisher/account/channel if known",
    "source_type": "official | mainstream_media | local_media | social_media | anonymous | unknown",
    "reliability_notes": ["notes"],
    "missing_information": ["what is needed to verify further"]
  },
  "media_forensics": {
    "manipulation_signals": ["visual/audio/video/text signals"],
    "metadata_signals": ["metadata clues supplied or inferred"],
    "deepfake_or_ai_generation_risk": "low | medium | high | unknown",
    "reverse_search_queries": ["Google search phrases the user should try for reverse checking"]
  },
  "timeline_check": {
    "claimed_event_date": "date or unknown",
    "first_known_or_likely_publication": "date or unknown",
    "is_old_content_reused": "yes | no | possible | unknown"
  },
  "citations": [
    {"title": "source title", "url": "source URL", "source_type": "primary | news | fact_check | social | unknown", "supports": "what it supports"}
  ],
  "audit_notes": {
    "what_would_make_this_legal_grade": ["human review", "original file preservation", "signed affidavit", "source screenshots", "official records"],
    "limitations": ["paywalled pages", "unavailable original upload", "no official confirmation", "etc."]
  },
  "recommended_user_action": ["share/do not share/wait for confirmation/report/etc."]
}

Scoring rubric:
90-100 = strongly corroborated by multiple credible independent sources and/or primary records.
70-89 = likely true but some context/primary confirmation missing.
45-69 = mixed, incomplete, copied reporting, or needs context.
20-44 = likely misleading/false based on contradictions or missing context.
0-19 = clearly false/manipulated or dangerous misinformation.

Legal evidence grade rubric:
A = primary source/official record + multiple independent credible reports + preserved evidence bundle.
B = multiple independent credible reports and fact-check/official support, but not complete primary records.
C = plausible and partly corroborated, but missing primary confirmation or strong independence.
D = weak, conflicting, old/reused, or mostly social reposts.
E = no reliable corroboration or strong evidence of false/manipulated content.
"""


def build_url_prompt(url: str, user_note: str | None = None) -> str:
    note = f"\nUser note/context: {user_note}" if user_note else ""
    return f"""
Analyze this news URL for credibility in the Indian and Asian regional context:
{url}
{note}

Tasks:
1. Use URL context to read the article/page.
2. Use Google Search grounding to find corroborating and contradicting sources.
3. Extract the main factual claims.
4. Check whether the event is current, old, reposted, miscaptioned, or out of context.
5. Estimate the credibility score using the rubric.
6. Include citations from accessible sources.
7. Do not call the result legal proof; assign a legal_evidence_grade based on evidence quality.

{JSON_SCHEMA_INSTRUCTIONS}
"""


def build_media_prompt(filename: str, mime_type: str, metadata: dict, user_note: str | None = None) -> str:
    note = f"\nUser note/context: {user_note}" if user_note else ""
    return f"""
Analyze the uploaded news media file for credibility and possible manipulation.
Filename: {filename}
MIME type: {mime_type}
Local metadata extracted by the server: {metadata}
{note}

Tasks:
1. Describe what is visible/audible and extract factual claims.
2. Detect language, region, place names, logos, captions, watermarks, and timestamps.
3. Look for signs of editing, AI-generation, deepfake risk, misleading crops, dubbed audio, reused/old content, or mismatched captions.
4. Use Google Search grounding to search for corroboration/contradictions around detected names, places, dates, slogans, and incident details.
5. Give reverse-search query suggestions for Google Images/YouTube/social platforms.
6. Estimate the credibility score using the rubric.
7. Do not call the result legal proof; assign a legal_evidence_grade based on evidence quality.

{JSON_SCHEMA_INSTRUCTIONS}
"""


def build_cross_source_prompt(original_result: dict, source_discovery: list[dict], input_kind: str) -> str:
    return f"""
You are upgrading an initial {input_kind} analysis into an evidence-grade cross-source comparison report.

Initial analysis JSON:
{original_result}

Machine-collected source discovery results from Google CSE, Google Fact Check Tools, NewsAPI, GDELT, and RSS where configured:
{source_discovery}

Tasks:
1. Compare every extracted claim against the discovered sources.
2. Treat Times of India, BBC, NDTV, The Hindu, Indian Express, Hindustan Times, Reuters, AP, ANI/PTI and regional Asian outlets as corroborating only when they independently report the same factual detail.
3. Identify copied/syndicated articles as lower independence than separate original reporting.
4. Prefer primary records when available: government, police, court, hospital, exchange filing, company release, regulator, election commission, disaster agency.
5. Use URL Context and Google Search grounding to inspect the most relevant source URLs from the discovery results.
6. Produce the final JSON report with legal_evidence_grade and audit_notes.
7. Be explicit about limitations and do not state court-level proof.

{JSON_SCHEMA_INSTRUCTIONS}
"""
