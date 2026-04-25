from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import UTC, datetime, timedelta

from ai_news_bot.models import BacklogItem
from ai_news_bot.ranking import score_item
from ai_news_bot.topics import canonicalize_url


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _normalized_status(item: BacklogItem) -> str:
    if item.confirmed:
        if item.status in {"published", "drafted", "skipped"}:
            return item.status
        return "queued"
    return "observed_unconfirmed"


def _merged_status(existing: BacklogItem, incoming: BacklogItem, winner: BacklogItem) -> str:
    statuses = {existing.status, incoming.status}
    for status in ("published", "drafted", "skipped"):
        if status in statuses:
            return status
    return _normalized_status(winner)


def _select_primary(existing: BacklogItem, incoming: BacklogItem) -> BacklogItem:
    if incoming.source_priority > existing.source_priority:
        winner, loser = incoming, existing
    else:
        winner, loser = existing, incoming

    winner.evidence_urls = sorted(
        set((winner.evidence_urls or []) + (loser.evidence_urls or []) + [winner.source_url, loser.source_url])
    )
    winner.confirmed = existing.confirmed or incoming.confirmed
    winner.status = _merged_status(existing, incoming, winner)
    winner.first_seen_at = min(existing.first_seen_at, incoming.first_seen_at)
    winner.last_considered_at = max(existing.last_considered_at, incoming.last_considered_at)
    if winner.image_url is None:
        winner.image_url = loser.image_url
    if winner.video_url is None:
        winner.video_url = loser.video_url
    return winner


def _merge_key(item: BacklogItem) -> str:
    if item.topic_fingerprint:
        return f"topic:{item.topic_fingerprint}"
    return f"url:{canonicalize_url(item.source_url)}"


def merge_candidates(
    existing: list[BacklogItem],
    incoming: list[BacklogItem],
    *,
    now_iso: str,
    expiry_days: int,
) -> list[BacklogItem]:
    now = _parse_timestamp(now_iso)
    cutoff = timedelta(days=expiry_days)
    merged_by_key: dict[str, BacklogItem] = {}

    for item in existing:
        if now - _parse_timestamp(item.published_at) > cutoff:
            continue
        item.status = _normalized_status(item)
        key = _merge_key(item)
        current = merged_by_key.get(key)
        if current is None:
            merged_by_key[key] = item
        else:
            merged_by_key[key] = _select_primary(current, item)

    for item in incoming:
        if now - _parse_timestamp(item.published_at) > cutoff:
            continue
        item.status = _normalized_status(item)
        key = _merge_key(item)
        current = merged_by_key.get(key)
        if current is None:
            merged_by_key[key] = item
        else:
            merged_by_key[key] = _select_primary(current, item)

    return list(merged_by_key.values())


def select_main_slot_items(backlog: list[BacklogItem], limit: int = 5) -> list[BacklogItem]:
    queued = [item for item in backlog if item.status == "queued" and item.confirmed]
    return sorted(queued, key=score_item, reverse=True)[:limit]


def select_daily_slot_items(backlog: list[BacklogItem], limit: int = 10) -> list[BacklogItem]:
    return select_daily_slot_items_with_age(backlog, limit=limit)


def select_daily_slot_items_with_age(
    backlog: list[BacklogItem],
    *,
    limit: int = 10,
    now_iso: str | None = None,
    max_age_days: int | None = None,
) -> list[BacklogItem]:
    queued = [item for item in backlog if item.status == "queued" and item.confirmed]
    if now_iso is not None and max_age_days is not None:
        now = _parse_timestamp(now_iso)
        cutoff = timedelta(days=max_age_days)
        queued = [
            item for item in queued
            if now - _parse_timestamp(item.published_at) <= cutoff
        ]
    if limit <= 0 or not queued:
        return []

    return sorted(queued, key=score_item, reverse=True)[:limit]


def select_watcher_items(
    backlog: list[BacklogItem],
    *,
    sent_topics: set[str],
    limit: int,
    now_iso: str,
    max_age_hours: int,
) -> list[BacklogItem]:
    now = _parse_timestamp(now_iso)
    cutoff = timedelta(hours=max_age_hours)
    queued = [
        item for item in backlog
        if item.status == "queued"
        and item.confirmed
        and item.topic_fingerprint not in sent_topics
        and now - _parse_timestamp(item.published_at) <= cutoff
    ]
    if limit <= 0 or not queued:
        return []
    return sorted(queued, key=score_item, reverse=True)[:limit]
