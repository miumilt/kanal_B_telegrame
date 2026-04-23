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


def _normalized_status(item: BacklogItem) -> str:
    if item.confirmed:
        if item.status in {"published", "drafted", "skipped"}:
            return item.status
        return "queued"
    return "observed_unconfirmed"


def _select_primary(existing: BacklogItem, incoming: BacklogItem) -> BacklogItem:
    if incoming.source_priority > existing.source_priority:
        winner, loser = incoming, existing
    else:
        winner, loser = existing, incoming

    winner.evidence_urls = sorted(
        set((winner.evidence_urls or []) + (loser.evidence_urls or []) + [winner.source_url, loser.source_url])
    )
    winner.confirmed = existing.confirmed or incoming.confirmed
    winner.status = _normalized_status(winner)
    winner.first_seen_at = min(existing.first_seen_at, incoming.first_seen_at)
    winner.last_considered_at = max(existing.last_considered_at, incoming.last_considered_at)
    return winner


def merge_candidates(
    existing: list[BacklogItem],
    incoming: list[BacklogItem],
    *,
    now_iso: str,
    expiry_days: int,
) -> list[BacklogItem]:
    now = _parse_timestamp(now_iso)
    cutoff = timedelta(days=expiry_days)
    merged_by_title: dict[str, BacklogItem] = {}

    for item in existing:
        if now - _parse_timestamp(item.published_at) > cutoff:
            continue
        item.status = _normalized_status(item)
        current = merged_by_title.get(item.normalized_title)
        if current is None:
            merged_by_title[item.normalized_title] = item
        else:
            merged_by_title[item.normalized_title] = _select_primary(current, item)

    for item in incoming:
        if now - _parse_timestamp(item.published_at) > cutoff:
            continue
        item.status = _normalized_status(item)
        current = merged_by_title.get(item.normalized_title)
        if current is None:
            merged_by_title[item.normalized_title] = item
        else:
            merged_by_title[item.normalized_title] = _select_primary(current, item)

    return list(merged_by_title.values())


def select_main_slot_items(backlog: list[BacklogItem], limit: int = 5) -> list[BacklogItem]:
    queued = [item for item in backlog if item.status == "queued" and item.confirmed]
    return sorted(queued, key=score_item, reverse=True)[:limit]


def select_daily_slot_items(backlog: list[BacklogItem], limit: int = 3) -> list[BacklogItem]:
    return select_daily_slot_items_with_age(backlog, limit=limit)


def select_daily_slot_items_with_age(
    backlog: list[BacklogItem],
    *,
    limit: int = 3,
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
