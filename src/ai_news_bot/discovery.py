from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from ai_news_bot.models import BacklogItem
from ai_news_bot.source_registry import SourceConfig, load_sources


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _get_value(entry, key: str, default: str = "") -> str:
    if hasattr(entry, "get"):
        return entry.get(key, default)
    return getattr(entry, key, default)


def parse_feed(feed_url: str) -> list:
    import feedparser

    return list(getattr(feedparser.parse(feed_url), "entries", []))


def fetch_page_text(url: str) -> str:
    import trafilatura

    downloaded = trafilatura.fetch_url(url) or ""
    return trafilatura.extract(downloaded) or ""


def build_candidate_from_entry(source: SourceConfig, entry, now_iso: str) -> BacklogItem:
    title = _get_value(entry, "title", "")
    url = _get_value(entry, "link", "")
    summary = fetch_page_text(url) or _get_value(entry, "summary", "")
    is_confirmed = source.tier != "tier4_community"
    status = "new" if is_confirmed else "observed_unconfirmed"
    return BacklogItem(
        item_id=str(uuid4()),
        source_url=url,
        source_title=title,
        normalized_title=normalize_title(title),
        topic_fingerprint=normalize_title(title).replace(" ", "-"),
        source_name=source.name,
        published_at=_get_value(entry, "published", now_iso),
        summary_candidate=summary[:800],
        status=status,
        first_seen_at=now_iso,
        last_considered_at=now_iso,
        source_tier=source.tier,
        source_kind=source.kind,
        source_priority=source.priority,
        confirmed=is_confirmed,
        evidence_urls=[url],
    )


def fetch_candidates_from_sources(sources: list[SourceConfig], now_iso: str) -> list[BacklogItem]:
    items: list[BacklogItem] = []
    for source in sources:
        try:
            entries = parse_feed(source.feed_url)
        except Exception:
            continue
        for entry in entries:
            items.append(build_candidate_from_entry(source, entry, now_iso))
    return items


def fetch_candidates(now_iso: str, *, sources_path: Path | None = None) -> list[BacklogItem]:
    path = sources_path or (Path(__file__).resolve().parents[2] / "sources.yaml")
    return fetch_candidates_from_sources(load_sources(path), now_iso)
