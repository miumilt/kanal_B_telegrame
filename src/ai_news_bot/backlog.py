from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import UTC, datetime, timedelta

from ai_news_bot.models import BacklogItem
from ai_news_bot.ranking import score_item


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def merge_candidates(
    existing: list[BacklogItem],
    incoming: list[BacklogItem],
    *,
    now_iso: str,
    expiry_days: int,
) -> list[BacklogItem]:
    now = _parse_timestamp(now_iso)
    cutoff = timedelta(days=expiry_days)
    merged: list[BacklogItem] = []
    seen_titles: set[str] = set()

    for item in existing:
        if now - _parse_timestamp(item.published_at) > cutoff:
            continue
        if item.normalized_title in seen_titles:
            continue
        seen_titles.add(item.normalized_title)
        merged.append(item)

    for item in incoming:
        if now - _parse_timestamp(item.published_at) > cutoff:
            continue
        if item.normalized_title in seen_titles:
            continue
        seen_titles.add(item.normalized_title)
        merged.append(item)

    return merged


def select_main_slot_items(backlog: list[BacklogItem], limit: int = 5) -> list[BacklogItem]:
    queued = [item for item in backlog if item.status == "queued"]
    return sorted(queued, key=score_item, reverse=True)[:limit]
