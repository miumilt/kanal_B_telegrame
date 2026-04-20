from __future__ import annotations

import re
from uuid import uuid4

from ai_news_bot.models import BacklogItem
from ai_news_bot.queries import AI_SEARCH_QUERIES


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _get_value(entry, key: str, default: str = "") -> str:
    if hasattr(entry, "get"):
        return entry.get(key, default)
    return getattr(entry, key, default)


def build_google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"


def fetch_candidates(now_iso: str) -> list[BacklogItem]:
    try:
        import feedparser
        import trafilatura
    except ModuleNotFoundError:
        return []

    items: list[BacklogItem] = []
    for query in AI_SEARCH_QUERIES:
        feed = feedparser.parse(build_google_news_url(query))
        for entry in getattr(feed, "entries", []):
            source = _get_value(entry, "source", {})
            source_name = source.get("title", "unknown") if isinstance(source, dict) else getattr(source, "title", "unknown")
            title = _get_value(entry, "title", "")
            url = _get_value(entry, "link", "")
            downloaded = trafilatura.fetch_url(url) or ""
            extracted = trafilatura.extract(downloaded) or _get_value(entry, "summary", "")
            items.append(
                BacklogItem(
                    item_id=str(uuid4()),
                    source_url=url,
                    source_title=title,
                    normalized_title=normalize_title(title),
                    topic_fingerprint=normalize_title(title).replace(" ", "-"),
                    source_name=source_name,
                    published_at=_get_value(entry, "published", now_iso),
                    summary_candidate=extracted[:800],
                    status="new",
                    first_seen_at=now_iso,
                    last_considered_at=now_iso,
                )
            )
    return items
