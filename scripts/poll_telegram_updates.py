from __future__ import annotations

from datetime import UTC, datetime

from ai_news_bot.approval import (
    build_draft_keyboard,
    mark_draft_approved,
    mark_draft_editing,
    mark_draft_publish_now,
    parse_owner_command,
    should_publish_now,
)
from ai_news_bot.config import load_config
from ai_news_bot.drafts import build_short_post_text
from ai_news_bot.models import DraftRecord
from ai_news_bot.storage import JsonStateStore
from ai_news_bot.telegram_api import TelegramApi


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _owner_matches(chat_id: object, owner_chat_id: object) -> bool:
    return chat_id is not None and owner_chat_id is not None and str(chat_id) == str(owner_chat_id)


def _message_chat_id(message: dict) -> object:
    chat = message.get("chat") or {}
    return chat.get("id")


def _callback_chat_id(callback: dict) -> object:
    message = callback.get("message") or {}
    return _message_chat_id(message)


def _finalize_publication(store: JsonStateStore, draft: DraftRecord) -> None:
    backlog = store.load_backlog()
    published_ids = set(draft.selected_story_ids)
    published_urls = set(store.load_published())
    for item in backlog:
        if item.item_id in published_ids:
            item.status = "published"
            published_urls.add(item.source_url)
    store.save_backlog(backlog)
    store.save_published(sorted(published_urls))
    draft.status = "published"
    store.save_current_draft(draft)


def _replaceable_draft_or_none(draft: DraftRecord | None) -> DraftRecord | None:
    if draft is not None and draft.status == "publishing":
        return None
    return draft


def _release_unpublished_draft_items(
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


def _publish_draft(store: JsonStateStore, telegram_api: TelegramApi, channel_id: str, draft: DraftRecord) -> None:
    if draft.status == "published":
        return

    if draft.status == "publishing":
        _finalize_publication(store, draft)
        return

    original_status = draft.status
    if draft.status != "publishing":
        draft.status = "publishing"
        store.save_current_draft(draft)
        try:
            telegram_api.send_message(channel_id, draft.current_text)
        except Exception:
            draft.status = original_status
            store.save_current_draft(draft)
            raise

    _finalize_publication(store, draft)


def _build_short_draft(store: JsonStateStore, item_id: str) -> DraftRecord | None:
    current_draft = _replaceable_draft_or_none(store.load_current_draft())
    if current_draft is None and store.load_current_draft() is not None:
        return None

    backlog = store.load_backlog()
    item = next((entry for entry in backlog if entry.item_id == item_id and entry.status in {"queued", "drafted"}), None)
    if item is None:
        return None

    _release_unpublished_draft_items(
        store,
        current_draft,
        preserve_story_ids={item_id},
    )
    backlog = store.load_backlog()
    item = next((entry for entry in backlog if entry.item_id == item_id and entry.status in {"queued", "drafted"}), None)
    if item is None:
        return None

    generated_text = build_short_post_text(item)
    draft = DraftRecord(
        draft_id=f"short-{item.item_id}",
        generated_text=generated_text,
        current_text=generated_text,
        selected_story_ids=[item.item_id],
        draft_type="short_post",
        status="pending",
        created_at=_now_iso(),
        approved_for_slot=False,
        approved_at=None,
    )
    store.save_current_draft(draft)

    for backlog_item in backlog:
        if backlog_item.item_id == item.item_id:
            backlog_item.status = "drafted"
    store.save_backlog(backlog)
    return draft


def process_updates(store: JsonStateStore, telegram_api: TelegramApi, config) -> None:
    cursor = store.load_cursor()
    updates = telegram_api.get_updates(offset=cursor + 1)

    for update in updates:
        cursor = update["update_id"]
        callback = update.get("callback_query")
        message = update.get("message")

        if callback is not None:
            if not _owner_matches(_callback_chat_id(callback), config.telegram_owner_chat_id):
                continue

            draft = store.load_current_draft()
            if draft is None:
                continue
            if draft.status == "publishing":
                continue

            data = callback.get("data", "")
            if data == f"edit:{draft.draft_id}":
                mark_draft_editing(draft)
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Send replacement text as the next message")
            elif data == f"approve:{draft.draft_id}":
                mark_draft_approved(draft, _now_iso())
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Draft approved for 18:00")
            elif data == f"publish_now:{draft.draft_id}":
                mark_draft_publish_now(draft, _now_iso())
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Draft will publish immediately")
            elif data == f"skip:{draft.draft_id}":
                _release_unpublished_draft_items(store, draft)
                draft.approved_for_slot = False
                draft.approved_at = None
                draft.status = "skipped"
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Draft skipped")
            continue

        if message is None:
            continue
        if not _owner_matches(_message_chat_id(message), config.telegram_owner_chat_id):
            continue

        draft = store.load_current_draft()
        text = (message.get("text") or "").strip()

        if draft is not None and draft.status == "editing" and text:
            draft.current_text = text
            draft.status = "pending"
            store.save_current_draft(draft)
            telegram_api.send_message(
                config.telegram_owner_chat_id,
                "Draft updated. You can publish or edit again.",
                build_draft_keyboard(draft.draft_id),
            )
            continue

        command, arg = parse_owner_command(text)
        if command == "backlog":
            queued = [item for item in store.load_backlog() if item.status == "queued"][:10]
            lines = [f"{item.item_id}: {item.source_title}" for item in queued]
            telegram_api.send_message(
                config.telegram_owner_chat_id,
                "\n".join(lines) if lines else "Backlog is empty",
            )
        elif command == "short" and arg:
            short_draft = _build_short_draft(store, arg)
            if short_draft is not None:
                telegram_api.send_message(
                    config.telegram_owner_chat_id,
                    short_draft.generated_text,
                    build_draft_keyboard(short_draft.draft_id),
                )
        elif command == "publish_now" and arg:
            short_draft = _build_short_draft(store, arg)
            if short_draft is not None:
                mark_draft_publish_now(short_draft, _now_iso())
                store.save_current_draft(short_draft)

    store.save_cursor(cursor)

    draft = store.load_current_draft()
    if draft is None or draft.approved_at is None or draft.status == "skipped":
        return

    if draft.status == "publishing":
        _publish_draft(store, telegram_api, config.telegram_channel_id, draft)
        return

    if draft.approved_for_slot:
        if not should_publish_now(
            approved_at_iso=draft.approved_at,
            now_iso=_now_iso(),
            slot_hour=config.daily_slot_hour,
            slot_minute=config.daily_slot_minute,
        ):
            return

    _publish_draft(store, telegram_api, config.telegram_channel_id, draft)


def main() -> None:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    process_updates(store, telegram_api, config)


if __name__ == "__main__":
    main()
