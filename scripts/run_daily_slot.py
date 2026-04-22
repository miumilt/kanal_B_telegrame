from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ai_news_bot.approval import build_draft_keyboard
from ai_news_bot.backlog import merge_candidates, select_daily_slot_items_with_age
from ai_news_bot.config import load_config
from ai_news_bot.drafts import build_single_post_text
from ai_news_bot.models import BacklogItem, DraftRecord
from ai_news_bot.storage import JsonStateStore
from ai_news_bot.telegram_api import TelegramApi

BACKLOG_EXPIRY_DAYS = 14
DAILY_CANDIDATE_MAX_AGE_DAYS = 1


def _require_replaceable_draft(draft: DraftRecord | None) -> DraftRecord | None:
    if draft is None:
        return None
    if draft.status == "publishing":
        raise RuntimeError("Cannot replace draft while publication recovery is pending")
    return draft


def _send_owner_draft_preview(
    telegram_api: TelegramApi,
    owner_chat_id: str,
    draft: DraftRecord,
    reply_markup: dict | None = None,
) -> None:
    if draft.image_url:
        telegram_api.send_photo(
            owner_chat_id,
            draft.image_url,
            caption=draft.current_text,
            reply_markup=reply_markup,
        )
        return

    telegram_api.send_message(
        owner_chat_id,
        draft.current_text,
        reply_markup,
    )


def _build_preview_draft(primary_item: BacklogItem) -> DraftRecord:
    generated_text = build_single_post_text(primary_item)
    return DraftRecord(
        draft_id=str(uuid4()),
        generated_text=generated_text,
        current_text=generated_text,
        selected_story_ids=[primary_item.item_id],
        draft_type="single_post",
        status="pending",
        created_at=datetime.now(UTC).isoformat(),
        category=primary_item.category,
        header_label="Single Post",
        image_url=primary_item.image_url,
    )


def release_unpublished_draft_items(
    store: JsonStateStore,
    draft: DraftRecord | None,
    *,
    preserve_story_ids: set[str] | None = None,
) -> None:
    if draft is None:
        return

    preserved_ids = preserve_story_ids or set()
    selected_ids = set(draft.selected_story_ids) - preserved_ids
    if not selected_ids:
        return

    backlog = store.load_backlog()
    published_urls = set(store.load_published())
    changed = False
    for item in backlog:
        if item.item_id not in selected_ids:
            continue
        if item.status == "published" or item.source_url in published_urls:
            continue
        if item.status != "queued":
            item.status = "queued"
            changed = True

    if changed:
        store.save_backlog(backlog)


def release_unpublished_owner_drafts(store: JsonStateStore) -> None:
    owner_drafts = store.load_owner_drafts()
    if not owner_drafts:
        return

    for draft in owner_drafts:
        release_unpublished_draft_items(store, draft)
    store.save_owner_drafts([])
    current_draft = store.load_current_draft()
    if current_draft is not None and current_draft.status not in {"published", "publishing"}:
        store.save_current_draft(None)


def refresh_backlog(
    store: JsonStateStore,
    *,
    now_iso: str,
    fetcher=None,
    expiry_days: int = BACKLOG_EXPIRY_DAYS,
) -> list[BacklogItem]:
    if fetcher is None:
        from ai_news_bot.discovery import fetch_candidates

        fetcher = fetch_candidates
    refreshed = merge_candidates(
        store.load_backlog(),
        fetcher(now_iso),
        now_iso=now_iso,
        expiry_days=expiry_days,
    )
    store.save_backlog(refreshed)
    return refreshed


def build_main_slot_draft(
    store: JsonStateStore,
    telegram_api: TelegramApi | None = None,
    owner_chat_id: str | None = None,
    now_iso: str | None = None,
    max_age_days: int | None = None,
) -> DraftRecord:
    current_draft = _require_replaceable_draft(store.load_current_draft())
    release_unpublished_owner_drafts(store)
    release_unpublished_draft_items(store, current_draft)

    backlog = store.load_backlog()
    selected = select_daily_slot_items_with_age(
        backlog,
        now_iso=now_iso,
        max_age_days=max_age_days,
    )
    if not selected:
        raise RuntimeError("No eligible backlog items for draft")

    owner_drafts = [_build_preview_draft(item) for item in selected]
    draft = owner_drafts[0]
    store.save_current_draft(draft)
    store.save_owner_drafts(owner_drafts)

    selected_ids = {item.item_id for item in selected}
    updated_backlog = []
    for item in backlog:
        if item.item_id in selected_ids:
            item.status = "drafted"
        updated_backlog.append(item)
    store.save_backlog(updated_backlog)

    if telegram_api is not None and owner_chat_id:
        for preview_draft in owner_drafts:
            _send_owner_draft_preview(
                telegram_api,
                owner_chat_id,
                preview_draft,
                build_draft_keyboard(preview_draft.draft_id),
            )

    return draft


def run_daily_slot(
    store: JsonStateStore,
    *,
    telegram_api: TelegramApi | None = None,
    owner_chat_id: str | None = None,
    now_iso: str | None = None,
    fetcher=None,
) -> DraftRecord | None:
    current_now_iso = now_iso or datetime.now(UTC).isoformat()
    if fetcher is None:
        from ai_news_bot.discovery import fetch_candidates

        fetcher = fetch_candidates
    backlog = refresh_backlog(store, now_iso=current_now_iso, fetcher=fetcher)
    if not select_daily_slot_items_with_age(
        backlog,
        now_iso=current_now_iso,
        max_age_days=DAILY_CANDIDATE_MAX_AGE_DAYS,
    ):
        if telegram_api is not None and owner_chat_id:
            telegram_api.send_message(
                owner_chat_id,
                "No eligible backlog items for draft today.",
            )
        return None

    return build_main_slot_draft(
        store,
        telegram_api=telegram_api,
        owner_chat_id=owner_chat_id,
        now_iso=current_now_iso,
        max_age_days=DAILY_CANDIDATE_MAX_AGE_DAYS,
    )


def main() -> DraftRecord | None:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    from ai_news_bot.discovery import fetch_candidates

    return run_daily_slot(
        store,
        telegram_api=telegram_api,
        owner_chat_id=config.telegram_owner_chat_id,
        fetcher=lambda now_iso: fetch_candidates(now_iso, sources_path=config.sources_path),
    )


if __name__ == "__main__":
    main()
