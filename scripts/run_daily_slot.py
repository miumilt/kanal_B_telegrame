from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ai_news_bot.approval import build_draft_keyboard
from ai_news_bot.backlog import select_main_slot_items
from ai_news_bot.config import load_config
from ai_news_bot.drafts import build_digest_text, build_short_post_text
from ai_news_bot.models import DraftRecord
from ai_news_bot.storage import JsonStateStore
from ai_news_bot.telegram_api import TelegramApi


def _require_replaceable_draft(draft: DraftRecord | None) -> DraftRecord | None:
    if draft is None:
        return None
    if draft.status == "publishing":
        raise RuntimeError("Cannot replace draft while publication recovery is pending")
    if draft.approved_for_slot and draft.approved_at is not None and draft.status != "published":
        raise RuntimeError("Cannot replace draft while scheduled publication is pending")
    return draft


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


def build_main_slot_draft(
    store: JsonStateStore,
    telegram_api: TelegramApi | None = None,
    owner_chat_id: str | None = None,
) -> DraftRecord:
    release_unpublished_draft_items(store, _require_replaceable_draft(store.load_current_draft()))

    backlog = store.load_backlog()
    selected = select_main_slot_items(backlog)
    if not selected:
        raise RuntimeError("No eligible backlog items for draft")

    if len(selected) == 1:
        generated_text = build_short_post_text(selected[0])
        draft_type = "short_post"
    else:
        generated_text = build_digest_text(selected)
        draft_type = "digest"

    draft = DraftRecord(
        draft_id=str(uuid4()),
        generated_text=generated_text,
        current_text=generated_text,
        selected_story_ids=[item.item_id for item in selected],
        draft_type=draft_type,
        status="pending",
        created_at=datetime.now(UTC).isoformat(),
        approved_for_slot=False,
        approved_at=None,
    )
    store.save_current_draft(draft)

    selected_ids = set(draft.selected_story_ids)
    updated_backlog = []
    for item in backlog:
        if item.item_id in selected_ids:
            item.status = "drafted"
        updated_backlog.append(item)
    store.save_backlog(updated_backlog)

    if telegram_api is not None and owner_chat_id:
        telegram_api.send_message(
            owner_chat_id,
            draft.generated_text,
            build_draft_keyboard(draft.draft_id),
        )

    return draft


def main() -> DraftRecord:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    return build_main_slot_draft(
        store,
        telegram_api=telegram_api,
        owner_chat_id=config.telegram_owner_chat_id,
    )


if __name__ == "__main__":
    main()
