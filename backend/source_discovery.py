from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

from .config import settings


# India + Asia focused source allowlist. These are used for targeted searches,
# not as a claim that every article from a source is automatically true.
TRUSTED_SOURCE_DOMAINS: dict[str, str] = {
    "Times of India": "timesofindia.indiatimes.com",
    "BBC News": "bbc.com",
    "NDTV": "ndtv.com",
    "The Hindu": "thehindu.com",
    "Indian Express": "indianexpress.com",
    "Hindustan Times": "hindustantimes.com",
    "Reuters": "reuters.com",
    "Associated Press": "apnews.com",
    "ANI": "aninews.in",
    "PTI": "ptinews.com",
    "Al Jazeera": "aljazeera.com",
    "CNA": "channelnewsasia.com",
    "Nikkei Asia": "asia.nikkei.com",
    "Dawn": "dawn.com",
    "The Straits Times": "straitstimes.com",
    "South China Morning Post": "scmp.com",
}

# RSS feeds are best-effort discovery only. For production/commercial use, check
# each publisher's terms and prefer licensed APIs.
RSS_FEEDS: dict[str, str] = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Asia": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "TOI Top Stories": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "TOI India": "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
    "NDTV Top Stories": "https://feeds.feedburner.com/ndtvnews-top-stories",
    "NDTV India": "https://feeds.feedburner.com/ndtvnews-india-news",
    "The Hindu National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "The Hindu International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Indian Express India": "https://indianexpress.com/section/india/feed/",
    "Indian Express World": "https://indianexpress.com/section/world/feed/",
}


class SourceDiscoveryError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_claim_for_search(text: str, max_words: int = 16) -> str:
    """Make a compact query from a claim without losing key entities."""
    cleaned = re.sub(r"https?://\S+", " ", text or "")
    cleaned = re.sub(r"[^\w\s\-.,:/]", " ", cleaned, flags=re.UNICODE)
    words = [w for w in cleaned.split() if len(w) > 2]
    return " ".join(words[:max_words]).strip() or cleaned[:160]


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _dedupe(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in results:
        url = item.get("url") or item.get("link") or ""
        key = url.strip().lower() or hashlib.sha256(str(item).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        item.setdefault("domain", _domain(url))
        unique.append(item)
    return unique


def search_google_cse(query: str, site_domains: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Search Google Programmable Search JSON API if configured."""
    if not settings.GOOGLE_CSE_API_KEY or not settings.GOOGLE_CSE_ID:
        return []

    results: list[dict[str, Any]] = []
    domain_expr = " OR ".join([f"site:{d}" for d in site_domains or []])
    q = f"({domain_expr}) {query}" if domain_expr else query
    params = {
        "key": settings.GOOGLE_CSE_API_KEY,
        "cx": settings.GOOGLE_CSE_ID,
        "q": q,
        "num": min(limit, 10),
    }
    resp = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("items", [])[:limit]:
        results.append({
            "provider": "google_cse",
            "source": item.get("displayLink") or _domain(item.get("link", "")),
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
            "published_at": None,
            "retrieved_at": utc_now(),
        })
    return results


def search_gdelt(query: str, limit: int = 25, timespan: str = "30d") -> list[dict[str, Any]]:
    """Search GDELT DOC API, no key required."""
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": min(limit, 75),
        "sort": "HybridRel",
        "timespan": timespan,
    }
    resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=25)
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except ValueError:
        return []

    results = []
    for item in data.get("articles", [])[:limit]:
        url = item.get("url")
        results.append({
            "provider": "gdelt",
            "source": item.get("domain") or _domain(url or ""),
            "title": item.get("title"),
            "url": url,
            "snippet": item.get("seendate") or item.get("language"),
            "published_at": item.get("seendate"),
            "language": item.get("language"),
            "country": item.get("sourcecountry"),
            "retrieved_at": utc_now(),
        })
    return results


def search_newsapi(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Optional NewsAPI discovery if NEWSAPI_KEY is configured."""
    if not settings.NEWSAPI_KEY:
        return []
    params = {
        "q": query,
        "language": "en",
        "pageSize": min(limit, 100),
        "sortBy": "relevancy",
        "apiKey": settings.NEWSAPI_KEY,
    }
    resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("articles", [])[:limit]:
        url = item.get("url")
        results.append({
            "provider": "newsapi",
            "source": (item.get("source") or {}).get("name") or _domain(url or ""),
            "title": item.get("title"),
            "url": url,
            "snippet": item.get("description"),
            "published_at": item.get("publishedAt"),
            "retrieved_at": utc_now(),
        })
    return results


def search_factcheck_api(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Google Fact Check Tools API if configured."""
    if not settings.FACT_CHECK_API_KEY:
        return []
    params = {
        "query": query,
        "key": settings.FACT_CHECK_API_KEY,
        "languageCode": "en",
        "pageSize": min(limit, 50),
    }
    resp = requests.get("https://factchecktools.googleapis.com/v1alpha1/claims:search", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for claim in data.get("claims", [])[:limit]:
        for review in claim.get("claimReview", []) or [{}]:
            url = review.get("url")
            results.append({
                "provider": "google_factcheck",
                "source": (review.get("publisher") or {}).get("name") or _domain(url or ""),
                "title": review.get("title") or claim.get("text"),
                "url": url,
                "snippet": review.get("textualRating") or claim.get("claimant"),
                "published_at": review.get("reviewDate") or claim.get("claimDate"),
                "retrieved_at": utc_now(),
            })
    return results


def search_rss_feeds(query: str, limit_per_feed: int = 4) -> list[dict[str, Any]]:
    """Best-effort RSS search by title/summary keyword overlap."""
    terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]{4,}", query)}
    if not terms:
        return []
    results: list[dict[str, Any]] = []
    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        matched = 0
        for entry in feed.entries[:60]:
            haystack = f"{getattr(entry, 'title', '')} {getattr(entry, 'summary', '')}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score <= 0:
                continue
            url = getattr(entry, "link", None)
            results.append({
                "provider": "rss",
                "source": feed_name,
                "title": getattr(entry, "title", None),
                "url": url,
                "snippet": re.sub("<[^>]+>", " ", getattr(entry, "summary", ""))[:500],
                "published_at": getattr(entry, "published", None),
                "retrieved_at": utc_now(),
                "keyword_overlap_score": score,
            })
            matched += 1
            if matched >= limit_per_feed:
                break
    return results


def discover_sources_for_claim(claim: str, max_results: int = 40) -> dict[str, Any]:
    query = normalize_claim_for_search(claim)
    target_domains = list(TRUSTED_SOURCE_DOMAINS.values())
    errors: list[str] = []
    results: list[dict[str, Any]] = []

    for fn, kwargs in [
        (search_factcheck_api, {"limit": 10}),
        (search_google_cse, {"site_domains": target_domains, "limit": 10}),
        (search_newsapi, {"limit": 15}),
        (search_gdelt, {"limit": 25}),
        (search_rss_feeds, {"limit_per_feed": 3}),
    ]:
        try:
            results.extend(fn(query, **kwargs))
        except Exception as exc:
            errors.append(f"{fn.__name__}: {exc}")

    unique = _dedupe(results)
    # Prefer fact-check results and trusted domains before general GDELT/NewsAPI results.
    def rank(item: dict[str, Any]) -> tuple[int, int]:
        provider_rank = {"google_factcheck": 0, "google_cse": 1, "rss": 2, "newsapi": 3, "gdelt": 4}.get(item.get("provider"), 9)
        trusted = 0 if any(item.get("domain", "").endswith(d) for d in target_domains) else 1
        return (provider_rank, trusted)

    unique.sort(key=rank)
    return {
        "claim": claim,
        "search_query": query,
        "retrieved_at": utc_now(),
        "results": unique[:max_results],
        "errors": errors,
        "configured_providers": {
            "google_cse": bool(settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID),
            "google_factcheck": bool(settings.FACT_CHECK_API_KEY),
            "newsapi": bool(settings.NEWSAPI_KEY),
            "gdelt": True,
            "rss": True,
        },
    }
