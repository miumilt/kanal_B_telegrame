from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from ai_news_bot.config import resolve_project_root
from ai_news_bot.editorial import classify_candidate
from ai_news_bot.media import extract_image_url
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
    return extract_text_from_html(fetch_page_html(url))


def fetch_page_html(url: str) -> str:
    import trafilatura

    return trafilatura.fetch_url(url) or ""


def extract_text_from_html(html: str) -> str:
    import trafilatura

    return trafilatura.extract(html) or ""


def _entry_value(entry, key: str, default=None):
    if hasattr(entry, "get"):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _resolve_image_url(page_url: str, candidate: str) -> str:
    from urllib.parse import urljoin

    return urljoin(page_url, candidate)


def _extract_feed_image_url(entry, page_url: str) -> str | None:
    for key in ("media_thumbnail", "media_content"):
        media_items = _entry_value(entry, key, [])
        if isinstance(media_items, list):
            for media_item in media_items:
                if isinstance(media_item, dict):
                    candidate = media_item.get("url")
                    if isinstance(candidate, str) and candidate.strip():
                        return _resolve_image_url(page_url, candidate.strip())

    links = _entry_value(entry, "links", [])
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            href = link.get("href")
            link_type = str(link.get("type", "")).lower()
            rel = str(link.get("rel", "")).lower()
            if isinstance(href, str) and href.strip() and rel == "enclosure" and link_type.startswith("image/"):
                return _resolve_image_url(page_url, href.strip())

    for key in ("summary", "content", "description"):
        value = _entry_value(entry, key, "")
        if isinstance(value, str) and ("<img" in value.lower() or "og:image" in value.lower()):
            candidate = extract_image_url(value, page_url)
            if candidate:
                return candidate
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    html = item.get("value", "")
                    if isinstance(html, str) and ("<img" in html.lower() or "og:image" in html.lower()):
                        candidate = extract_image_url(html, page_url)
                        if candidate:
                            return candidate
    return None


def build_candidate_from_entry(source: SourceConfig, entry, now_iso: str) -> BacklogItem:
    title = _get_value(entry, "title", "")
    url = _get_value(entry, "link", "")
    summary = _get_value(entry, "summary", "")
    image_url: str | None = _extract_feed_image_url(entry, url)
    if source.kind == "website" and not summary:
        page_html = fetch_page_html(url)
        summary = extract_text_from_html(page_html)
        if image_url is None:
            image_url = extract_image_url(page_html, url)
    category = classify_candidate(
        BacklogItem(
            item_id="",
            source_url=url,
            source_title=title,
            normalized_title=normalize_title(title),
            topic_fingerprint=normalize_title(title).replace(" ", "-"),
            source_name=source.name,
            published_at=_get_value(entry, "published", now_iso),
            summary_candidate=summary[:800],
            status="new",
            first_seen_at=now_iso,
            last_considered_at=now_iso,
        )
    )
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
        category=category,
        image_url=image_url,
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
    path = sources_path or (resolve_project_root() / "sources.yaml")
    return fetch_candidates_from_sources(load_sources(path), now_iso)
